from fde_cli.process import redact, safe_command


def test_redacts_secret_like_values() -> None:
    value = "password=hunter2 token:abc api_key = xyz Authorization: Bearer eyJ.test"
    output = redact(value)
    assert "hunter2" not in output
    assert "abc" not in output
    assert "xyz" not in output
    assert "eyJ.test" not in output


def test_safe_command_preserves_non_secret_arguments() -> None:
    assert safe_command(["terraform", "plan", "-input=false"]) == "terraform plan -input=false"
