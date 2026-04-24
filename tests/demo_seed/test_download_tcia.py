"""Unit tests for scripts/demo_seed/download_tcia.py real-fetch path.

These supplement the existing ``tests/unit/test_demo_seed_download.py``
(which only covers dry-run / plan-only). Network I/O is stubbed via a
fake ``TCIAClient``; no live requests are ever made.
"""

from __future__ import annotations

import json

import pytest


class FakeTCIAClient:
    """In-memory double for :class:`TCIAClient`.

    Records call counts so tests can assert retry behaviour.
    """

    def __init__(self, *, fail_first_n: int = 0, dcm_per_series: int = 2) -> None:
        self.fail_first_n = fail_first_n
        self.dcm_per_series = dcm_per_series
        self.calls = {"list_patients": 0, "list_studies": 0, "list_series": 0, "download_series": 0}

    def list_patients(self, collection):
        self.calls["list_patients"] += 1
        return [{"PatientID": f"P-{collection}-{i:03d}"} for i in range(5)]

    def list_studies(self, collection, patient_id):
        self.calls["list_studies"] += 1
        return [{"StudyInstanceUID": f"2.25.study.{collection}.{patient_id}"}]

    def list_series(self, study_uid):
        self.calls["list_series"] += 1
        if self.calls["list_series"] <= self.fail_first_n:
            raise RuntimeError(f"simulated network flake {self.calls['list_series']}")
        return [{"SeriesInstanceUID": f"{study_uid}.series.{i}"} for i in range(1)]

    def download_series(self, series_uids, dest):
        self.calls["download_series"] += 1
        dest.mkdir(parents=True, exist_ok=True)
        # Write small fake DICOM-shaped files. The real download would
        # produce proper Part 10 files; we only need something the
        # pydicom header validator accepts, which we stub out below.
        for i, uid in enumerate(series_uids):
            (dest / f"IM_{i:04d}.dcm").write_bytes(b"DICMFAKE" + uid.encode() + b"\0" * 128)


def test_retry_succeeds_after_flake(download_mod, tmp_path, monkeypatch):
    """`_retry_call` should absorb transient failures up to the retry limit."""
    # Keep the retry sleep bounded for fast tests.
    monkeypatch.setattr(download_mod, "RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(download_mod, "RETRY_JITTER_SECONDS", 0.0)

    results: list[int] = []

    def flaky():
        results.append(len(results))
        if len(results) < 2:
            raise RuntimeError("try again")
        return "ok"

    out = download_mod._retry_call(flaky, retries=3, label="t")
    assert out == "ok"
    assert len(results) == 2  # failed once, succeeded on 2nd


def test_retry_gives_up_after_max_attempts(download_mod, monkeypatch):
    monkeypatch.setattr(download_mod, "RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(download_mod, "RETRY_JITTER_SECONDS", 0.0)
    with pytest.raises(RuntimeError, match="persistent"):
        download_mod._retry_call(lambda: (_ for _ in ()).throw(RuntimeError("persistent")), retries=2)


def test_download_study_writes_manifest_and_marker(download_mod, tmp_path, monkeypatch):
    """Happy path: download + header validation + manifest/marker write."""
    monkeypatch.setattr(download_mod, "RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(download_mod, "_validate_dicom_headers", lambda study_dir: 1)
    client = FakeTCIAClient()
    coll = download_mod.Collection(
        name="TEST-CT",
        modality="CT",
        body_part="CHEST",
        target_count=1,
        license="CC-BY",
    )
    outcome = download_mod.download_study(
        coll,
        "P-001",
        "2.25.study.test",
        tmp_path,
        dry_run=False,
        client=client,
        retries=2,
    )
    assert outcome == "done"
    study_dir = tmp_path / "TEST-CT" / "2.25.study.test"
    assert (study_dir / "_done.marker").exists()
    manifest = (study_dir / "_manifest.sha256").read_text().strip()
    assert len(manifest) == 64  # SHA-256 hex
    assert client.calls["download_series"] == 1


def test_download_study_idempotent_skip(download_mod, tmp_path):
    """Re-running a study with an existing _done.marker must skip (FR-S-6)."""
    coll = download_mod.Collection(
        name="TEST-CT",
        modality="CT",
        body_part="CHEST",
        target_count=1,
        license="CC-BY",
    )
    study_dir = tmp_path / "TEST-CT" / "2.25.study.skip"
    study_dir.mkdir(parents=True)
    (study_dir / "_done.marker").touch()

    client = FakeTCIAClient()
    outcome = download_mod.download_study(
        coll,
        "P-001",
        "2.25.study.skip",
        tmp_path,
        dry_run=False,
        client=client,
    )
    assert outcome == "skip"
    assert client.calls["download_series"] == 0


def test_download_study_records_failure(download_mod, tmp_path, monkeypatch):
    """On unrecoverable error, an entry must land in ``_failed.json`` (FR-S-7)."""
    monkeypatch.setattr(download_mod, "RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(download_mod, "RETRY_JITTER_SECONDS", 0.0)

    class AlwaysFailsClient(FakeTCIAClient):
        def list_series(self, study_uid):
            raise RuntimeError("fatal")

    coll = download_mod.Collection(
        name="TEST-CT",
        modality="CT",
        body_part="CHEST",
        target_count=1,
        license="CC-BY",
    )
    outcome = download_mod.download_study(
        coll,
        "P-001",
        "2.25.study.fail",
        tmp_path,
        dry_run=False,
        client=AlwaysFailsClient(),
        retries=2,
    )
    assert outcome == "fail"
    failures = json.loads((tmp_path / "_failed.json").read_text())
    assert len(failures) == 1
    assert failures[0]["study_uid"] == "2.25.study.fail"
    assert "fatal" in failures[0]["error"]


def test_iter_study_targets_respects_target_count(download_mod, monkeypatch):
    """Planner returns up to ``target_count`` (patient, study) pairs."""
    coll = download_mod.Collection(
        name="TEST-MR",
        modality="MR",
        body_part="BRAIN",
        target_count=3,
        license="CC-BY",
    )

    class Wide(FakeTCIAClient):
        def list_studies(self, collection, patient_id):
            self.calls["list_studies"] += 1
            return [{"StudyInstanceUID": f"{patient_id}.study.{i}"} for i in range(2)]

    targets = download_mod._iter_study_targets(coll, client=Wide(), dry_run=False)
    assert len(targets) == 3
    # All unique study UIDs.
    assert len({uid for _, uid in targets}) == 3


def test_config_missing_emits_bilingual_error(download_mod, tmp_path, capsys):
    missing = tmp_path / "no.yaml"
    with pytest.raises(SystemExit) as exc:
        download_mod.main(["--config", str(missing)])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    # AC-S-6 — bilingual error.
    assert "ERR_SEED_CONFIG_MISSING" in err
    assert "설정 파일" in err  # Korean half present
