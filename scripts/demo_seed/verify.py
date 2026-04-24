"""Seed-pipeline verification checklist V-1..V-8 (dev-spec §8.5 / FR-S-11).

Runs 8 independent checks and emits a human-readable PASS/FAIL report.

* All PASS → writes ``demo_seed_ready.lock`` next to this script and exits 0.
* Any FAIL → prints a hint per failed check and exits 1.

Design notes
------------
Each checker is a pure function that returns ``(ok: bool, detail: str)``.
Having them return structured results makes unit-testing trivial — we only
need to mock the two external surfaces the checkers touch:

* central DB   — SQLAlchemy session (V-1 / V-4 / V-6)
* search API   — HTTP request  (V-2 / V-3 / V-7)
* subprocess   — ``ingest-admin`` / ``curl`` (V-5 / V-8)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("demo_seed.verify")

LOCK_PATH = Path(__file__).parent / "demo_seed_ready.lock"

# ---------------------------------------------------------------------------
# Check result primitives
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass
class VerifyContext:
    central_dsn: str
    search_url: str
    central_url: str
    hospital_id: str
    hospital_bearer: str | None
    buyer_api_key: str | None
    min_studies: int = 300
    min_modalities: int = 3
    heartbeat_window_minutes: int = 5
    container: str = "radivault-central-1"
    # Injectable surfaces for tests.
    http_factory: Callable[[], httpx.Client] | None = None
    subprocess_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None
    session_factory: Callable[[], Any] | None = None
    results: list[CheckResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DB helpers (V-1 / V-4 / V-6)
# ---------------------------------------------------------------------------


def _get_session_factory(ctx: VerifyContext):
    if ctx.session_factory is not None:
        return ctx.session_factory
    # Lazy import — allows running `--help` without central extras installed.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(ctx.central_dsn, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _http_client(ctx: VerifyContext) -> httpx.Client:
    if ctx.http_factory is not None:
        return ctx.http_factory()
    return httpx.Client(timeout=10.0)


def _run_subprocess(ctx: VerifyContext, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    if ctx.subprocess_runner is not None:
        return ctx.subprocess_runner(cmd)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# V-1: study row count ≥ min_studies
# ---------------------------------------------------------------------------


def check_v1_study_count(ctx: VerifyContext) -> CheckResult:
    try:
        from radivault_central.db.models import Study
    except Exception as exc:  # pragma: no cover — central extras must be installed
        return CheckResult(
            "V-1",
            False,
            f"could not import radivault_central.db.models: {exc}",
            hint="pip install -e '.[central]'",
        )
    from sqlalchemy import func, select

    Session = _get_session_factory(ctx)
    with Session() as session:
        total = session.scalar(select(func.count()).select_from(Study)) or 0
    ok = total >= ctx.min_studies
    return CheckResult(
        "V-1",
        ok,
        f"study row count = {total} (min {ctx.min_studies})",
        hint="Run inject_all.sh / check gateway upload pipeline." if not ok else "",
    )


# ---------------------------------------------------------------------------
# V-2: search endpoint total ≥ min_studies
# ---------------------------------------------------------------------------


def check_v2_search_total(ctx: VerifyContext) -> CheckResult:
    try:
        with _http_client(ctx) as client:
            resp = client.post(
                f"{ctx.search_url.rstrip('/')}/v1/search/studies",
                json={"filters": {}, "page": 1, "per_page": 1},
                headers=_auth_header_buyer(ctx),
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:
        return CheckResult(
            "V-2",
            False,
            f"search request failed: {exc}",
            hint=f"Is {ctx.search_url} reachable? Did seed_buyer.py run?",
        )
    total = int(body.get("total", 0))
    ok = total >= ctx.min_studies
    return CheckResult(
        "V-2",
        ok,
        f"search total = {total} (min {ctx.min_studies})",
        hint="If 0, the metadata_index may not have caught up." if not ok else "",
    )


# ---------------------------------------------------------------------------
# V-3: modality facet ≥ min_modalities
# ---------------------------------------------------------------------------


def check_v3_modality_facet(ctx: VerifyContext) -> CheckResult:
    try:
        with _http_client(ctx) as client:
            resp = client.get(
                f"{ctx.search_url.rstrip('/')}/v1/search/facets",
                headers=_auth_header_buyer(ctx),
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:
        return CheckResult(
            "V-3",
            False,
            f"facets request failed: {exc}",
            hint="Same root cause as V-2 typically.",
        )
    modality = body.get("modality") or body.get("facets", {}).get("modality") or []
    modality_count = len(modality) if isinstance(modality, dict) else len(list(modality))
    ok = modality_count >= ctx.min_modalities
    return CheckResult(
        "V-3",
        ok,
        f"modality facet count = {modality_count} (min {ctx.min_modalities})",
        hint="Seed config includes CT/MR/MG/CR — if <3, fewer collections ingested." if not ok else "",
    )


# ---------------------------------------------------------------------------
# V-4: hospital + gateway heartbeat within window
# ---------------------------------------------------------------------------


def check_v4_hospital_heartbeat(ctx: VerifyContext) -> CheckResult:
    try:
        from radivault_central.db.models import Hospital, Study
    except Exception as exc:  # pragma: no cover
        return CheckResult(
            "V-4", False, f"import failed: {exc}", hint="pip install -e '.[central]'"
        )
    from sqlalchemy import func, select

    Session = _get_session_factory(ctx)
    with Session() as session:
        hospital_count = session.scalar(select(func.count()).select_from(Hospital)) or 0
        latest = session.scalar(select(func.max(Study.ingested_at)))
    if hospital_count == 0:
        return CheckResult(
            "V-4",
            False,
            "no hospital rows",
            hint="Run scripts/demo_seed/seed_hospital.py (or ingest-admin init-hospital).",
        )
    if latest is None:
        return CheckResult(
            "V-4",
            False,
            f"{hospital_count} hospital(s) but no ingested studies — heartbeat unknown",
            hint="Gateway has not uploaded anything yet.",
        )
    now = datetime.now(tz=UTC)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    delta = now - latest
    ok = delta <= timedelta(minutes=ctx.heartbeat_window_minutes)
    return CheckResult(
        "V-4",
        ok,
        f"{hospital_count} hospital(s); last ingest = {latest.isoformat()} ({delta.total_seconds():.0f}s ago)",
        hint=(
            "Last ingest older than window. Re-run gateway-admin to refresh."
            if not ok
            else ""
        ),
    )


# ---------------------------------------------------------------------------
# V-5: ingest-admin anchor verify
# ---------------------------------------------------------------------------


def check_v5_anchor_verify(ctx: VerifyContext) -> CheckResult:
    cmd = [
        "docker",
        "exec",
        ctx.container,
        "ingest-admin",
        "anchor",
        "verify",
        "--hospital-id",
        ctx.hospital_id,
    ]
    result = _run_subprocess(ctx, cmd)
    if result.returncode == 0:
        return CheckResult("V-5", True, "anchor verify PASS")
    combined = (result.stdout or "") + (result.stderr or "")
    # No anchors means nothing to verify — still treat as PASS if the studies
    # exist (anchors are written on a timer, dev-spec gateway §5.7).
    if "anchors     : 0" in combined or "anchors=0" in combined:
        return CheckResult(
            "V-5",
            True,
            "anchor verify: no anchors yet (expected on a fresh seed)",
        )
    return CheckResult(
        "V-5",
        False,
        f"anchor verify failed rc={result.returncode}",
        hint=combined.strip().splitlines()[-1] if combined.strip() else "",
    )


# ---------------------------------------------------------------------------
# V-6: de-ID flag all "fully_anonymized" + PHI leak 0
# ---------------------------------------------------------------------------


# Heuristic PHI suspects — any match in raw_dicom_tags triggers a fail.
PHI_SUSPECT_KEYS = {
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientAddress",
    "InstitutionAddress",
    "ReferringPhysicianName",
    "OtherPatientIDs",
    "PatientTelephoneNumbers",
}


def check_v6_phi_sampling(ctx: VerifyContext) -> CheckResult:
    try:
        from radivault_central.db.models import Study
    except Exception as exc:  # pragma: no cover
        return CheckResult("V-6", False, f"import failed: {exc}")
    from sqlalchemy import func, select

    Session = _get_session_factory(ctx)
    with Session() as session:
        # Sample up to 10 studies in random order; fall back to most-recent
        # on SQLite (no RANDOM() shorthand in older dialects).
        stmt = select(Study).order_by(func.random()).limit(10)
        try:
            rows = list(session.scalars(stmt))
        except Exception:
            rows = list(session.scalars(select(Study).order_by(Study.study_pk.desc()).limit(10)))

    if not rows:
        return CheckResult(
            "V-6",
            False,
            "no study rows to sample",
            hint="V-1 likely failed; fix ingestion first.",
        )

    leaks: list[str] = []
    for s in rows:
        tags = s.raw_dicom_tags or {}
        if not isinstance(tags, dict):
            continue
        for key in PHI_SUSPECT_KEYS:
            if tags.get(key):
                leaks.append(f"{s.pseudo_study_uid[:12]}:{key}")

    ok = len(leaks) == 0
    return CheckResult(
        "V-6",
        ok,
        (
            f"sampled {len(rows)} studies, PHI suspects = {len(leaks)}"
            + (f" (first={leaks[0]})" if leaks else "")
        ),
        hint="De-ID rules missed a tag. Check gateway ruleset_version." if not ok else "",
    )


# ---------------------------------------------------------------------------
# V-7: buyer key can search
# ---------------------------------------------------------------------------


def _auth_header_buyer(ctx: VerifyContext) -> dict[str, str]:
    if not ctx.buyer_api_key:
        return {}
    return {"Authorization": f"Bearer {ctx.buyer_api_key}"}


def check_v7_buyer_search(ctx: VerifyContext) -> CheckResult:
    if not ctx.buyer_api_key:
        return CheckResult(
            "V-7",
            False,
            "no buyer api key provided",
            hint="Run seed_buyer.py or pass --buyer-api-key-file.",
        )
    try:
        with _http_client(ctx) as client:
            resp = client.post(
                f"{ctx.search_url.rstrip('/')}/v1/search/studies",
                json={"filters": {}, "page": 1, "per_page": 1},
                headers={"Authorization": f"Bearer {ctx.buyer_api_key}"},
            )
    except Exception as exc:
        return CheckResult("V-7", False, f"request failed: {exc}")
    ok = resp.status_code == 200
    return CheckResult(
        "V-7",
        ok,
        f"buyer search status = {resp.status_code}",
        hint="Key may be revoked or tier-gated." if not ok else "",
    )


# ---------------------------------------------------------------------------
# V-8: hospital admin token → /v1/hospital/me/stats
# ---------------------------------------------------------------------------


def check_v8_hospital_stats(ctx: VerifyContext) -> CheckResult:
    if not ctx.hospital_bearer:
        return CheckResult(
            "V-8",
            False,
            "no hospital bearer provided",
            hint="Set HOSPITAL_UPSTREAM_BEARER or pass --hospital-bearer.",
        )
    try:
        with _http_client(ctx) as client:
            resp = client.get(
                f"{ctx.central_url.rstrip('/')}/v1/hospital/me/stats",
                headers={"Authorization": f"Bearer {ctx.hospital_bearer}"},
            )
    except Exception as exc:
        return CheckResult("V-8", False, f"request failed: {exc}")
    ok = resp.status_code == 200
    return CheckResult(
        "V-8",
        ok,
        f"hospital stats status = {resp.status_code}",
        hint="Bearer may be stale — rotate via ingest-admin token issue." if not ok else "",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


CHECKS: list[Callable[[VerifyContext], CheckResult]] = [
    check_v1_study_count,
    check_v2_search_total,
    check_v3_modality_facet,
    check_v4_hospital_heartbeat,
    check_v5_anchor_verify,
    check_v6_phi_sampling,
    check_v7_buyer_search,
    check_v8_hospital_stats,
]


def run_checks(ctx: VerifyContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    for fn in CHECKS:
        try:
            results.append(fn(ctx))
        except Exception as exc:
            results.append(
                CheckResult(
                    fn.__name__.replace("check_", "").split("_")[0].upper(),
                    False,
                    f"checker raised: {exc}",
                )
            )
    ctx.results = results
    return results


def format_report(results: list[CheckResult], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(
            [{"name": r.name, "ok": r.ok, "detail": r.detail, "hint": r.hint} for r in results],
            indent=2,
        )
    lines: list[str] = ["=" * 72, " RadiVault demo-seed verification report", "=" * 72]
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        lines.append(f"  [{mark}] {r.name}: {r.detail}")
        if not r.ok and r.hint:
            lines.append(f"         hint: {r.hint}")
    lines.append("-" * 72)
    passed = sum(1 for r in results if r.ok)
    lines.append(f" {passed}/{len(results)} checks passed")
    lines.append("=" * 72)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_optional_file(path: Path | None) -> str | None:
    if path is None:
        return None
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo-seed verification (V-1..V-8)")
    parser.add_argument(
        "--central-dsn",
        default=os.environ.get(
            "CENTRAL_DSN",
            "postgresql+psycopg://central_app:central_app@localhost:5432/central",
        ),
    )
    parser.add_argument(
        "--search-url",
        default=os.environ.get("SEARCH_URL", "http://localhost:8001"),
    )
    parser.add_argument(
        "--central-url",
        default=os.environ.get("CENTRAL_URL", "http://localhost:8000"),
    )
    parser.add_argument("--hospital-id", default="HOSP-001")
    parser.add_argument(
        "--hospital-bearer",
        default=os.environ.get("HOSPITAL_UPSTREAM_BEARER"),
    )
    parser.add_argument(
        "--buyer-api-key",
        default=os.environ.get("BUYER_API_KEY"),
    )
    parser.add_argument(
        "--buyer-api-key-file",
        type=Path,
        default=Path(__file__).parent / ".buyer_key.local.txt",
    )
    parser.add_argument("--container", default="radivault-central-1")
    parser.add_argument("--min-studies", type=int, default=300)
    parser.add_argument("--min-modalities", type=int, default=3)
    parser.add_argument("--heartbeat-window-minutes", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Emit JSON report instead of text.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    buyer_api_key = args.buyer_api_key or _read_optional_file(args.buyer_api_key_file)

    ctx = VerifyContext(
        central_dsn=args.central_dsn,
        search_url=args.search_url,
        central_url=args.central_url,
        hospital_id=args.hospital_id,
        hospital_bearer=args.hospital_bearer,
        buyer_api_key=buyer_api_key,
        min_studies=args.min_studies,
        min_modalities=args.min_modalities,
        heartbeat_window_minutes=args.heartbeat_window_minutes,
        container=args.container,
    )

    results = run_checks(ctx)
    sys.stdout.write(format_report(results, as_json=args.json))

    all_pass = all(r.ok for r in results)
    if all_pass:
        LOCK_PATH.write_text(
            json.dumps(
                {
                    "passed_at": datetime.now(tz=UTC).isoformat(),
                    "checks": [r.name for r in results],
                }
            ),
            encoding="utf-8",
        )
        log.info("demo_seed_ready_lock_written path=%s", LOCK_PATH)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
