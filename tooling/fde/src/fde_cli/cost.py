from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path

import yaml


class CostGateError(ValueError):
    pass


@dataclass(frozen=True)
class CostGate:
    project: str
    region: str
    zone: str
    estimated_total_usd: Decimal
    calculated_total_usd: Decimal
    estimate_cap_usd: Decimal
    reserve_usd: Decimal
    baseline_amount: Decimal
    baseline_observed_at: datetime
    paid_provisioning_allowed: bool

    @property
    def estimate_passes(self) -> bool:
        return (
            self.estimated_total_usd <= self.estimate_cap_usd
            and abs(self.estimated_total_usd - self.calculated_total_usd) <= Decimal("0.000001")
        )


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise CostGateError(f"{field} must be numeric") from exc


def load_cost_gate(path: str | Path) -> CostGate:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CostGateError(f"cannot read cost estimate: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CostGateError("cost estimate requires an items list")
    item_total = sum(
        (_decimal(item.get("estimated_usd"), f"items[{index}].estimated_usd") for index, item in enumerate(data["items"])),
        Decimal("0"),
    )
    auth = data.get("authorization", {})
    baseline = data.get("reported_cost_baseline", {})
    gate = data.get("gate", {})
    result = CostGate(
        project=str(data.get("project", "")),
        region=str(data.get("region", "")),
        zone=str(data.get("zone", "")),
        estimated_total_usd=_decimal(data.get("estimated_total_usd"), "estimated_total_usd"),
        calculated_total_usd=item_total,
        estimate_cap_usd=_decimal(auth.get("demo_estimate_cap_usd"), "demo_estimate_cap_usd"),
        reserve_usd=_decimal(auth.get("delayed_charge_reserve_usd"), "delayed_charge_reserve_usd"),
        baseline_amount=_decimal(baseline.get("amount"), "baseline amount"),
        baseline_observed_at=datetime.fromisoformat(str(baseline.get("observed_at", "")).replace("Z", "+00:00")),
        paid_provisioning_allowed=gate.get("paid_provisioning_allowed") is True,
    )
    if not result.project:
        raise CostGateError("cost estimate project is required")
    if not result.region or not result.zone.startswith(result.region + "-"):
        raise CostGateError("cost estimate needs a consistent region and zone")
    if result.reserve_usd < Decimal("15"):
        raise CostGateError("delayed-charge reserve cannot be below USD 15")
    if not result.estimate_passes:
        raise CostGateError("item total does not reconcile or exceeds USD 10 cap")
    return result
