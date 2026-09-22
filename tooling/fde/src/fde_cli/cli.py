from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigurationError, load_config
from .doctor import checks, serialise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="fde", description="Guardrailed FDE deployment CLI")
    subcommands = result.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-config", help="Validate a customer installation file")
    validate.add_argument("--config", required=True)

    doctor = subcommands.add_parser("doctor", help="Check local tools and optional GCP readiness")
    doctor.add_argument("--config", required=True)
    doctor.add_argument("--cloud", action="store_true", help="Run read-only GCP checks")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            print(json.dumps({"valid": True, "fingerprint": config.fingerprint}, indent=2))
            return 0
        if args.command == "doctor":
            results = checks(config, cloud=args.cloud)
            print(json.dumps({"checks": serialise(results)}, indent=2))
            return 0 if all(item.ok for item in results) else 2
    except (ConfigurationError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
