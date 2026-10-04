"""Tests for ai/settings_file.py and the /api/ai/configure route (never touch the real .env)."""

import pytest

import app as app_module
from ai.settings_file import InvalidSettingsError, clean_key, save_ai_settings


def test_save_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nLLM_PROVIDER=anthropic\nLLM_API_KEY=\nLLM_MODEL=\n", encoding="utf-8")
    save_ai_settings(env, "gemini", "  my-secret-key  ")
    text = env.read_text(encoding="utf-8")
    assert "# comment" in text
    assert "LLM_PROVIDER=gemini" in text
    assert "LLM_API_KEY=my-secret-key" in text
    assert "LLM_MODEL=" in text


def test_save_creates_file(tmp_path):
    env = tmp_path / ".env"
    save_ai_settings(env, "groq", "abc123")
    assert env.read_text(encoding="utf-8") == "LLM_PROVIDER=groq\nLLM_API_KEY=abc123\n"


@pytest.mark.parametrize("pasted, expected", [
    ('"abc"', "abc"), ("  abc  ", "abc"), ("LLM_API_KEY=abc", "abc"), ("'abc'", "abc"),
])
def test_clean_key(pasted, expected):
    assert clean_key(pasted) == expected


@pytest.mark.parametrize("provider, key", [("gemini", ""), ("nope", "abc"), ("gemini", "has space")])
def test_invalid_settings(tmp_path, provider, key):
    with pytest.raises(InvalidSettingsError):
        save_ai_settings(tmp_path / ".env", provider, key)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "BACKEND_DIR", tmp_path)   # write to a temp .env
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_configure_route_from_localhost(client, tmp_path):
    response = client.post("/api/ai/configure", json={"provider": "gemini", "key": "abc123"})
    assert response.status_code == 200
    assert "LLM_API_KEY=abc123" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_configure_route_refuses_remote_requests(client, tmp_path):
    response = client.post("/api/ai/configure", json={"provider": "gemini", "key": "abc123"},
                           environ_base={"REMOTE_ADDR": "203.0.113.7"})
    assert response.status_code == 403
    assert not (tmp_path / ".env").exists()


def test_configure_route_rejects_bad_key(client):
    response = client.post("/api/ai/configure", json={"provider": "gemini", "key": ""})
    assert response.status_code == 400
