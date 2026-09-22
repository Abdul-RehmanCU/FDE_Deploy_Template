from pathlib import Path

from fde_cli.cli import main
from test_config import VALID


def test_validate_config_command(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "customer.yaml"
    path.write_text(VALID, encoding="utf-8")
    assert main(["validate-config", "--config", str(path)]) == 0
    assert '"valid": true' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_doctor_reports_missing_tools_without_traceback(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "customer.yaml"
    path.write_text(VALID, encoding="utf-8")
    code = main(["doctor", "--config", str(path)])
    assert code in (0, 2)
    assert '"checks"' in capsys.readouterr().out  # type: ignore[attr-defined]
