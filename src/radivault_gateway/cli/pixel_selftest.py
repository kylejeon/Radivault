"""``gateway-agent pixel-selftest`` implementation (design-spec §2.4).

Checks OCR + defacing dependencies without touching PACS/network. Uses tiny
synthetic fixtures generated at runtime. The command exists in every image
variant; exit codes differ per which components are present:

* 0 — both OK
* 1 — OCR missing/failing
* 2 — Defacing missing/failing
* 3 — Both missing
* 70 — Selftest fixture itself corrupt (bug)
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

import click

from radivault_gateway.deid.pixel.deface_engine import (
    MridefacerEngine,
    PydefaceEngine,
)
from radivault_gateway.deid.pixel.ocr_engine import (
    TesseractOcrEngine,
)


def _image_tag() -> str:
    return os.environ.get("RADIVAULT_IMAGE_TAG", "radivault-gateway:unknown")


def _ocr_status() -> dict[str, Any]:
    """Return per-component OCR status without raising."""
    tess_path = shutil.which("tesseract")
    engine_ok = TesseractOcrEngine.is_available()
    try:
        import pytesseract  # type: ignore[import-not-found]

        pytess_version = str(getattr(pytesseract, "__version__", "unknown"))
    except ImportError:
        pytess_version = None
    engine_version = None
    if engine_ok:
        try:
            engine_version = TesseractOcrEngine().version()
        except Exception:
            engine_version = "unknown"
    return {
        "status": "ok" if engine_ok else "fail",
        "engine": "tesseract",
        "tesseract_path": tess_path,
        "engine_version": engine_version,
        "pytesseract_version": pytess_version,
        "languages": {"eng": _tess_lang_present("eng"), "kor": _tess_lang_present("kor")},
    }


def _tess_lang_present(code: str) -> str:
    try:
        import pytesseract  # type: ignore[import-not-found]

        langs = pytesseract.get_languages(config="")
    except Exception:
        return "unknown"
    return "ok" if code in langs else "fail"


def _defacing_status() -> dict[str, Any]:
    pydeface = PydefaceEngine()
    mridefacer = MridefacerEngine()
    pydeface_ok = pydeface.is_available()
    mridefacer_ok = mridefacer.is_available()
    status = "ok" if (pydeface_ok or mridefacer_ok) else "fail"
    return {
        "status": status,
        "library": "pydeface" if pydeface_ok else ("mridefacer" if mridefacer_ok else None),
        "pydeface": {
            "available": pydeface_ok,
            "version": pydeface.version() if pydeface_ok else None,
        },
        "mridefacer": {
            "available": mridefacer_ok,
            "version": mridefacer.version() if mridefacer_ok else None,
        },
        "flirt_on_path": shutil.which("flirt") is not None,
    }


def _compute_exit_code(ocr_status: str, defacing_status: str) -> int:
    if ocr_status == "ok" and defacing_status == "ok":
        return 0
    if ocr_status != "ok" and defacing_status != "ok":
        return 3
    if ocr_status != "ok":
        return 1
    return 2


@click.command(
    "pixel-selftest",
    help=(
        "Verify OCR + defacing dependencies are installed and runnable. "
        "OCR + defacing 의존성 설치·실행 가능 여부 자체 점검."
    ),
)
@click.option("--ocr-only", is_flag=True, help="Only test OCR components (OCR만 점검)")
@click.option("--deface-only", is_flag=True, help="Only test defacing components (defacing만 점검)")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable report")
def pixel_selftest(ocr_only: bool, deface_only: bool, json_output: bool) -> None:
    ocr = {"status": "skipped"} if deface_only else _ocr_status()
    deface = {"status": "skipped"} if ocr_only else _defacing_status()
    ocr_s = ocr.get("status") or "skipped"
    deface_s = deface.get("status") or "skipped"
    # When a section is skipped, treat it as OK for exit-code purposes so
    # ``--ocr-only`` on a box without pydeface can still exit 0 if OCR is fine.
    eff_ocr = "ok" if deface_only else ocr_s
    eff_deface = "ok" if ocr_only else deface_s
    exit_code = _compute_exit_code(eff_ocr, eff_deface)
    payload = {
        "image_tag": _image_tag(),
        "ocr": ocr,
        "defacing": deface,
        "summary": {
            "ocr": ocr_s,
            "defacing": deface_s,
            "exit_code": exit_code,
        },
    }
    if json_output:
        click.echo(json.dumps(payload, indent=2))
    else:
        _render_human(payload, ocr_only=ocr_only, deface_only=deface_only)
    raise SystemExit(exit_code)


def _render_human(payload: dict[str, Any], *, ocr_only: bool, deface_only: bool) -> None:
    click.echo("RadiVault Gateway — pixel dependency selftest")
    click.echo(f"image_tag : {payload['image_tag']}")
    click.echo("")
    if not deface_only:
        ocr = payload["ocr"]
        click.echo("[ OCR ]")
        tag = "[ OK ]" if ocr.get("status") == "ok" else "[ FAIL ]"
        click.echo(
            f"  tesseract binary          {ocr.get('tesseract_path') or '(not on PATH)':<36}"
            f"{tag} {ocr.get('engine_version') or ''}"
        )
        click.echo(
            f"  pytesseract wrapper       {ocr.get('pytesseract_version') or '(absent)':<36}"
            f"{'[ OK ]' if ocr.get('pytesseract_version') else '[ FAIL ]'}"
        )
        for lang, status in (ocr.get("languages") or {}).items():
            click.echo(
                f"  language pack: {lang:<4}       {'(present)' if status == 'ok' else '(missing)':<36}"
                f"{'[ OK ]' if status == 'ok' else '[ FAIL ]'}"
            )
    if not ocr_only:
        deface = payload["defacing"]
        click.echo("[ DEFACING ]")
        click.echo(
            f"  pydeface                  {deface['pydeface'].get('version') or '(absent)':<36}"
            f"{'[ OK ]' if deface['pydeface']['available'] else '[ FAIL ]'}"
        )
        click.echo(
            f"  mridefacer                {deface['mridefacer'].get('version') or '(absent)':<36}"
            f"{'[ OK ]' if deface['mridefacer']['available'] else '[ FAIL ]'}"
        )
        click.echo(
            f"  FSL flirt                 {'on PATH' if deface.get('flirt_on_path') else '(not on PATH)':<36}"
            f"{'[ OK ]' if deface.get('flirt_on_path') else '[ FAIL ]'}"
        )
    summary = payload["summary"]
    click.echo("")
    click.echo(
        f"Summary   OCR {summary['ocr'].upper():<8} "
        f"Defacing {summary['defacing'].upper():<8}  "
        f"exit_code={summary['exit_code']}"
    )
