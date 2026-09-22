from pathlib import Path

import pytest

from fde_cli.config import ConfigurationError, load_config


VALID = """
customer: acme
environment: staging
project: fdetemplate
region: northamerica-northeast1
zone: northamerica-northeast1-a
profile: demo
namespace: acme-staging
image_repository: northamerica-northeast1-docker.pkg.dev/fdetemplate/fde/api
image_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
frontend_image_repository: northamerica-northeast1-docker.pkg.dev/fdetemplate/fde/frontend
frontend_image_digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
app_version: test-version
branding:
  name: Acme Directory
sizing:
  api_replicas: 2
  worker_replicas: 1
  api_cpu: 250m
  api_memory: 384Mi
  worker_cpu: 250m
  worker_memory: 384Mi
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "customer.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_demo_configuration(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, VALID))
    assert config.immutable_image.endswith("@" + config.image_digest)
    assert config.release == "fde-acme-staging"
    assert len(config.fingerprint) == 16


@pytest.mark.parametrize("key", ["password", "secret", "token", "private_key", "api_key"])
def test_rejects_embedded_secrets(tmp_path: Path, key: str) -> None:
    with pytest.raises(ConfigurationError, match="forbidden"):
        load_config(write(tmp_path, VALID + f"\n{key}: unsafe\n"))


def test_demo_location_is_fixed(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="Montréal"):
        load_config(write(tmp_path, VALID.replace("northamerica-northeast1-a", "us-east1-b")))


def test_requires_digest(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="immutable"):
        load_config(write(tmp_path, VALID.replace("sha256:" + "a" * 64, "latest")))


def test_demo_rejects_public_domain(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="forbids a domain"):
        load_config(write(tmp_path, VALID + "\ndomain: demo.example.ca\n"))
