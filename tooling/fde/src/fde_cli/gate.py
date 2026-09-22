from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


class ReleaseGateError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseGate:
    project: str
    customer: str
    revision: str
    expires_at: datetime
    estimate_total_usd: float
    ci_kind_passed: bool
    expiry_sentinel_passed: bool
    independent_review_accepted: bool
    exact_manifest_sha: str


def load_release_gate(path: str | Path, *, now: datetime | None = None) -> ReleaseGate:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"cannot read release gate: {exc}") from exc
    try:
        expires_at = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
        gate = ReleaseGate(
            project=str(data["project"]),
            customer=str(data["customer"]),
            revision=str(data["revision"]),
            expires_at=expires_at,
            estimate_total_usd=float(data["estimate_total_usd"]),
            ci_kind_passed=data["ci_kind_passed"] is True,
            expiry_sentinel_passed=data["expiry_sentinel_passed"] is True,
            independent_review_accepted=data["independent_review_accepted"] is True,
            exact_manifest_sha=str(data["exact_manifest_sha"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseGateError(f"invalid release gate: {exc}") from exc
    current = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        raise ReleaseGateError("expires_at must include a timezone")
    remaining = expires_at.astimezone(timezone.utc) - current.astimezone(timezone.utc)
    if remaining <= timedelta(0) or remaining > timedelta(hours=4):
        raise ReleaseGateError("expiry must be in the future and no more than four hours away")
    if gate.estimate_total_usd > 10:
        raise ReleaseGateError("estimated total exceeds the USD 10 demo gate")
    if not all((gate.ci_kind_passed, gate.expiry_sentinel_passed, gate.independent_review_accepted)):
        raise ReleaseGateError("CI/kind, expiry sentinel, and independent review must all pass")
    if len(gate.revision) < 7 or not all(char in "0123456789abcdef" for char in gate.revision.lower()):
        raise ReleaseGateError("revision must be a git commit SHA")
    if len(gate.exact_manifest_sha) != 64 or not all(char in "0123456789abcdef" for char in gate.exact_manifest_sha.lower()):
        raise ReleaseGateError("exact_manifest_sha must be a sha256 digest")
    return gate
