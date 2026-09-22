import json
from pathlib import Path


LEDGER = Path(__file__).parents[3] / "infra" / "cost" / "ledger.demo.json"


def test_ledger_stays_within_authorization_and_preserves_pending_state() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    authorization = ledger["authorization"]
    assert authorization["total_usd"] == 25
    assert authorization["demo_estimate_cap_usd"] <= 10
    assert authorization["reserve_usd"] >= 15
    assert ledger["estimate"]["amount_usd"] <= authorization["demo_estimate_cap_usd"]
    assert ledger["billing"]["pending_delayed_charges"] is True
    assert ledger["paid_run"]["started_at"] is None
    assert all(event["billable_resources_created"] is False for event in ledger["events"])
