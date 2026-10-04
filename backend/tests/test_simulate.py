"""Tests for automata/simulate.py (Phase 4)."""

import pytest

from automata.pipeline import regex_to_min_dfa
from automata.simulate import simulate_dfa


@pytest.mark.parametrize(
    "regex, accepted_strings, rejected_strings",
    [
        ("(a|b)*abb", ["abb", "aabb", "babb", "ababb"], ["", "ab", "abba", "bbb"]),
        ("a*b*", ["", "a", "b", "aab", "abbb"], ["ba", "aba"]),
        ("(ab)*", ["", "ab", "abab"], ["a", "b", "aba", "ba"]),
        ("a(b|c)*", ["a", "ab", "acbc"], ["", "b", "aa"]),
        ("(a|b)*a(a|b)", ["aa", "ab", "baa", "bbab"], ["", "a", "ba", "abb"]),
    ],
)
def test_accept_and_reject(regex, accepted_strings, rejected_strings):
    dfa = regex_to_min_dfa(regex)
    for text in accepted_strings:
        assert simulate_dfa(dfa, text)["accepted"], text
    for text in rejected_strings:
        assert not simulate_dfa(dfa, text)["accepted"], text


def test_path_has_one_more_state_than_symbols():
    dfa = regex_to_min_dfa("(a|b)*abb")
    result = simulate_dfa(dfa, "aabb")
    assert len(result["path"]) == 5
    assert result["path"][0] == dfa.start
    assert len(result["steps"]) == 4
    assert result["steps"][0]["symbol"] == "a"


def test_symbol_outside_alphabet_is_rejected_with_reason():
    dfa = regex_to_min_dfa("(a|b)*abb")
    result = simulate_dfa(dfa, "abc")
    assert not result["accepted"]
    assert "'c'" in result["reason"]
    assert len(result["path"]) == 3   # stopped before 'c'


def test_dead_state_reason():
    dfa = regex_to_min_dfa("(ab)*")
    result = simulate_dfa(dfa, "bab")
    assert not result["accepted"]
    assert "dead state" in result["reason"]
