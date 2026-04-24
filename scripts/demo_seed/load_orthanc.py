"""Upload cached TCIA DICOMs to Orthanc via STOW-RS.

Dev-spec buyer-portal-demo §8.3 step 2 (``load_orthanc.py``). Called by
``inject_all.sh`` after ``download_tcia.py`` has populated the cache.

Idempotent at the study level:

* If ``{study_dir}/_orthanc_uploaded.marker`` exists → skip (matches the
  ``_done.marker`` produced by the downloader).
* Each study is one STOW-RS transaction (multipart/related). Failure on a
  single study does not abort the run; we record the failure and move on.

Required:
* Orthanc reachable at ``--orthanc-url`` (default ``http://localhost:8042``).
* Basic auth credentials — default ``orthanc:orthanc`` per seed_config.yaml.

If Orthanc is not running, exit with code 3 and a clear hint for the
operator (FR-S-8 step 1).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
import uuid
from pathlib import Path

import httpx

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

log = logging.getLogger("demo_seed.orthanc")

STOW_BOUNDARY = "radivault-stow"
UPLOADED_MARKER = "_orthanc_uploaded.marker"
DEFAULT_TIMEOUT = 60.0  # per-study STOW-RS request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_study_dirs(cache_dir: Path) -> list[Path]:
    """Return study directories (one level below collection)."""
    out: list[Path] = []
    if not cache_dir.exists():
        return out
    for collection in sorted(cache_dir.iterdir()):
        if not collection.is_dir():
            continue
        for study in sorted(collection.iterdir()):
            if study.is_dir() and (study / "_done.marker").exists():
                out.append(study)
    return out


def _multipart_payload(dcm_files: list[Path], boundary: str) -> bytes:
    """Build a multipart/related body suitable for STOW-RS.

    See RFC 7578 + DICOM PS3.18 §6.6 for the shape. Each part is:

        --{boundary}
        Content-Type: application/dicom

        <raw .dcm bytes>

    followed by a terminating ``--{boundary}--`` marker.
    """
    crlf = b"\r\n"
    parts: list[bytes] = []
    for f in dcm_files:
        parts.append(b"--" + boundary.encode("ascii") + crlf)
        parts.append(b"Content-Type: application/dicom" + crlf)
        parts.append(crlf)
        parts.append(f.read_bytes())
        parts.append(crlf)
    parts.append(b"--" + boundary.encode("ascii") + b"--" + crlf)
    return b"".join(parts)


def _auth_header(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("ascii")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def check_orthanc(client: httpx.Client) -> None:
    """Ping Orthanc /system; exit 3 with a hint if unreachable."""
    try:
        resp = client.get("/system", timeout=5.0)
        resp.raise_for_status()
    except Exception as exc:
        sys.stderr.write(
            "[ERR_SEED_ORTHANC_DOWN] Orthanc unreachable / Orthanc에 접속할 수 없습니다.\n"
            f"  cause: {exc}\n"
            "  hint : docker compose -f docker-compose.yml up -d orthanc\n"
            "         (dev-spec buyer-portal-demo §8.3 step 1)\n"
        )
        raise SystemExit(3) from None


def upload_study(
    client: httpx.Client,
    study_dir: Path,
    *,
    boundary: str = STOW_BOUNDARY,
) -> tuple[int, int]:
    """Upload one study directory via STOW-RS. Returns (files_sent, http_status)."""
    dcm_files = sorted(study_dir.rglob("*.dcm"))
    if not dcm_files:
        raise RuntimeError(f"no DICOM files under {study_dir}")
    body = _multipart_payload(dcm_files, boundary)
    headers = {
        "Content-Type": f"multipart/related; type=application/dicom; boundary={boundary}",
        "Accept": "application/dicom+json",
    }
    resp = client.post(
        "/dicom-web/studies",
        content=body,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return len(dcm_files), resp.status_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload cached DICOM to Orthanc (STOW-RS)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "seed_config.yaml",
    )
    parser.add_argument("--orthanc-url", default=None, help="Override Orthanc base URL")
    parser.add_argument("--username", default=None, help="Override Orthanc username")
    parser.add_argument("--password", default=None, help="Override Orthanc password")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Override seed_config.yaml cache_dir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List studies that would be uploaded and exit.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Config load — cache_dir + orthanc defaults come from YAML unless
    # overridden by flags.
    cfg: dict = {}
    if args.config.exists():
        if yaml is None:
            raise SystemExit("PyYAML is required. `pip install pyyaml`.")
        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}

    cache_dir = (args.cache_dir or Path(cfg.get("cache_dir", "./demo_data/cache"))).resolve()
    orthanc_cfg = cfg.get("orthanc", {}) or {}
    base_url = args.orthanc_url or orthanc_cfg.get("url", "http://localhost:8042")
    username = args.username or orthanc_cfg.get("username", "orthanc")
    password = args.password or orthanc_cfg.get("password", "orthanc")

    studies = _iter_study_dirs(cache_dir)
    if not studies:
        log.warning("no_studies cache_dir=%s (did you run download_tcia.py?)", cache_dir)
        return 0

    if args.dry_run:
        json.dump(
            [
                {
                    "study_dir": str(s),
                    "dcm_files": sum(1 for _ in s.rglob("*.dcm")),
                    "already_uploaded": (s / UPLOADED_MARKER).exists(),
                }
                for s in studies
            ],
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    headers = {"Authorization": _auth_header(username, password)}
    with httpx.Client(base_url=base_url, headers=headers) as client:
        check_orthanc(client)

        skipped = 0
        done = 0
        failed = 0
        total_files = 0
        for study in studies:
            marker = study / UPLOADED_MARKER
            if marker.exists():
                skipped += 1
                continue
            try:
                boundary = f"{STOW_BOUNDARY}-{uuid.uuid4().hex[:8]}"
                n_files, status = upload_study(client, study, boundary=boundary)
                marker.write_text(f"status={status} files={n_files}\n", encoding="utf-8")
                done += 1
                total_files += n_files
                log.info("stow_done study=%s files=%d status=%d", study.name, n_files, status)
            except Exception as exc:
                failed += 1
                (study / "_orthanc_error.json").write_text(
                    json.dumps({"error": str(exc)}, indent=2), encoding="utf-8"
                )
                log.error("stow_failed study=%s err=%s", study.name, exc)

    log.info(
        "orthanc_load_complete skipped=%d done=%d failed=%d files=%d",
        skipped,
        done,
        failed,
        total_files,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
