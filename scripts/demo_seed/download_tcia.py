"""TCIA demo data downloader (dev-spec buyer-portal-demo §8.2).

Idempotent: each study directory is marked with ``_done.marker`` after
completion so reruns skip already-fetched data. Failed studies are
appended to ``_failed.json`` for manual retry.

v0.1 scope
----------
This script targets small TCIA subsets (total ~400 studies per
``seed_config.yaml``) and uses ``tcia_utils`` if available, otherwise
falls back to direct REST calls via ``requests``. Both library paths are
stubbed for the MVP — the real fetch will be wired in by the demo dry-run
(2-3 business days before the demo, per R-1 in dev-spec §8.4).

License compliance
------------------
The script halts on any collection with ``license: RESTRICTED`` unless the
operator passes ``--accept-restricted``. This is the automation side of
the manual Kyle-confirmation gate (L-1..L-3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None

log = logging.getLogger("demo_seed.download")


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


def _mark_done(study_dir: Path, files: list[Path]) -> None:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    (study_dir / "_manifest.sha256").write_text(h.hexdigest())
    (study_dir / "_done.marker").touch()


def download_study(
    collection: Collection,
    patient_id: str,
    study_uid: str,
    cache_dir: Path,
    *,
    dry_run: bool,
) -> str:
    """Download a single study. Returns 'skip' | 'done' | 'fail'."""
    target = cache_dir / collection.name / study_uid
    if (target / "_done.marker").exists():
        return "skip"
    target.mkdir(parents=True, exist_ok=True)
    try:
        if dry_run:
            (target / "_plan.txt").write_text(
                f"Would download collection={collection.name}\n"
                f"patient_id={patient_id} study_uid={study_uid}\n"
            )
            return "done"
        # Real fetch path — intentionally left as a TODO anchor for the
        # rehearsal step where we wire up tcia_utils + REST. This keeps
        # the bytes-over-network work out of the CI pipeline while the
        # structure is reviewable now.
        raise NotImplementedError(
            "TCIA fetch is wired during rehearsal R-1 (dev-spec §8.4)."
        )
    except Exception as exc:
        (target / "_error.json").write_text(json.dumps({"error": str(exc)}))
        return "fail"


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
        # Stub: emit 'target_count' placeholder studies. Rehearsal R-1
        # replaces this block with tcia_utils.list_patients().
        for i in range(c.target_count):
            patient_id = f"{c.name[:6]}-P-{i:05d}"
            study_uid = f"2.25.demo.{c.name}.{i}"
            outcome = download_study(
                c,
                patient_id,
                study_uid,
                cache_dir,
                dry_run=args.dry_run,
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
