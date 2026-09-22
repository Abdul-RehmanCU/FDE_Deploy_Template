from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigurationError, load_config
from .doctor import checks, serialise
from .operations import (
    OperationError,
    assert_scope,
    bootstrap_gcp,
    collect_evidence,
    deploy_demo,
    deploy_demo_infrastructure,
    deploy_release,
    destroy_demo,
    rollback_release,
    terraform_plan,
    verify_release,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="fde", description="Guardrailed FDE deployment CLI")
    subcommands = result.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-config", help="Validate a customer installation file")
    validate.add_argument("--config", required=True)

    doctor = subcommands.add_parser("doctor", help="Check local tools and optional GCP readiness")
    doctor.add_argument("--config", required=True)
    doctor.add_argument("--cloud", action="store_true", help="Run read-only GCP checks")

    def cloud_command(name: str, help_text: str) -> argparse.ArgumentParser:
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("--config", required=True)
        command.add_argument("--customer", required=True)
        command.add_argument("--environment", required=True)
        command.add_argument("--project", required=True)
        return command

    plan = cloud_command("plan", "Create a saved Terraform plan without applying it")
    plan.add_argument("--terraform-dir", required=True)
    plan.add_argument("--backend-bucket", required=True)
    plan.add_argument("--state-prefix", required=True)
    plan.add_argument("--out", required=True)
    plan.add_argument("--expiry-id", required=True)

    bootstrap = cloud_command("bootstrap", "Create the bounded state/WIF bootstrap in the configured project")
    bootstrap.add_argument("--terraform-dir", required=True)
    bootstrap.add_argument("--state-bucket", required=True)
    bootstrap.add_argument("--github-repository", required=True)
    bootstrap.add_argument("--confirm-project", required=True)

    deploy = cloud_command("deploy", "Apply an approved demo plan and deploy its chart")
    deploy.add_argument("--gate", required=True)
    deploy.add_argument("--cost", required=True)
    deploy.add_argument("--terraform-dir", required=True)
    deploy.add_argument("--plan", required=True)
    deploy.add_argument("--chart", required=True)
    deploy.add_argument("--values", required=True)
    deploy.add_argument("--expiry-terraform-dir", required=True)
    deploy.add_argument("--expiry-evidence", required=True)

    deploy_infra = cloud_command("deploy-infrastructure", "Apply an approved demo infrastructure plan only")
    deploy_infra.add_argument("--gate", required=True)
    deploy_infra.add_argument("--cost", required=True)
    deploy_infra.add_argument("--terraform-dir", required=True)
    deploy_infra.add_argument("--plan", required=True)
    deploy_infra.add_argument("--expiry-terraform-dir", required=True)
    deploy_infra.add_argument("--expiry-evidence", required=True)

    deploy_app = cloud_command("deploy-release", "Deploy rendered Helm values after infrastructure outputs exist")
    deploy_app.add_argument("--chart", required=True)
    deploy_app.add_argument("--values", required=True)

    verify = cloud_command("verify", "Verify rollout and dependency-aware health")
    verify.add_argument("--local-port", type=int, default=18080)

    cloud_command("rollback", "Roll application workloads back to the previous Helm revision")

    evidence = cloud_command("evidence", "Collect sanitized deployment evidence")
    evidence.add_argument("--output-dir", required=True)

    destroy = cloud_command("destroy", "Destroy the exact Terraform demo and inventory residues")
    destroy.add_argument("--terraform-dir", required=True)
    destroy.add_argument("--confirm-customer", required=True)
    destroy.add_argument("--expiry-id", required=True)
    destroy.add_argument("--expiry-terraform-dir", required=True)
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
        assert_scope(config, args.customer, args.environment, args.project)
        if args.command == "plan":
            terraform_plan(
                config,
                Path(args.terraform_dir),
                args.backend_bucket,
                args.state_prefix,
                Path(args.out),
                args.expiry_id,
            )
            return 0
        if args.command == "bootstrap":
            bootstrap_gcp(
                config,
                terraform_dir=Path(args.terraform_dir),
                state_bucket=args.state_bucket,
                github_repository=args.github_repository,
                confirm_project=args.confirm_project,
            )
            return 0
        if args.command == "deploy":
            deploy_demo(
                config,
                gate_path=Path(args.gate),
                cost_path=Path(args.cost),
                terraform_dir=Path(args.terraform_dir),
                plan_path=Path(args.plan),
                chart=Path(args.chart),
                values=Path(args.values),
                expiry_terraform_dir=Path(args.expiry_terraform_dir),
                expiry_evidence_path=Path(args.expiry_evidence),
            )
            return 0
        if args.command == "deploy-infrastructure":
            deploy_demo_infrastructure(
                config,
                gate_path=Path(args.gate),
                cost_path=Path(args.cost),
                terraform_dir=Path(args.terraform_dir),
                plan_path=Path(args.plan),
                expiry_terraform_dir=Path(args.expiry_terraform_dir),
                expiry_evidence_path=Path(args.expiry_evidence),
            )
            return 0
        if args.command == "deploy-release":
            deploy_release(config, chart=Path(args.chart), values=Path(args.values))
            return 0
        if args.command == "verify":
            print(json.dumps(verify_release(config, local_port=args.local_port), indent=2))
            return 0
        if args.command == "rollback":
            print(json.dumps(rollback_release(config), indent=2))
            return 0
        if args.command == "evidence":
            print(collect_evidence(config, Path(args.output_dir)))
            return 0
        if args.command == "destroy":
            print(json.dumps(destroy_demo(config, Path(args.terraform_dir), args.confirm_customer, args.expiry_id, Path(args.expiry_terraform_dir)), indent=2))
            return 0
    except (ConfigurationError, OperationError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
