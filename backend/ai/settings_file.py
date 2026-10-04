"""
settings_file.py - save the AI provider and key into backend/.env.

Used by the "Paste your key" box in the AI setup window, so nobody has to
edit the file by hand. Only the LLM_PROVIDER and LLM_API_KEY lines are
changed; every other line (comments, LLM_MODEL, ...) is kept as it is.
"""

from __future__ import annotations

from pathlib import Path

from ai.llm_client import DEFAULT_MODELS

MAX_KEY_LENGTH = 300


class InvalidSettingsError(ValueError):
    """The provider or key the user typed cannot be used."""


def clean_key(key: str) -> str:
    """Remove spaces and quotes that are often copied by accident."""
    key = key.strip().strip('"').strip("'").strip()
    if key.upper().startswith("LLM_API_KEY="):      # pasted the whole line
        key = key.split("=", 1)[1].strip()
    return key


def validate(provider: str, key: str) -> None:
    if provider not in DEFAULT_MODELS:
        raise InvalidSettingsError(f"Unknown provider '{provider}'. Choose one of: {', '.join(DEFAULT_MODELS)}.")
    if not key:
        raise InvalidSettingsError("The key is empty. Paste your API key into the box.")
    if len(key) > MAX_KEY_LENGTH or any(char.isspace() for char in key):
        raise InvalidSettingsError("That does not look like an API key (it contains spaces or is too long).")


def save_ai_settings(env_path: Path, provider: str, key: str) -> None:
    """Write LLM_PROVIDER and LLM_API_KEY into the .env file (create it if needed)."""
    key = clean_key(key)
    provider = provider.strip().lower()
    validate(provider, key)

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    new_values = {"LLM_PROVIDER": provider, "LLM_API_KEY": key}
    written = set()
    for index, line in enumerate(lines):
        name = line.split("=", 1)[0].strip()
        if name in new_values and not line.lstrip().startswith("#"):
            lines[index] = f"{name}={new_values[name]}"
            written.add(name)
    for name, value in new_values.items():
        if name not in written:
            lines.append(f"{name}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
