"""Reconcile local _orthanc_uploaded.marker files with Orthanc truth.

Session 16 emergency tool. After the first load_orthanc.py run's
client-side timeouts (60s), many studies were actually received by
Orthanc server-side but the client never saw the 200 response, so the
marker was not written. Re-running load_orthanc.py then wastes time
retrying studies that already exist server-side.

This one-off queries Orthanc via QIDO-RS (/dicom-web/studies) for all
StudyInstanceUIDs it holds, compares to local study directories, and
writes `_orthanc_uploaded.marker` for matches. Safe to run while
load_orthanc.py is still executing — the marker check inside the
upload loop is evaluated fresh each iteration.

Usage:
    python scripts/demo_seed/reconcile_orthanc.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

try:
    import yaml  # type: ignore[import-untyped]
except Exception:
    yaml = None  # type: ignore[assignment]

CFG_PATH = Path(__file__).parent / "seed_config.yaml"
MARKER = "_orthanc_uploaded.marker"


def _auth(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("ascii")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def main() -> int:
    if yaml is None:
        print("ERR: PyYAML required", file=sys.stderr)
        return 2
    cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
    cache_dir = Path(cfg.get("cache_dir", "./demo_data/cache")).resolve()
    orthanc_cfg = cfg.get("orthanc", {}) or {}
    base_url = orthanc_cfg.get("url", "http://localhost:8042")
    username = orthanc_cfg.get("username", "orthanc")
    password = orthanc_cfg.get("password", "orthanc")

    headers = {"Authorization": _auth(username, password)}
    with httpx.Client(base_url=base_url, headers=headers, timeout=120.0) as c:
        # QIDO-RS returns JSON array of study objects with DICOM tag dicts.
        # StudyInstanceUID = tag 0020000D.
        resp = c.get("/dicom-web/studies", params={"limit": 10000})
        resp.raise_for_status()
        studies = resp.json()

    uids: set[str] = set()
    for s in studies:
        tag = s.get("0020000D") or {}
        values = tag.get("Value") or []
        if values:
            uids.add(str(values[0]))
    print(f"Orthanc reports {len(uids)} StudyInstanceUIDs")

    if not cache_dir.exists():
        print(f"cache_dir missing: {cache_dir}")
        return 1

    new_markers = 0
    already = 0
    orphans = 0
    local_uids: set[str] = set()
    for col_dir in sorted(cache_dir.iterdir()):
        if not col_dir.is_dir():
            continue
        for study_dir in sorted(col_dir.iterdir()):
            if not study_dir.is_dir():
                continue
            local_uids.add(study_dir.name)
            if study_dir.name in uids:
                marker = study_dir / MARKER
                if marker.exists():
                    already += 1
                else:
                    marker.write_text(
                        "reconciled=orthanc source=qido-rs\n", encoding="utf-8"
                    )
                    new_markers += 1

    orphans = len(uids - local_uids)
    print(f"Already marked: {already}")
    print(f"New markers written: {new_markers}")
    print(f"Orthanc studies without local dir (orphans): {orphans}")
    print(f"Local studies still unmarked: {len(local_uids - uids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
