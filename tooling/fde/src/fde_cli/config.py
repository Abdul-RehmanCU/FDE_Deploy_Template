from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_PROFILES = {"demo", "managed"}
_ALLOWED_DEMO_REGION = "northamerica-northeast1"
_ALLOWED_DEMO_ZONE = "northamerica-northeast1-a"


class ConfigurationError(ValueError):
    """Raised when a customer installation configuration is unsafe or invalid."""


@dataclass(frozen=True)
class ResourceSizing:
    api_replicas: int
    worker_replicas: int
    api_cpu: str
    api_memory: str
    worker_cpu: str
    worker_memory: str


@dataclass(frozen=True)
class InstallationConfig:
    customer: str
    environment: str
    project: str
    region: str
    zone: str
    profile: str
    namespace: str
    image_repository: str
    image_digest: str
    branding_name: str
    sizing: ResourceSizing
    domain: str | None = None

    @property
    def release(self) -> str:
        return f"fde-{self.customer}-{self.environment}"

    @property
    def immutable_image(self) -> str:
        return f"{self.image_repository}@{self.image_digest}"

    @property
    def fingerprint(self) -> str:
        value = "\n".join(
            (self.customer, self.environment, self.project, self.profile, self.image_digest)
        )
        return hashlib.sha256(value.encode()).hexdigest()[:16]


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{key} must be a non-empty string")
    return value.strip()


def load_config(path: str | Path) -> InstallationConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot read configuration: {exc}") from exc
    data = _mapping(raw, "configuration")

    customer = _required_text(data, "customer")
    environment = _required_text(data, "environment")
    project = _required_text(data, "project")
    region = _required_text(data, "region")
    zone = _required_text(data, "zone")
    profile = _required_text(data, "profile")
    namespace = _required_text(data, "namespace")
    image_repository = _required_text(data, "image_repository")
    image_digest = _required_text(data, "image_digest")

    for field, value in (("customer", customer), ("environment", environment), ("namespace", namespace)):
        if not _SLUG.fullmatch(value):
            raise ConfigurationError(f"{field} must be a lowercase DNS-safe slug")
    if not _PROJECT.fullmatch(project):
        raise ConfigurationError("project is not a valid GCP project ID")
    if profile not in _ALLOWED_PROFILES:
        raise ConfigurationError("profile must be demo or managed")
    if profile == "demo" and (region != _ALLOWED_DEMO_REGION or zone != _ALLOWED_DEMO_ZONE):
        raise ConfigurationError("demo is fixed to Montréal northamerica-northeast1/a")
    if not _DIGEST.fullmatch(image_digest):
        raise ConfigurationError("image_digest must be an immutable sha256 digest")
    expected_prefix = f"{region}-docker.pkg.dev/{project}/"
    if not image_repository.startswith(expected_prefix):
        raise ConfigurationError("image_repository must be regional and belong to project")

    sizing_data = _mapping(data.get("sizing"), "sizing")
    sizing = ResourceSizing(
        api_replicas=int(sizing_data.get("api_replicas", 2)),
        worker_replicas=int(sizing_data.get("worker_replicas", 1)),
        api_cpu=_required_text(sizing_data, "api_cpu"),
        api_memory=_required_text(sizing_data, "api_memory"),
        worker_cpu=_required_text(sizing_data, "worker_cpu"),
        worker_memory=_required_text(sizing_data, "worker_memory"),
    )
    if profile == "demo" and sizing.api_replicas != 2:
        raise ConfigurationError("demo requires exactly two API replicas")
    if not 1 <= sizing.worker_replicas <= 4:
        raise ConfigurationError("worker_replicas must be between one and four")

    branding = _mapping(data.get("branding", {}), "branding")
    branding_name = str(branding.get("name", customer)).strip()
    domain = data.get("domain")
    if domain is not None and (not isinstance(domain, str) or not domain.strip()):
        raise ConfigurationError("domain must be omitted or a non-empty string")

    forbidden = {"password", "secret", "token", "private_key", "api_key"}
    present = forbidden.intersection(data)
    if present:
        raise ConfigurationError(f"secret-bearing top-level keys are forbidden: {', '.join(sorted(present))}")

    return InstallationConfig(
        customer=customer,
        environment=environment,
        project=project,
        region=region,
        zone=zone,
        profile=profile,
        namespace=namespace,
        image_repository=image_repository,
        image_digest=image_digest,
        branding_name=branding_name,
        sizing=sizing,
        domain=domain.strip() if isinstance(domain, str) else None,
    )
