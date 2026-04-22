"""Configuration loader with secret interpolation and friendly error reporting.

Implements FR-34..FR-37 and the design-spec §4.3/§4.5 error UX.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from radivault_gateway.config.schema import GatewayConfig


_SECRET_RE = re.compile(r"\$\{(file|env):([^}]+)\}")


class ConfigError(Exception):
    """Raised when config loading / validation fails.

    Carries a design-spec §4.5 style structured error payload.
    """

    def __init__(
        self,
        code: str,
        ko_message: str,
        en_message: str,
        *,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(f"[{code}] {en_message}")
        self.code = code
        self.ko_message = ko_message
        self.en_message = en_message
        self.details = details or {}
        self.suggestion = suggestion

    def format_human(self) -> str:
        lines = [f"[{self.code}] {self.ko_message} / {self.en_message}"]
        for key, value in self.details.items():
            lines.append(f"  {key}: {value}")
        if self.suggestion:
            lines.append(f"  수정 / Fix: {self.suggestion}")
        lines.append(
            f"  문서 / Docs: https://docs.radivault.io/gateway-agent/errors/{self.code}"
        )
        return "\n".join(lines)


def resolve_secret(raw: str, *, env: dict[str, str] | None = None) -> str:
    """Expand ``${file:/path}`` and ``${env:NAME}`` references in a string.

    Values lacking a ``${...}`` prefix are returned verbatim. Supports one
    reference per value (the dev-spec does not mandate multi-ref composition).
    """
    if not isinstance(raw, str):
        return raw
    match = _SECRET_RE.fullmatch(raw.strip())
    if match is None:
        return raw
    kind, target = match.group(1), match.group(2)
    if kind == "file":
        path = Path(target)
        if not path.exists():
            raise ConfigError(
                "ERR_CFG_010",
                f"시크릿 파일이 없습니다: {path}",
                f"Secret credential file missing: {path}",
                details={"path": str(path)},
                suggestion=f"파일을 생성하고 chmod 0600 을 적용하세요: {path}",
            )
        # Permission check is only a warning on macOS; enforced on Linux at runtime.
        try:
            data = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(
                "ERR_CFG_012",
                f"시크릿 파일을 읽을 수 없습니다: {path}",
                f"Cannot read secret file: {path}",
                details={"path": str(path), "error": str(exc)},
            ) from exc
        return data
    # env:
    source = env if env is not None else os.environ
    if target not in source:
        raise ConfigError(
            "ERR_CFG_013",
            f"환경변수가 설정되지 않았습니다: {target}",
            f"Environment variable not set: {target}",
            details={"variable": target},
            suggestion=f"해당 환경변수를 export 하거나 ${{file:...}} 참조로 전환하세요.",
        )
    return source[target]


def _expand_tree(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    if isinstance(node, str):
        return resolve_secret(node)
    return node


def _env_override(tree: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    """Apply RADIVAULT_<SECTION>__<KEY> overrides (FR-35, design-spec §4.4).

    Nesting uses ``__`` (double underscore) between levels. Values are cast
    best-effort: ``true/false`` -> bool, integers -> int, otherwise str.
    """
    prefix = "RADIVAULT_"
    for env_key, value in env.items():
        if not env_key.startswith(prefix):
            continue
        if env_key in {"RADIVAULT_CONFIG"}:
            continue
        path = env_key[len(prefix) :].lower().split("__")
        if not path or not path[0]:
            continue
        cursor: Any = tree
        for part in path[:-1]:
            if not isinstance(cursor, dict):
                break
            cursor = cursor.setdefault(part, {})
        if isinstance(cursor, dict):
            cursor[path[-1]] = _coerce(value)
    return tree


def _coerce(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def _translate_validation_error(error: ValidationError, path: Path) -> ConfigError:
    first = error.errors()[0]
    loc = ".".join(str(p) for p in first.get("loc", ()))
    msg = first.get("msg", "invalid")
    expected_type = first.get("type", "")
    input_value = first.get("input", "")
    if expected_type.endswith("_missing") or expected_type == "missing":
        return ConfigError(
            "ERR_CFG_002",
            f"필수 설정 키가 없습니다: {loc}",
            f"Required config key missing: {loc}",
            details={"file": str(path), "path": loc},
            suggestion=f"{loc} 항목을 추가하세요.",
        )
    return ConfigError(
        "ERR_CFG_003",
        "설정 검증 실패",
        "Config validation failed",
        details={
            "file": str(path),
            "path": loc,
            "current": repr(input_value),
            "expected": msg,
        },
        suggestion=f"{loc} 값을 확인하세요.",
    )


def load_config(
    path: str | Path,
    *,
    env: dict[str, str] | None = None,
    interpolate_secrets: bool = True,
) -> GatewayConfig:
    """Load and validate a gateway configuration file.

    Raises :class:`ConfigError` with a design-spec §4.5 formatted payload.
    """
    env_map = env if env is not None else dict(os.environ)
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            "ERR_CFG_000",
            f"설정 파일이 존재하지 않습니다: {path}",
            f"Config file not found: {path}",
            details={"path": str(path)},
            suggestion="RADIVAULT_CONFIG 환경변수 또는 --config 플래그를 확인하세요.",
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(
            "ERR_CFG_001",
            "설정 파일을 파싱할 수 없습니다",
            "Cannot parse config file",
            details={"file": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(
            "ERR_CFG_001",
            "설정 파일 최상위가 매핑(dict)이 아닙니다",
            "Config root must be a mapping",
            details={"file": str(path), "type": type(raw).__name__},
        )
    raw = _env_override(raw, env_map)
    if interpolate_secrets:
        try:
            raw = _expand_tree(raw)
        except ConfigError:
            raise
    try:
        return GatewayConfig.model_validate(raw)
    except ValidationError as exc:
        raise _translate_validation_error(exc, path) from exc
