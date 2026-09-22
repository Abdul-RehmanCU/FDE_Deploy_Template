from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|api[_-]?key)(\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~-]+"),
)


def redact(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        if "Bearer" in pattern.pattern:
            result = pattern.sub("Bearer [REDACTED]", result)
        else:
            result = pattern.sub(r"\1\2[REDACTED]", result)
    return result


@dataclass(frozen=True)
class Result:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def require_success(self) -> "Result":
        if self.returncode:
            detail = redact(self.stderr.strip() or self.stdout.strip())
            raise RuntimeError(f"command failed ({self.returncode}): {detail}")
        return self


def executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"required executable not found: {name}")
    return path


def run(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> Result:
    if not args:
        raise ValueError("command cannot be empty")
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    result = Result(tuple(args), completed.returncode, completed.stdout, completed.stderr)
    return result.require_success() if check else result


def run_json(args: Sequence[str], **kwargs: object) -> object:
    result = run(args, **kwargs)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("command returned invalid JSON") from exc


def safe_command(args: Iterable[str]) -> str:
    return " ".join(redact(part) for part in args)
