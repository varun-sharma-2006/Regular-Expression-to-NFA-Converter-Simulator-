"""
Tests for the ai/ package (Phase 7).

The real LLM is replaced by a fake function (monkeypatch), so these tests
need no API key and no internet, and they always give the same result.
"""

import pytest

import ai.nl_to_regex as nl_to_regex
from ai.llm_client import AINotConfiguredError, ask_llm, is_configured
from ai.verifier import verify_regex


# ---------------------------------------------------------------------------
# Verifier (no AI involved)
# ---------------------------------------------------------------------------

def test_verifier_correct_with_examples_and_expected():
    result = verify_regex("(a|b)*abb", ["abb", "babb"], ["ab", "ε"], "(b|a)*abb")
    assert result["verdict"] == "correct"
    assert all(r["passed"] for r in result["examples"])
    assert result["equivalence"]["equivalent"]


def test_verifier_catches_failed_example():
    result = verify_regex("(a|b)*ab", ["abb"], [], None)
    assert result["verdict"] == "wrong"
    assert "'abb'" in result["message"]


def test_verifier_gives_counterexample():
    result = verify_regex("a*", [], [], "a+")
    assert result["verdict"] == "wrong"
    assert result["equivalence"]["counterexample"] == ""


def test_verifier_epsilon_example_means_empty_string():
    result = verify_regex("a*", ["ε"], [], None)
    assert result["examples"][0]["passed"]
    assert result["examples"][0]["string"] == "ε"


def test_verifier_reports_invalid_expected_regex():
    result = verify_regex("a*", [], [], "a||b")
    assert result["verdict"] == "error"


def test_verifier_with_nothing_to_check():
    assert verify_regex("a*", [], [], "")["verdict"] == "nothing"


# ---------------------------------------------------------------------------
# LLM client without a key
# ---------------------------------------------------------------------------

def test_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert not is_configured()
    with pytest.raises(AINotConfiguredError):
        ask_llm("system", "hello")


# ---------------------------------------------------------------------------
# Natural language -> regex, with a fake LLM
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "llm_reply, expected",
    [
        ("(a|b)*abb", "(a|b)*abb"),
        ("```\n(a|b)*abb\n```", "(a|b)*abb"),
        ("Regex: (a|b)*abb", "(a|b)*abb"),
        ("`a*`", "a*"),
    ],
)
def test_clean_llm_output(llm_reply, expected):
    assert nl_to_regex.clean_llm_output(llm_reply) == expected


def test_generate_regex_accepts_valid_reply(monkeypatch):
    monkeypatch.setattr(nl_to_regex, "ask_llm", lambda system, message, max_tokens=None: "(a|b)*abb")
    result = nl_to_regex.generate_regex("ends with abb")
    assert result["regex"] == "(a|b)*abb"
    assert len(result["attempts"]) == 1


def test_generate_regex_retries_after_invalid_reply(monkeypatch):
    replies = iter(["(a|b)*ab{2}", "(a|b)*abb"])   # first reply uses forbidden { }
    received_messages = []

    def fake_llm(system, message, max_tokens=None):
        received_messages.append(message)
        return next(replies)

    monkeypatch.setattr(nl_to_regex, "ask_llm", fake_llm)
    result = nl_to_regex.generate_regex("ends with abb")
    assert result["regex"] == "(a|b)*abb"
    assert len(result["attempts"]) == 2
    assert not result["attempts"][0]["valid"]
    # the retry message tells the LLM what was wrong
    assert "Invalid character '{'" in received_messages[1]


def test_generate_regex_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(nl_to_regex, "ask_llm", lambda system, message, max_tokens=None: "not a regex!")
    result = nl_to_regex.generate_regex("anything")
    assert result["regex"] is None
    assert len(result["attempts"]) == nl_to_regex.MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Model fallback (fake OpenAI client, no network)
# ---------------------------------------------------------------------------

class _FakeCompletions:
    def __init__(self, failures):
        self.failures = failures      # model name -> exception to raise
        self.tried = []

    def create(self, model, **kwargs):
        self.tried.append(model)
        if model in self.failures:
            raise self.failures[model]
        message = type("Message", (), {"content": f"answer from {model}"})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


def _openai_error(cls, status):
    import httpx2 as httpx   # the HTTP library used by the openai SDK
    import openai
    request = httpx.Request("POST", "https://example.test")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


@pytest.fixture
def fake_gemini(monkeypatch):
    import openai
    from ai import llm_client
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    holder = {}

    def make_client(**kwargs):
        client = type("Client", (), {})()
        client.chat = type("Chat", (), {})()
        client.chat.completions = holder["completions"]
        return client

    monkeypatch.setattr(openai, "OpenAI", make_client)
    return holder


def test_busy_model_falls_back_to_next(fake_gemini):
    import openai
    from ai import llm_client
    fake_gemini["completions"] = _FakeCompletions({
        "gemini-3.8-flash": _openai_error(openai.InternalServerError, 503),
        "gemini-3.7-flash": _openai_error(openai.RateLimitError, 429),
    })
    assert ask_llm("s", "m") == "answer from gemini-3.5-flash"
    assert llm_client.last_model_used == "gemini-3.5-flash"
    assert fake_gemini["completions"].tried == ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"]


def test_all_models_busy_gives_clear_message(fake_gemini):
    import openai
    from ai.llm_client import AIRequestError, models_to_try
    fake_gemini["completions"] = _FakeCompletions(
        {model: _openai_error(openai.InternalServerError, 503) for model in models_to_try()}
    )
    with pytest.raises(AIRequestError) as error_info:
        ask_llm("s", "m")
    assert "Wait one minute" in str(error_info.value)


def test_wrong_key_stops_immediately(fake_gemini):
    import openai
    from ai.llm_client import AIRequestError
    fake_gemini["completions"] = _FakeCompletions(
        {"gemini-3.8-flash": _openai_error(openai.AuthenticationError, 401)}
    )
    with pytest.raises(AIRequestError, match="key was rejected"):
        ask_llm("s", "m")
    assert fake_gemini["completions"].tried == ["gemini-3.8-flash"]


def test_default_provider_is_free_gemini(monkeypatch):
    from ai import llm_client
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm_client.get_provider() == "gemini"
    assert llm_client.get_model() == llm_client.DEFAULT_MODELS["gemini"]


def test_unsupported_provider_gives_clear_message(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")      # removed: only free providers now
    monkeypatch.setenv("LLM_API_KEY", "x")
    assert not is_configured()
    with pytest.raises(AINotConfiguredError, match="not supported"):
        ask_llm("system", "hello")
