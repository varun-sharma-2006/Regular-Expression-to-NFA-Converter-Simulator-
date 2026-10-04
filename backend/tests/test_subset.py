"""Tests for automata/subset.py (Phase 3)."""

import pytest

from automata.parser import parse_regex
from automata.simulate import accepts
from automata.subset import (
    DEAD_STATE_NAME,
    MAX_DFA_STATES,
    AutomatonTooLargeError,
    epsilon_closure,
    make_state_name,
    subset_construction,
)
from automata.thompson import thompson_construction
from tests.helpers import SAMPLE_REGEXES, all_strings, expected_match


def build_dfa(regex):
    nfa, _ = thompson_construction(parse_regex(regex)["postfix"])
    dfa, details = subset_construction(nfa)
    return nfa, dfa, details


def test_epsilon_closure_includes_the_state_itself():
    nfa, _, _ = build_dfa("a")
    assert epsilon_closure(nfa, [nfa.accept]) == frozenset({nfa.accept})


def test_epsilon_closure_follows_chains_of_epsilon_moves():
    nfa, _, _ = build_dfa("a*")
    closure = epsilon_closure(nfa, [nfa.start])
    assert nfa.accept in closure          # start -ε-> accept
    assert len(closure) == 3              # start, inner start, accept


def test_state_names():
    assert make_state_name(0) == "A"
    assert make_state_name(25) == "Z"
    assert make_state_name(26) == "AA"


def test_running_example_gives_textbook_dfa():
    # The classic (a|b)*abb example gives 5 DFA states A..E, E accepting.
    _, dfa, details = build_dfa("(a|b)*abb")
    assert dfa.states == ["A", "B", "C", "D", "E"]
    assert dfa.accepts == {"E"}
    assert dfa.dead_state is None
    assert len(details["subset_table"]) == 5


def test_dfa_is_complete():
    for regex in SAMPLE_REGEXES:
        _, dfa, _ = build_dfa(regex)
        for state in dfa.states:
            assert set(dfa.transitions[state]) == set(dfa.alphabet)


def test_dead_state_added_when_needed():
    # in (ab)*, reading 'b' first leads nowhere -> dead state
    _, dfa, _ = build_dfa("(ab)*")
    assert dfa.dead_state == DEAD_STATE_NAME
    assert dfa.next_state(dfa.start, "b") == DEAD_STATE_NAME
    assert dfa.next_state(DEAD_STATE_NAME, "a") == DEAD_STATE_NAME


def test_epsilon_only_regex():
    _, dfa, _ = build_dfa("ε")
    assert dfa.alphabet == []
    assert accepts(dfa, "")
    assert not accepts(dfa, "a")


@pytest.mark.parametrize("regex", SAMPLE_REGEXES)
def test_dfa_language_matches_answer_key(regex):
    _, dfa, _ = build_dfa(regex)
    for text in all_strings("abc01", 4):
        assert accepts(dfa, text) == expected_match(regex, text), (regex, text)


def test_exponential_dfa_is_stopped_at_the_size_limit():
    # Each extra (a|b) doubles the DFA: 2^9 = 512 states > MAX_DFA_STATES.
    with pytest.raises(AutomatonTooLargeError, match=str(MAX_DFA_STATES)):
        build_dfa("(a|b)*a" + "(a|b)" * 8)


def test_dfa_just_under_the_size_limit_is_built():
    _, dfa, _ = build_dfa("(a|b)*a" + "(a|b)" * 7)     # 2^8 = 256 states + 1
    assert len(dfa.states) <= MAX_DFA_STATES
