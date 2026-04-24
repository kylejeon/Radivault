"""TCIA demo data downloader (dev-spec buyer-portal-demo §8.2).

Idempotent: each study directory is marked with ``_done.marker`` after
completion so reruns skip already-fetched data. Failed studies are
appended to ``_failed.json`` for manual retry.

Scope
-----
This script targets small TCIA subsets (total ~400 studies per
``seed_config.yaml``) and uses ``tcia_utils`` (PyPI) for the NBIA REST
calls. The ``--dry-run`` / ``--plan-only`` paths never hit the network
and are exercised in CI. The real fetch is exercised by the demo
operator (Kyle) during rehearsal R-1 — a one-shot ~30-minute run that
populates ``demo_data/cache/``.

License compliance
------------------
The script skips any collection with ``license: RESTRICTED`` unless the
operator passes ``--accept-restricted``. This is the automation side of
the manual Kyle-confirmation gate (L-1..L-3 / FR-S-1).

FR mapping (dev-spec buyer-portal-demo §8):
* FR-S-1..S-3  — CC-BY default, RESTRICTED gate, local cache
* FR-S-4       — tcia_utils library path
* FR-S-5       — cache layout ``{cache_dir}/{collection}/{study_uid}/*.dcm``
* FR-S-6       — idempotent, SHA-256 manifest
* FR-S-7       — exponential backoff retries, ``_failed.json``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

log = logging.getLogger("demo_seed.download")

# ---------------------------------------------------------------------------
# Retry + fetch tuning (dev-spec FR-S-7)
# ---------------------------------------------------------------------------

DEFAULT_RETRIES = 3  # per-study attempt count
RETRY_BASE_SECONDS = 2.0  # exponential: 2s, 4s, 8s ...
RETRY_JITTER_SECONDS = 1.0  # up to +1s jitter each sleep

# Arbitrary but non-zero — we don't need the full series list, only enough
# to fill ``target_count`` studies. Over-fetching metadata is cheap compared
# to DICOM bytes.
PATIENTS_MULTIPLIER = 3


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class Collection:
    name: str
    modality: str
    body_part: str
    target_count: int
    license: str


def load_config(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. `pip install pyyaml`.")
    if not path.exists():
        # AC-S-6 — bilingual error. Stream stderr so shells / CI can grep.
        sys.stderr.write(
            "[ERR_SEED_CONFIG_MISSING] config not found / 설정 파일을 찾을 수 없습니다: "
            f"{path}\n"
        )
        log.error("config_missing path=%s", path)
        raise SystemExit(2)
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def parse_collections(cfg: dict) -> list[Collection]:
    out: list[Collection] = []
    for entry in cfg.get("collections", []):
        out.append(
            Collection(
                name=entry["name"],
                modality=entry["modality"],
                body_part=entry.get("body_part", ""),
                target_count=int(entry["target_count"]),
                license=entry.get("license", "UNKNOWN"),
            )
        )
    return out


def plan(collections: list[Collection], cache_dir: Path) -> list[dict]:
    """Produce a dry-run plan describing what would be fetched."""
    plan_entries: list[dict] = []
    for c in collections:
        plan_entries.append(
            {
                "collection": c.name,
                "target_count": c.target_count,
                "cache_path": str(cache_dir / c.name),
                "license": c.license,
            }
        )
    return plan_entries


# ---------------------------------------------------------------------------
# Manifest + marker helpers
# ---------------------------------------------------------------------------


def _write_manifest(study_dir: Path, files: list[Path]) -> str:
    """Produce SHA-256 of file bytes + names and write ``_manifest.sha256``.

    The manifest hashes (filename || bytes) for each file in sorted order so
    the same file set always yields the same hash. Returns the hex digest so
    callers can log / verify.
    """
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.name.encode("utf-8"))
        h.update(f.read_bytes())
    digest = h.hexdigest()
    (study_dir / "_manifest.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def _mark_done(study_dir: Path, files: list[Path]) -> None:
    _write_manifest(study_dir, files)
    (study_dir / "_done.marker").touch()


def _record_failure(cache_dir: Path, entry: dict[str, Any]) -> None:
    """Append a failure entry to ``_failed.json`` (FR-S-7)."""
    failed_path = cache_dir / "_failed.json"
    existing: list[dict[str, Any]] = []
    if failed_path.exists():
        try:
            existing = json.loads(failed_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing.append(entry)
    failed_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# tcia_utils adapter (injectable for tests)
# ---------------------------------------------------------------------------


class TCIAClient:
    """Thin wrapper around ``tcia_utils.nbia``.

    Kept as a class so tests can pass a stub without patching ``sys.modules``.
    The real ``tcia_utils`` import is lazy so importing this script works
    even when the package isn't installed (CI / dry-run path).
    """

    def __init__(self) -> None:
        self._nbia: Any | None = None

    def _load(self) -> Any:
        if self._nbia is None:
            from tcia_utils import nbia  # type: ignore[import-untyped]

            self._nbia = nbia
        return self._nbia

    def list_patients(self, collection: str) -> list[dict]:
        nbia = self._load()
        result = nbia.getPatient(collection=collection)
        if result is None:
            return []
        # nbia.getPatient returns JSON list in v3+.
        if hasattr(result, "to_dict"):
            return result.to_dict("records")  # DataFrame path
        return list(result)

    def list_studies(self, collection: str, patient_id: str) -> list[dict]:
        nbia = self._load()
        result = nbia.getStudy(collection=collection, patientId=patient_id)
        if result is None:
            return []
        if hasattr(result, "to_dict"):
            return result.to_dict("records")
        return list(result)

    def list_series(self, study_uid: str) -> list[dict]:
        nbia = self._load()
        result = nbia.getSeries(studyUid=study_uid)
        if result is None:
            return []
        if hasattr(result, "to_dict"):
            return result.to_dict("records")
        return list(result)

    def download_series(self, series_uids: list[str], dest: Path) -> None:
        nbia = self._load()
        dest.mkdir(parents=True, exist_ok=True)
        nbia.downloadSeries(
            series_data=series_uids,
            input_type="list",
            path=str(dest),
            as_zip=False,
        )


# ---------------------------------------------------------------------------
# Retry helper (FR-S-7)
# ---------------------------------------------------------------------------


def _retry_call(
    fn, *args, retries: int = DEFAULT_RETRIES, label: str = "op", **kwargs
) -> Any:
    """Exponential-backoff retry. Re-raises the last exception on failure."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == retries:
                break
            sleep_for = (RETRY_BASE_SECONDS * (2 ** (attempt - 1))) + random.random() * RETRY_JITTER_SECONDS
            log.warning(
                "retry label=%s attempt=%d/%d sleep=%.1fs err=%s",
                label,
                attempt,
                retries,
                sleep_for,
                exc,
            )
            time.sleep(sleep_for)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Validation (header-only pydicom check, FR-S-4)
# ---------------------------------------------------------------------------


def _validate_dicom_headers(study_dir: Path) -> int:
    """Open each .dcm header-only. Returns count of valid files. Raises on zero."""
    import pydicom  # local import — optional dep path

    dcms = sorted(study_dir.rglob("*.dcm"))
    if not dcms:
        raise RuntimeError(f"no DICOM files downloaded to {study_dir}")
    ok = 0
    for f in dcms:
        try:
            pydicom.dcmread(str(f), stop_before_pixels=True)
            ok += 1
        except Exception as exc:
            log.warning("dicom_header_invalid path=%s err=%s", f, exc)
    if ok == 0:
        raise RuntimeError(f"all DICOM headers invalid under {study_dir}")
    return ok


# ---------------------------------------------------------------------------
# Study-level download
# ---------------------------------------------------------------------------


def download_study(
    collection: Collection,
    patient_id: str,
    study_uid: str,
    cache_dir: Path,
    *,
    dry_run: bool,
    client: TCIAClient | None = None,
    retries: int = DEFAULT_RETRIES,
) -> str:
    """Download a single study. Returns 'skip' | 'done' | 'fail'.

    Idempotent: if ``_done.marker`` exists, returns ``skip`` without touching
    the network. ``dry_run`` only writes a ``_plan.txt`` placeholder.
    """
    target = cache_dir / collection.name / study_uid
    if (target / "_done.marker").exists():
        return "skip"
    target.mkdir(parents=True, exist_ok=True)
    try:
        if dry_run:
            (target / "_plan.txt").write_text(
                f"Would download collection={collection.name}\n"
                f"patient_id={patient_id} study_uid={study_uid}\n",
                encoding="utf-8",
            )
            return "done"

        tc = client or TCIAClient()
        # 1) Resolve series UIDs for this study.
        series_rows = _retry_call(
            tc.list_series,
            study_uid,
            retries=retries,
            label=f"list_series:{collection.name}",
        )
        series_uids = [
            r.get("SeriesInstanceUID") or r.get("seriesInstanceUID")
            for r in series_rows
            if r.get("SeriesInstanceUID") or r.get("seriesInstanceUID")
        ]
        if not series_uids:
            raise RuntimeError(f"no series under study {study_uid}")

        # 2) Download series DICOMs into a per-study directory.
        _retry_call(
            tc.download_series,
            series_uids,
            target,
            retries=retries,
            label=f"download_series:{collection.name}",
        )

        # 3) Validate headers (pydicom, stop_before_pixels).
        dcm_files = sorted(target.rglob("*.dcm"))
        _validate_dicom_headers(target)

        # 4) Write manifest + done marker (FR-S-6).
        _mark_done(target, dcm_files)
        return "done"
    except Exception as exc:
        (target / "_error.json").write_text(
            json.dumps({"error": str(exc), "study_uid": study_uid}, indent=2),
            encoding="utf-8",
        )
        log.error(
            "study_failed collection=%s study_uid=%s err=%s",
            collection.name,
            study_uid,
            exc,
        )
        _record_failure(
            cache_dir,
            {
                "collection": collection.name,
                "patient_id": patient_id,
                "study_uid": study_uid,
                "error": str(exc),
                "ts": time.time(),
            },
        )
        return "fail"


# ---------------------------------------------------------------------------
# Collection-level orchestration (FR-S-4 / FR-S-5)
# ---------------------------------------------------------------------------


def _iter_study_targets(
    collection: Collection,
    client: TCIAClient,
    *,
    dry_run: bool,
) -> list[tuple[str, str]]:
    """Return up to ``target_count`` (patient_id, study_uid) pairs.

    In dry_run mode we synthesize deterministic placeholders to keep the
    CI path hermetic. In real mode we ask TCIA for patients / studies.
    """
    if dry_run:
        return [
            (f"{collection.name[:6]}-P-{i:05d}", f"2.25.demo.{collection.name}.{i}")
            for i in range(collection.target_count)
        ]

    patients = _retry_call(
        client.list_patients, collection.name, label=f"list_patients:{collection.name}"
    )
    if not patients:
        log.warning("no_patients collection=%s", collection.name)
        return []

    # Sample more patients than we need so studies-per-patient variance
    # doesn't starve us of targets.
    max_patients = max(collection.target_count * PATIENTS_MULTIPLIER, collection.target_count)
    patient_ids = [
        (p.get("PatientID") or p.get("patientId"))
        for p in patients
        if p.get("PatientID") or p.get("patientId")
    ][:max_patients]

    targets: list[tuple[str, str]] = []
    for pid in patient_ids:
        if len(targets) >= collection.target_count:
            break
        try:
            studies = _retry_call(
                client.list_studies,
                collection.name,
                pid,
                label=f"list_studies:{collection.name}:{pid}",
            )
        except Exception as exc:
            log.warning("list_studies_failed patient=%s err=%s", pid, exc)
            continue
        for s in studies:
            uid = s.get("StudyInstanceUID") or s.get("studyInstanceUID")
            if not uid:
                continue
            targets.append((pid, uid))
            if len(targets) >= collection.target_count:
                break
    return targets


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TCIA demo seed downloader")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "seed_config.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan-only; do not contact TCIA.",
    )
    parser.add_argument(
        "--accept-restricted",
        action="store_true",
        help="Download collections with license=RESTRICTED.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print the JSON plan and exit.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Per-study retry count (default {DEFAULT_RETRIES}).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = load_config(args.config)
    cache_dir = Path(cfg.get("cache_dir", "./demo_data/cache")).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    collections = parse_collections(cfg)
    if args.plan_only:
        json.dump(plan(collections, cache_dir), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    client = TCIAClient() if not args.dry_run else None

    skipped = 0
    done = 0
    failed = 0
    for c in collections:
        if c.license == "RESTRICTED" and not args.accept_restricted:
            log.warning(
                "skipping_restricted_collection name=%s (use --accept-restricted to override)",
                c.name,
            )
            continue

        if args.dry_run:
            targets = _iter_study_targets(c, client=TCIAClient(), dry_run=True)
        else:
            assert client is not None
            try:
                targets = _iter_study_targets(c, client=client, dry_run=False)
            except Exception as exc:
                log.error("collection_list_failed name=%s err=%s", c.name, exc)
                failed += c.target_count
                continue

        if not targets:
            log.warning("no_targets collection=%s", c.name)
            continue

        for patient_id, study_uid in targets:
            outcome = download_study(
                c,
                patient_id,
                study_uid,
                cache_dir,
                dry_run=args.dry_run,
                client=client,
                retries=args.retries,
            )
            if outcome == "skip":
                skipped += 1
            elif outcome == "done":
                done += 1
            else:
                failed += 1

    log.info("seed_complete skipped=%d done=%d failed=%d", skipped, done, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
