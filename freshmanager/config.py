"""Minimal configuration and secret-masking helpers for EG-4."""

from __future__ import annotations

from pathlib import Path


API_KEY_NAME = "SEOUL_OPEN_API_KEY"
MASK = "********"


class ConfigError(ValueError):
    """Raised when the required local configuration is unavailable or empty."""


def load_api_key(env_path: Path) -> str:
    """Read the approved API key from an explicitly supplied ``.env`` path.

    Tests must pass a path inside a temporary directory. The function never
    prints the key and does not choose the repository's real ``.env`` itself.
    """

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigError("config_error: .env 파일을 읽을 수 없음") from error

    value: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, candidate = stripped.split("=", 1)
        if key.strip() == API_KEY_NAME:
            value = candidate.strip()
            break

    if not value:
        raise ConfigError(f"config_error: {API_KEY_NAME} 누락 또는 빈 값")
    return value


def mask_secret(text: str, secret: str) -> str:
    """Replace an exact secret value without exposing it in diagnostics."""

    return text.replace(secret, MASK) if secret else text
