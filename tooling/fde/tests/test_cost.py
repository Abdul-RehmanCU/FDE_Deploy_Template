from decimal import Decimal
from pathlib import Path

import pytest

from fde_cli.cost import CostGateError, load_cost_gate


ESTIMATE = Path(__file__).parents[3] / "infra" / "cost" / "demo-estimate.yaml"


def test_committed_demo_estimate_reconciles_below_cap() -> None:
    gate = load_cost_gate(ESTIMATE)
    assert gate.estimated_total_usd == Decimal("4.96619304")
    assert gate.estimate_passes
    assert gate.reserve_usd == Decimal("15.00")
    assert gate.paid_provisioning_allowed is False


def test_rejects_understated_total(tmp_path: Path) -> None:
    text = ESTIMATE.read_text(encoding="utf-8").replace("estimated_total_usd: 4.96619304", "estimated_total_usd: 4.00")
    path = tmp_path / "estimate.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CostGateError, match="reconcile"):
        load_cost_gate(path)


def test_rejects_cost_evidence_for_a_different_zone(tmp_path: Path) -> None:
    text = ESTIMATE.read_text(encoding="utf-8").replace(
        "zone: example-region1-a", "zone: another-region2-a"
    )
    path = tmp_path / "estimate.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CostGateError, match="consistent region and zone"):
        load_cost_gate(path)
