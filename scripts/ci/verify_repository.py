"""Fail CI when repository-level publication invariants are broken."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FILES = (
    "LICENSE",
    "PLAN.md",
    "docs/upstream-provenance.md",
    "docs/implementation-ledger.md",
)
FORBIDDEN_TRACKED_NAMES = {
    ".env",
    "terraform.tfstate",
    "terraform.tfstate.backup",
    "kubeconfig",
}
FORBIDDEN_SUFFIXES = (".pem", ".p12", ".pfx")


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"Missing required repository files: {', '.join(missing)}")

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Sebastián Ramírez" not in license_text:
        raise SystemExit("The retained upstream MIT notice is incomplete")

    tracked = tracked_files()
    unsafe = sorted(
        path
        for path in tracked
        if Path(path).name in FORBIDDEN_TRACKED_NAMES
        or path.lower().endswith(FORBIDDEN_SUFFIXES)
    )
    if unsafe:
        raise SystemExit(f"Unsafe credential/state files are tracked: {', '.join(unsafe)}")

    print(f"Repository invariants verified across {len(tracked)} tracked files")


if __name__ == "__main__":
    main()
