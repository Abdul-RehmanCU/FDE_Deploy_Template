import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fde_cli.gate import ReleaseGateError, load_release_gate


NOW = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


def write_gate(tmp_path: Path, **changes: object) -> Path:
    data = {
        "project": "fdetemplate",
        "customer": "acme",
        "revision": "a" * 40,
        "expires_at": (NOW + timedelta(hours=3, minutes=59)).isoformat(),
        "estimate_total_usd": 4.50619304,
        "ci_kind_passed": True,
        "expiry_sentinel_passed": True,
        "independent_review_accepted": True,
        "exact_manifest_sha": "b" * 64,
    }
    data.update(changes)
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_accepts_complete_bounded_gate(tmp_path: Path) -> None:
    gate = load_release_gate(write_gate(tmp_path), now=NOW)
    assert gate.estimate_total_usd == 4.50619304


@pytest.mark.parametrize("field", ["ci_kind_passed", "expiry_sentinel_passed", "independent_review_accepted"])
def test_rejects_incomplete_evidence(tmp_path: Path, field: str) -> None:
    with pytest.raises(ReleaseGateError, match="must all pass"):
        load_release_gate(write_gate(tmp_path, **{field: False}), now=NOW)


def test_rejects_expiry_over_four_hours(tmp_path: Path) -> None:
    with pytest.raises(ReleaseGateError, match="four hours"):
        load_release_gate(write_gate(tmp_path, expires_at=(NOW + timedelta(hours=4, seconds=1)).isoformat()), now=NOW)


def test_rejects_expired_gate(tmp_path: Path) -> None:
    with pytest.raises(ReleaseGateError, match="future"):
        load_release_gate(write_gate(tmp_path, expires_at=(NOW - timedelta(seconds=1)).isoformat()), now=NOW)


def test_rejects_manfiest_mismatch_shape(tmp_path: Path) -> None:
    with pytest.raises(ReleaseGateError, match="sha256"):
        load_release_gate(write_gate(tmp_path, exact_manifest_sha="wrong"), now=NOW)


def test_rejects_estimate_over_cap(tmp_path: Path) -> None:
    with pytest.raises(ReleaseGateError, match="exceeds"):
        load_release_gate(write_gate(tmp_path, estimate_total_usd=10.01), now=NOW)
