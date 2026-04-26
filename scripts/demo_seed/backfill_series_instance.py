"""Backfill series + instance rows for already-ingested studies.

dev-spec-backfill-series-instance §FR-1..FR-18: D-13 demo unblocker.

The first-pass ingest path (Flow A metadata-only) wrote the parent ``study``
row but never populated the child ``series`` / ``instance`` tables, so Buyer
Portal study-detail pages currently render "Series Count: 0", "Sample DICOM
disabled", "Preview unavailable" for every study.

This script walks Orthanc per study, resolves pseudo UIDs through the
gateway ``state.sqlite3`` ``uid_map``, and INSERTs the missing rows in an
idempotent fashion. It also UPDATEs ``study.n_series`` /
``study.n_instances`` / ``study.total_bytes`` / ``study.sample_instance_uid``
so the portal counters reconcile.

Inputs:
- Orthanc HTTP API for raw DICOM bytes + tags.
- Gateway ``state.sqlite3`` ``uid_map`` for original_uid → pseudo_uid
  (study/series/sop). Per Kyle K-1 옵션 A, on miss we apply the byte-for-byte
  identical SHA256 fallback algorithm from
  ``src/radivault_gateway/deid/engine.py:DeidEngine.pseudo_uid`` and persist
  the freshly computed mapping back to ``state_db.uid_map`` so subsequent
  re-runs hit the cache. Salt + org_root are loaded from
  ``configs/demo_gateway.yaml`` via ``--gateway-config``.
- Central Postgres for the INSERT/UPDATE.

Idempotent: re-running on the same pseudo_study_uid SELECTs first and
SKIPs existing series/instance rows.

# DEMO-ONLY: do not run in production. Per Kyle K-4, no env guard is
# wired in (demo workstation only).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger("backfill.series_instance")

DEFAULT_ORTHANC = "http://localhost:8042"
DEFAULT_ORTHANC_USER = "orthanc"
DEFAULT_ORTHANC_PASS = "orthanc"
DEFAULT_DB_DSN = (
    "postgresql+psycopg://central_app:central_app@localhost:5432/central"
)
DEFAULT_STATE_DB = "/Users/yonghyuk/Radivault/demo_data/gateway/state.sqlite3"
DEFAULT_GATEWAY_CONFIG = "/Users/yonghyuk/Radivault/configs/demo_gateway.yaml"


# ---------------------------------------------------------------------------
# Gateway config loader (FR-5 fallback prerequisites: salt + org_root).
# ---------------------------------------------------------------------------


def _load_gateway_secrets(path: str) -> tuple[bytes, str, int]:
    """Load (salt_bytes, org_root_oid, salt_version) from gateway YAML config.

    Mirrors the way ``DeidEngine.__init__`` consumes config — salt is treated
    as a UTF-8 string and ``.encode('utf-8')``ed, NOT decoded from hex. This
    is critical for byte-equivalence with engine.py:321.
    """
    import yaml  # PyYAML — already in env (gateway uses it)

    if not Path(path).exists():
        raise FileNotFoundError(f"gateway config not found at {path}")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    deid = cfg.get("deid") or {}
    agent = cfg.get("agent") or {}
    salt = deid.get("salt")
    salt_version = deid.get("salt_version")
    org_root = agent.get("org_root_oid")
    if not salt or not org_root or salt_version is None:
        raise ValueError(
            f"gateway config {path} missing deid.salt / deid.salt_version / "
            "agent.org_root_oid"
        )
    return salt.encode("utf-8"), str(org_root), int(salt_version)


def _fallback_pseudo_uid(
    original_uid: str, *, salt_bytes: bytes, org_root: str
) -> str:
    """Recompute pseudo UID identically to gateway DeidEngine.pseudo_uid.

    Source of truth: ``src/radivault_gateway/deid/engine.py:310-329``. Any
    drift here breaks search/portal cross-references because gateway-issued
    UIDs and backfill-issued UIDs would diverge.
    """
    digest = hashlib.sha256(
        salt_bytes + str(original_uid).encode("utf-8")
    ).digest()
    suffix = str(int.from_bytes(digest[:5], "big"))
    pseudo = f"{org_root}.{suffix}"
    if len(pseudo) > 64:
        pseudo = pseudo[:64]
    return pseudo


def _fallback_self_test(
    state_conn: sqlite3.Connection,
    *,
    salt_bytes: bytes,
    org_root: str,
) -> None:
    """Verify fallback algorithm matches an existing uid_map entry.

    Picks one known mapping (for each kind that has data) from the gateway
    state DB and recomputes the pseudo UID using the fallback algorithm —
    on mismatch we abort BEFORE touching central DB to avoid poisoning the
    cross-reference graph (R-1 in dev-spec §12).
    """
    rows = state_conn.execute(
        "SELECT original_uid, pseudo_uid, uid_kind FROM uid_map "
        "WHERE uid_kind IN ('study','series','sop') "
        "GROUP BY uid_kind"
    ).fetchall()
    if not rows:
        raise RuntimeError(
            "fallback self-test: state_db.uid_map is empty — refusing to run"
        )
    for row in rows:
        computed = _fallback_pseudo_uid(
            row["original_uid"], salt_bytes=salt_bytes, org_root=org_root
        )
        if computed != row["pseudo_uid"]:
            raise RuntimeError(
                "fallback self-test FAILED for kind="
                f"{row['uid_kind']}: salt/org_root mismatch with gateway. "
                f"original={row['original_uid'][:40]!r} "
                f"expected={row['pseudo_uid']!r} computed={computed!r}"
            )
        log.info(
            "fallback_self_test OK kind=%s expected=%s",
            row["uid_kind"],
            row["pseudo_uid"],
        )


# ---------------------------------------------------------------------------
# Orthanc helpers (lifted from backfill_v2_metadata.py — same auth/timeout).
# ---------------------------------------------------------------------------


def _orthanc_get_json(args, path: str) -> object:
    import requests

    r = requests.get(
        f"{args.orthanc}{path}",
        auth=(args.orthanc_user, args.orthanc_password),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _orthanc_get_bytes(args, path: str) -> bytes:
    import requests

    r = requests.get(
        f"{args.orthanc}{path}",
        auth=(args.orthanc_user, args.orthanc_password),
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _list_orthanc_studies(args) -> list[str]:
    return _orthanc_get_json(args, "/studies")


# ---------------------------------------------------------------------------
# state_db helpers (sqlite3, read-only logically).
# ---------------------------------------------------------------------------


def _connect_state_db(path: str) -> sqlite3.Connection:
    if not Path(path).exists():
        raise FileNotFoundError(f"gateway state DB not found at {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_pseudo_uid(
    state_conn: sqlite3.Connection,
    original_uid: str,
    kind: str,
    *,
    salt_bytes: bytes | None = None,
    org_root: str | None = None,
    salt_version: int | None = None,
    fallback_counter: dict[str, int] | None = None,
) -> str | None:
    """Look up pseudo_uid from gateway state_db with fallback hash.

    Lookup order:
      1) state_db.uid_map (gateway-issued mapping). Authoritative when
         present.
      2) If salt_bytes/org_root are provided and the row is missing, compute
         the pseudo UID via the same SHA256 algorithm DeidEngine uses, persist
         it back to uid_map (so subsequent runs short-circuit), and return.
      3) When fallback args are absent and the row is missing, return None
         (caller decides SKIP semantics — preserves the original behaviour).
    """
    row = state_conn.execute(
        "SELECT pseudo_uid FROM uid_map WHERE original_uid = ? AND uid_kind = ?",
        (original_uid, kind),
    ).fetchone()
    if row:
        return row["pseudo_uid"]
    if salt_bytes is None or org_root is None or salt_version is None:
        return None
    pseudo = _fallback_pseudo_uid(
        original_uid, salt_bytes=salt_bytes, org_root=org_root
    )
    # Persist back so re-runs hit the cache (uses INSERT OR IGNORE semantics
    # to be safe under any concurrent gateway writer).
    try:
        state_conn.execute(
            "INSERT OR IGNORE INTO uid_map "
            "(original_uid, pseudo_uid, uid_kind, salt_version, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (original_uid, pseudo, kind, salt_version),
        )
        state_conn.commit()
    except sqlite3.IntegrityError as exc:
        # Pseudo UID collision against a different original_uid would be a
        # gateway-level invariant violation — surface loudly.
        log.error(
            "fallback uid_map insert failed kind=%s original=%s pseudo=%s: %s",
            kind,
            original_uid[:40],
            pseudo,
            exc,
        )
        raise
    if fallback_counter is not None:
        fallback_counter[kind] = fallback_counter.get(kind, 0) + 1
    log.debug(
        "pseudo_uid_fallback kind=%s original=%s pseudo=%s",
        kind,
        original_uid[:40],
        pseudo,
    )
    return pseudo


# ---------------------------------------------------------------------------
# DB session.
# ---------------------------------------------------------------------------


def _make_session(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(dsn)
    return sessionmaker(bind=engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Per-instance fetch + sha256/sop_class_uid extraction.
# ---------------------------------------------------------------------------


def _fetch_instance_payload(
    args, orthanc_instance_id: str, *, file_size_hint: int | None
) -> tuple[int, bytes, str | None]:
    """Download DICOM bytes (memory only — never disk per §14 PHI rule).

    Returns (bytes_len, sha256_digest_32b, sop_class_uid).

    SOPClassUID is parsed from the in-memory DICOM payload using pydicom
    (``stop_before_pixels=True`` so the pixel array is never decoded). This
    avoids one extra HTTP roundtrip per instance vs ``/tags?simplify``.
    """
    import pydicom

    raw = _orthanc_get_bytes(args, f"/instances/{orthanc_instance_id}/file")
    sha = hashlib.sha256(raw).digest()
    n_bytes = file_size_hint if file_size_hint is not None else len(raw)
    sop_class_uid: str | None = None
    try:
        ds = pydicom.dcmread(
            io.BytesIO(raw), stop_before_pixels=True, force=True
        )
        v = ds.get("SOPClassUID")
        if v is not None:
            sop_class_uid = str(v)
    except Exception as exc:  # noqa: BLE001
        log.debug(
            "pydicom parse failed for %s (sop_class_uid=NULL): %s",
            orthanc_instance_id,
            exc,
        )
    return n_bytes, sha, sop_class_uid


# ---------------------------------------------------------------------------
# Parsing helpers.
# ---------------------------------------------------------------------------


def _maybe_int(v: object) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Main per-study worker.
# ---------------------------------------------------------------------------


def process_one(
    args,
    *,
    state_conn: sqlite3.Connection,
    session_factory,
    orthanc_study_id: str,
    salt_bytes: bytes,
    org_root: str,
    salt_version: int,
    fallback_counter: dict[str, int],
) -> tuple[bool, str]:
    """Backfill series + instance rows + study counters for one Orthanc study."""
    from sqlalchemy import select

    from radivault_central.db.models import Instance, Series, Study

    # 1. Resolve pseudo_study_uid (FR-2). Study-kind mappings are 100% present
    # per Kyle K-1 audit, but we still pass fallback args defensively so a
    # late-discovered Orthanc study with no uid_map row is handled deterministically.
    study_meta = _orthanc_get_json(args, f"/studies/{orthanc_study_id}")
    main_tags = study_meta.get("MainDicomTags", {}) or {}
    original_study_uid = main_tags.get("StudyInstanceUID") or ""
    if not original_study_uid:
        return False, f"orthanc study {orthanc_study_id} missing StudyInstanceUID"

    pseudo_study_uid = _resolve_pseudo_uid(
        state_conn,
        original_study_uid,
        "study",
        salt_bytes=salt_bytes,
        org_root=org_root,
        salt_version=salt_version,
        fallback_counter=fallback_counter,
    )
    if not pseudo_study_uid:
        return False, f"no uid_map entry for study {original_study_uid[:40]}"

    # 2. Series enumerate (FR-4).
    orthanc_series = _orthanc_get_json(
        args, f"/studies/{orthanc_study_id}/series"
    )
    if not orthanc_series:
        return False, f"no series for {pseudo_study_uid[:30]}"

    # ------------------------------------------------------------------
    # Pre-fetch instance lists + DICOM payloads BEFORE opening the DB
    # transaction, so a long Orthanc download window doesn't hold a DB
    # transaction open. We collect a fully-resolved per-study plan, then
    # commit the whole study atomically.
    # ------------------------------------------------------------------

    series_plans: list[dict] = []  # list of dicts ready for INSERT
    sample_pseudo_sop_uid: str | None = None  # FR-13
    total_bytes_accum = 0

    for raw_series in orthanc_series:
        series_main = raw_series.get("MainDicomTags", {}) or {}
        original_series_uid = series_main.get("SeriesInstanceUID") or ""
        if not original_series_uid:
            log.warning(
                "skipping series with no SeriesInstanceUID under %s",
                pseudo_study_uid[:30],
            )
            continue
        pseudo_series_uid = _resolve_pseudo_uid(
            state_conn,
            original_series_uid,
            "series",
            salt_bytes=salt_bytes,
            org_root=org_root,
            salt_version=salt_version,
            fallback_counter=fallback_counter,
        )
        if not pseudo_series_uid:
            return (
                False,
                f"no uid_map entry for series {original_series_uid[:40]} "
                f"(study {pseudo_study_uid[:30]})",
            )

        orthanc_series_id = raw_series.get("ID")
        instance_meta_list = _orthanc_get_json(
            args, f"/series/{orthanc_series_id}/instances"
        )
        # FR-7: sort by InstanceNumber asc so middle picker is deterministic.
        def _sort_key(item):
            return _maybe_int(
                (item.get("MainDicomTags") or {}).get("InstanceNumber")
            ) or 0

        instance_meta_list = sorted(instance_meta_list, key=_sort_key)

        # Pre-resolve pseudo UIDs (sequential, sqlite3 is not thread-safe).
        # Build a list of (inst_meta, pseudo_sop_uid) pairs, then fan out the
        # HTTP downloads in parallel — the dominant cost is roundtrip latency
        # to localhost Orthanc (~80ms/instance), so even a small thread pool
        # yields a 5-8x speedup on multi-hundred-instance series.
        resolved: list[tuple[dict, str]] = []
        for inst_meta in instance_meta_list:
            inst_main = inst_meta.get("MainDicomTags", {}) or {}
            original_sop_uid = inst_main.get("SOPInstanceUID") or ""
            if not original_sop_uid:
                log.warning(
                    "skipping instance with no SOPInstanceUID under series %s",
                    pseudo_series_uid[:30],
                )
                continue
            pseudo_sop_uid = _resolve_pseudo_uid(
                state_conn,
                original_sop_uid,
                "sop",
                salt_bytes=salt_bytes,
                org_root=org_root,
                salt_version=salt_version,
                fallback_counter=fallback_counter,
            )
            if not pseudo_sop_uid:
                return (
                    False,
                    f"no uid_map entry for sop {original_sop_uid[:40]} "
                    f"(study {pseudo_study_uid[:30]})",
                )
            resolved.append((inst_meta, pseudo_sop_uid))

        # Parallel Orthanc download + sha256 (network/IO-bound → threads OK).
        def _do_fetch(item):
            inst_meta, _pseudo_sop_uid = item
            orthanc_instance_id = str(inst_meta.get("ID"))
            file_size_hint = inst_meta.get("FileSize")
            n_bytes, sha, sop_class_uid = _fetch_instance_payload(
                args, orthanc_instance_id, file_size_hint=file_size_hint
            )
            return n_bytes, sha, sop_class_uid

        instance_plans: list[dict] = []
        if args.workers > 1 and len(resolved) > 1:
            with ThreadPoolExecutor(
                max_workers=args.workers,
                thread_name_prefix="backfill-fetch",
            ) as pool:
                results = list(pool.map(_do_fetch, resolved))
        else:
            results = [_do_fetch(item) for item in resolved]

        for (inst_meta, pseudo_sop_uid), (n_bytes, sha, sop_class_uid) in zip(
            resolved, results
        ):
            inst_main = inst_meta.get("MainDicomTags", {}) or {}
            orthanc_instance_id = inst_meta.get("ID")
            instance_plans.append(
                {
                    "pseudo_sop_uid": pseudo_sop_uid,
                    "sop_class_uid": sop_class_uid,
                    "instance_number": _maybe_int(inst_main.get("InstanceNumber")),
                    "object_key": f"orthanc:{orthanc_instance_id}",
                    "bytes": n_bytes,
                    "sha256": sha,
                }
            )
            total_bytes_accum += n_bytes

        if not instance_plans:
            log.warning(
                "no instances resolved for series %s under %s — skipping series",
                pseudo_series_uid[:30],
                pseudo_study_uid[:30],
            )
            continue

        series_plans.append(
            {
                "pseudo_series_uid": pseudo_series_uid,
                "modality": series_main.get("Modality"),
                "body_part": series_main.get("BodyPartExamined"),
                "series_number": _maybe_int(series_main.get("SeriesNumber")),
                "n_instances": len(instance_plans),
                "instances": instance_plans,
            }
        )

    if not series_plans:
        return False, f"no resolvable series for {pseudo_study_uid[:30]}"

    # 3. FR-13: sample = first series (by series_number asc, NULL last) →
    #          middle instance's pseudo_sop_uid.
    def _series_sort(p):
        sn = p["series_number"]
        return (sn is None, sn if sn is not None else 0)

    first_series = sorted(series_plans, key=_series_sort)[0]
    mid_idx = len(first_series["instances"]) // 2
    sample_pseudo_sop_uid = first_series["instances"][mid_idx]["pseudo_sop_uid"]

    # ------------------------------------------------------------------
    # 4. Dry-run: report and bail before touching the DB.
    # ------------------------------------------------------------------
    if args.dry_run:
        n_instances_total = sum(p["n_instances"] for p in series_plans)
        log.info(
            "DRY pseudo=%s would insert series=%d instances=%d total_bytes=%d sample=%s",
            pseudo_study_uid[:30],
            len(series_plans),
            n_instances_total,
            total_bytes_accum,
            sample_pseudo_sop_uid[:30],
        )
        return True, (
            f"DRY pseudo={pseudo_study_uid[:30]} "
            f"series={len(series_plans)} instances={n_instances_total}"
        )

    # ------------------------------------------------------------------
    # 5. Single per-study DB transaction (FR-14).
    # ------------------------------------------------------------------
    inserted_series = 0
    inserted_instances = 0
    skipped_series = 0
    skipped_instances = 0

    with session_factory() as session:
        study = session.scalar(
            select(Study).where(Study.pseudo_study_uid == pseudo_study_uid)
        )
        if study is None:
            return False, f"central row missing for {pseudo_study_uid[:30]}"

        for sp in series_plans:
            existing_series = session.scalar(
                select(Series).where(
                    Series.pseudo_series_uid == sp["pseudo_series_uid"]
                )
            )
            if existing_series is not None:
                series_pk = existing_series.series_pk
                # Idempotent: refresh n_instances if this study truly owns
                # this series. (Different study_pk → leave alone, but log.)
                if existing_series.study_pk != study.study_pk:
                    log.warning(
                        "series %s already owned by study_pk=%d (current=%d) — leaving",
                        sp["pseudo_series_uid"][:30],
                        existing_series.study_pk,
                        study.study_pk,
                    )
                else:
                    existing_series.n_instances = sp["n_instances"]
                skipped_series += 1
            else:
                series_row = Series(
                    study_pk=study.study_pk,
                    pseudo_series_uid=sp["pseudo_series_uid"],
                    modality=sp["modality"],
                    body_part=sp["body_part"],
                    series_number=sp["series_number"],
                    n_instances=sp["n_instances"],
                )
                session.add(series_row)
                session.flush()
                series_pk = series_row.series_pk
                inserted_series += 1

            for ip in sp["instances"]:
                existing_inst = session.scalar(
                    select(Instance.instance_pk).where(
                        Instance.pseudo_sop_uid == ip["pseudo_sop_uid"]
                    )
                )
                if existing_inst is not None:
                    skipped_instances += 1
                    continue
                session.add(
                    Instance(
                        series_pk=series_pk,
                        pseudo_sop_uid=ip["pseudo_sop_uid"],
                        sop_class_uid=ip["sop_class_uid"],
                        instance_number=ip["instance_number"],
                        object_key=ip["object_key"],
                        bytes=ip["bytes"],
                        sha256=ip["sha256"],
                    )
                )
                inserted_instances += 1

        # FR-12: recompute counters from authoritative DB state (handles
        # the case where some series rows pre-existed). FR-13 sample.
        from sqlalchemy import func as sa_func

        n_series_actual = session.scalar(
            select(sa_func.count(Series.series_pk)).where(
                Series.study_pk == study.study_pk
            )
        ) or 0
        n_instances_actual = session.scalar(
            select(sa_func.count(Instance.instance_pk))
            .select_from(Instance)
            .join(Series, Instance.series_pk == Series.series_pk)
            .where(Series.study_pk == study.study_pk)
        ) or 0
        total_bytes_actual = session.scalar(
            select(sa_func.coalesce(sa_func.sum(Instance.bytes), 0))
            .select_from(Instance)
            .join(Series, Instance.series_pk == Series.series_pk)
            .where(Series.study_pk == study.study_pk)
        ) or 0

        study.n_series = int(n_series_actual)
        study.n_instances = int(n_instances_actual)
        study.total_bytes = int(total_bytes_actual)
        study.sample_instance_uid = sample_pseudo_sop_uid

        # AC-12: append trace tag without clobbering existing
        # backfilled_by from backfill_v2_metadata.py.
        existing_tags = dict(study.raw_dicom_tags or {})
        existing_tags["series_instance_backfilled_by"] = (
            "backfill_series_instance.py"
        )
        study.raw_dicom_tags = existing_tags

        session.commit()

    return True, (
        f"OK pseudo={pseudo_study_uid[:30]} series={len(series_plans)} "
        f"(new={inserted_series},skip={skipped_series}) "
        f"instances={sum(p['n_instances'] for p in series_plans)} "
        f"(new={inserted_instances},skip={skipped_instances}) "
        f"sample={sample_pseudo_sop_uid[:30]}"
    )


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill series + instance rows from Orthanc "
        "(dev-spec-backfill-series-instance)"
    )
    parser.add_argument("--orthanc", default=DEFAULT_ORTHANC)
    parser.add_argument("--orthanc-user", default=DEFAULT_ORTHANC_USER)
    parser.add_argument("--orthanc-password", default=DEFAULT_ORTHANC_PASS)
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--state-db", default=DEFAULT_STATE_DB)
    parser.add_argument(
        "--gateway-config",
        default=DEFAULT_GATEWAY_CONFIG,
        help="Path to gateway YAML config; supplies deid.salt + "
        "deid.salt_version + agent.org_root_oid for the fallback hash "
        "(K-1 옵션 A). Required because most series/sop UIDs are absent "
        "from state_db.uid_map under Flow A metadata-only ingest.",
    )
    # FR-16 compatibility: accept (and ignore) the --bucket arg so operators
    # can copy/paste their backfill_v2_metadata.py invocation.
    parser.add_argument("--bucket", default=None, help="(unused; compat only)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent Orthanc /instances/{id}/file fetches per series "
        "(default 8; set 1 to disable parallelism).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info(
        "backfill_start orthanc=%s state_db=%s dry_run=%s",
        args.orthanc,
        args.state_db,
        args.dry_run,
    )

    state_conn = _connect_state_db(args.state_db)
    session_factory = _make_session(args.db_dsn)

    # Load gateway secrets and run the self-test BEFORE we touch central DB —
    # mismatched salt/org_root would silently poison search/portal cross-refs
    # (R-1 in dev-spec §12). Self-test compares fallback output against a
    # known gateway-issued mapping.
    salt_bytes, org_root, salt_version = _load_gateway_secrets(args.gateway_config)
    log.info(
        "gateway_secrets_loaded org_root=%s salt_version=%d salt_len=%d",
        org_root,
        salt_version,
        len(salt_bytes),
    )
    _fallback_self_test(
        state_conn, salt_bytes=salt_bytes, org_root=org_root
    )

    try:
        studies = _list_orthanc_studies(args)
    except Exception as exc:  # noqa: BLE001
        log.error("orthanc list failed: %s", exc)
        return 2

    if args.limit:
        studies = studies[: args.limit]
    log.info("backfill_targets count=%d", len(studies))

    successes = 0
    failures = 0
    fail_reasons: dict[str, int] = {}
    fallback_counter: dict[str, int] = {}
    started = time.time()

    for i, oid in enumerate(studies, 1):
        try:
            ok, detail = process_one(
                args,
                state_conn=state_conn,
                session_factory=session_factory,
                orthanc_study_id=oid,
                salt_bytes=salt_bytes,
                org_root=org_root,
                salt_version=salt_version,
                fallback_counter=fallback_counter,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("study failed %s", oid)
            ok, detail = False, f"exception: {exc}"

        if ok:
            successes += 1
            log.info("[%d/%d] %s", i, len(studies), detail)
        else:
            failures += 1
            key = detail.split(":", 1)[0][:32]
            fail_reasons[key] = fail_reasons.get(key, 0) + 1
            log.warning("[%d/%d] FAIL %s", i, len(studies), detail)

    duration = time.time() - started
    log.info(
        "backfill_summary ok=%d fail=%d duration_s=%.1f",
        successes,
        failures,
        duration,
    )
    if fallback_counter:
        log.info("backfill_fallback_counts %s", fallback_counter)
    if fail_reasons:
        log.info("backfill_fail_reasons %s", fail_reasons)
    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
