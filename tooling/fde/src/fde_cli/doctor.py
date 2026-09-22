from __future__ import annotations

import platform
from dataclasses import asdict, dataclass

from .config import InstallationConfig
from .process import executable, run, run_json

REQUIRED_DEMO_SERVICES = {
    "artifactregistry.googleapis.com",
    "cloudasset.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iamcredentials.googleapis.com",
    "secretmanager.googleapis.com",
    "sts.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _tool(name: str, version_args: list[str]) -> Check:
    try:
        path = executable(name)
        result = run([path, *version_args], check=False)
        first_line = (result.stdout or result.stderr).splitlines()[0]
        return Check(f"tool:{name}", result.returncode == 0, first_line.strip())
    except (RuntimeError, IndexError) as exc:
        return Check(f"tool:{name}", False, str(exc))


def checks(config: InstallationConfig, *, cloud: bool) -> list[Check]:
    result = [
        Check("python", True, platform.python_version()),
        _tool("terraform", ["version"]),
        _tool("helm", ["version", "--short"]),
        _tool("kubectl", ["version", "--client=true"]),
        _tool("gcloud", ["version"]),
    ]
    if not cloud:
        return result

    try:
        gcloud = executable("gcloud")
        active = run_json([gcloud, "auth", "list", "--filter=status:ACTIVE", "--format=json"])
        result.append(Check("gcloud:active-account", bool(active), "active credential present"))
        billing = run_json(
            [gcloud, "billing", "projects", "describe", config.project, "--format=json"]
        )
        enabled = isinstance(billing, dict) and billing.get("billingEnabled") is True
        result.append(Check("gcloud:billing", enabled, "billing enabled" if enabled else "billing disabled"))
        project = run_json([gcloud, "projects", "describe", config.project, "--format=json"])
        is_active = isinstance(project, dict) and project.get("lifecycleState") == "ACTIVE"
        result.append(Check("gcloud:project", is_active, str(project.get("lifecycleState", "unknown"))))
        services = run(
            [gcloud, "services", "list", "--enabled", f"--project={config.project}", "--format=value(config.name)"]
        )
        present = set(services.stdout.splitlines())
        missing = sorted(REQUIRED_DEMO_SERVICES - present)
        result.append(Check("gcloud:services", not missing, "missing: " + ", ".join(missing) if missing else "all enabled"))
    except RuntimeError as exc:
        result.append(Check("gcloud:readiness", False, str(exc)))
    return result


def serialise(items: list[Check]) -> list[dict[str, object]]:
    return [asdict(item) for item in items]
