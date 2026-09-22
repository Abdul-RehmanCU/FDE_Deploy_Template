from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Iterable

from .config import InstallationConfig
from .cost import load_cost_gate
from .gate import load_release_gate
from .process import executable, redact, run


class OperationError(RuntimeError):
    pass


def assert_scope(config: InstallationConfig, customer: str, environment: str, project: str) -> None:
    supplied = (customer, environment, project)
    expected = (config.customer, config.environment, config.project)
    if supplied != expected:
        raise OperationError(f"explicit scope {supplied!r} does not match configuration {expected!r}")


def terraform_plan(
    config: InstallationConfig,
    terraform_dir: Path,
    backend_bucket: str,
    state_prefix: str,
    output: Path,
) -> None:
    terraform = executable("terraform")
    run([terraform, "init", "-input=false", f"-backend-config=bucket={backend_bucket}", f"-backend-config=prefix={state_prefix}"], cwd=terraform_dir)
    run([terraform, "validate", "-no-color"], cwd=terraform_dir)
    run(
        [
            terraform,
            "plan",
            "-input=false",
            "-lock-timeout=60s",
            f"-var=project_id={config.project}",
            f"-var=customer={config.customer}",
            f"-var=cluster_name=fde-{config.customer}-demo",
            f"-out={output.resolve()}",
        ],
        cwd=terraform_dir,
    )


def deploy_demo(
    config: InstallationConfig,
    *,
    gate_path: Path,
    cost_path: Path,
    terraform_dir: Path,
    plan_path: Path,
    chart: Path,
    values: Path,
) -> None:
    if config.profile != "demo":
        raise OperationError("managed profile deployment is forbidden under the USD 25 demo authorization")
    cost = load_cost_gate(cost_path)
    gate = load_release_gate(gate_path)
    if cost.project != config.project or gate.project != config.project or gate.customer != config.customer:
        raise OperationError("cost/release evidence does not match explicit deployment scope")
    git = executable("git")
    revision = run([git, "-C", str(terraform_dir), "rev-parse", "HEAD"]).stdout.strip().lower()
    if revision != gate.revision.lower():
        raise OperationError("release gate revision does not match the current repository HEAD")
    if plan_path.stat().st_mtime > gate_path.stat().st_mtime:
        raise OperationError("release gate must be issued after the final Terraform plan")
    terraform = executable("terraform")
    run([terraform, "apply", "-input=false", "-lock-timeout=60s", str(plan_path.resolve())], cwd=terraform_dir)
    gcloud = executable("gcloud")
    run([gcloud, "container", "clusters", "get-credentials", f"fde-{config.customer}-demo", f"--zone={config.zone}", f"--project={config.project}"])
    helm = executable("helm")
    run(
        [helm, "upgrade", "--install", config.release, str(chart.resolve()), "--namespace", config.namespace, "--create-namespace", "--values", str(values.resolve()), "--atomic", "--wait", "--wait-for-jobs", "--timeout", "12m"],
    )


def verify_release(config: InstallationConfig, *, local_port: int = 18080) -> dict[str, object]:
    kubectl = executable("kubectl")
    for component in ("api", "worker", "publisher", "frontend"):
        run([kubectl, "rollout", "status", f"deployment/{config.release}-{component}", "--namespace", config.namespace, "--timeout=180s"])
    process = subprocess.Popen(
        [kubectl, "port-forward", f"service/{config.release}-api", f"{local_port}:8000", "--namespace", config.namespace],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{local_port}/api/v1/health/ready", timeout=2) as response:
                    readiness = json.loads(response.read().decode("utf-8"))
                with urllib.request.urlopen(f"http://127.0.0.1:{local_port}/api/v1/version", timeout=2) as response:
                    version = json.loads(response.read().decode("utf-8"))
                return {"ready": readiness, "version": version}
            except (OSError, json.JSONDecodeError):
                time.sleep(1)
        detail = process.stderr.read() if process.poll() is not None and process.stderr else "port-forward did not become ready"
        raise OperationError(redact(detail))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def rollback_release(config: InstallationConfig) -> None:
    helm = executable("helm")
    run([helm, "rollback", config.release, "--namespace", config.namespace, "--wait", "--timeout", "8m"])
    run([executable("kubectl"), "rollout", "status", f"deployment/{config.release}-api", "--namespace", config.namespace, "--timeout=180s"])


def collect_evidence(config: InstallationConfig, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: dict[str, list[str]] = {
        "cluster": [executable("gcloud"), "container", "clusters", "describe", f"fde-{config.customer}-demo", f"--zone={config.zone}", f"--project={config.project}", "--format=json"],
        "workloads": [executable("kubectl"), "get", "deployments,statefulsets,jobs,pods,pvc", "--namespace", config.namespace, "-o", "json"],
        "helm": [executable("helm"), "status", config.release, "--namespace", config.namespace, "--output", "json"],
        "compute_instances": [executable("gcloud"), "compute", "instances", "list", f"--project={config.project}", "--format=json"],
        "compute_disks": [executable("gcloud"), "compute", "disks", "list", f"--project={config.project}", "--format=json"],
        "compute_addresses": [executable("gcloud"), "compute", "addresses", "list", f"--project={config.project}", "--format=json"],
        "artifact_repositories": [executable("gcloud"), "artifacts", "repositories", "list", f"--project={config.project}", "--location=all", "--format=json"],
        "storage_buckets": [executable("gcloud"), "storage", "buckets", "list", f"--project={config.project}", "--format=json"],
        "expiry_workflows": [executable("gcloud"), "workflows", "list", f"--project={config.project}", f"--location={config.region}", "--format=json"],
        "expiry_schedules": [executable("gcloud"), "scheduler", "jobs", "list", f"--project={config.project}", f"--location={config.region}", "--format=json"],
    }
    evidence: dict[str, object] = {"scope": {"customer": config.customer, "environment": config.environment, "project": config.project}, "config_fingerprint": config.fingerprint}
    for name, command in commands.items():
        result = run(command, check=False)
        raw = redact(result.stdout if result.returncode == 0 else result.stderr)
        try:
            evidence[name] = json.loads(raw)
        except json.JSONDecodeError:
            evidence[name] = {"returncode": result.returncode, "output": raw}
    path = output_dir / "deployment-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return path


def destroy_demo(config: InstallationConfig, terraform_dir: Path, confirm_customer: str) -> list[dict[str, object]]:
    if confirm_customer != config.customer:
        raise OperationError("--confirm-customer must exactly match the configured customer")
    terraform = executable("terraform")
    run([terraform, "destroy", "-input=false", "-auto-approve", "-lock-timeout=60s", f"-var=project_id={config.project}", f"-var=customer={config.customer}", f"-var=cluster_name=fde-{config.customer}-demo"], cwd=terraform_dir)
    gcloud = executable("gcloud")
    inventory_commands: Iterable[tuple[str, list[str]]] = (
        ("clusters", [gcloud, "container", "clusters", "list", f"--project={config.project}", "--format=json"]),
        ("instances", [gcloud, "compute", "instances", "list", f"--project={config.project}", "--format=json"]),
        ("disks", [gcloud, "compute", "disks", "list", f"--project={config.project}", "--format=json"]),
        ("addresses", [gcloud, "compute", "addresses", "list", f"--project={config.project}", "--format=json"]),
    )
    inventory = []
    for name, command in inventory_commands:
        result = run(command)
        inventory.append({"kind": name, "resources": json.loads(result.stdout)})
    return inventory
