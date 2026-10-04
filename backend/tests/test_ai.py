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
    monkeypatch.setattr(nl_to_regex, "ask_llm", lambda system, message: "(a|b)*abb")
    result = nl_to_regex.generate_regex("ends with abb")
    assert result["regex"] == "(a|b)*abb"
    assert len(result["attempts"]) == 1


def test_generate_regex_retries_after_invalid_reply(monkeypatch):
    replies = iter(["(a|b)*ab{2}", "(a|b)*abb"])   # first reply uses forbidden { }
    received_messages = []

    def fake_llm(system, message):
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
    monkeypatch.setattr(nl_to_regex, "ask_llm", lambda system, message: "not a regex!")
    result = nl_to_regex.generate_regex("anything")
    assert result["regex"] is None
    assert len(result["attempts"]) == nl_to_regex.MAX_ATTEMPTS
