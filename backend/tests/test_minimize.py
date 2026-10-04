"""Tests for automata/minimize.py (Phase 4)."""

import pytest

from automata.minimize import minimize_dfa, remove_unreachable_states
from automata.pipeline import run_pipeline
from automata.simulate import accepts
from automata.subset import DFA
from tests.helpers import SAMPLE_REGEXES, all_strings, expected_match


def test_running_example_minimizes_from_5_to_4_states():
    # Textbook result: A and C are equivalent in the DFA of (a|b)*abb.
    result = run_pipeline("(a|b)*abb")
    assert len(result.dfa.states) == 5
    assert len(result.min_dfa.states) == 4
    assert ["A", "C"] in result.min_details["groups"]
    assert result.min_dfa.start == "{A,C}"


def test_pass_zero_marks_accepting_vs_non_accepting():
    result = run_pipeline("(a|b)*abb")
    pass_zero_pairs = [m["pair"] for m in result.min_details["passes"][0]["marked"]]
    # E is the only accepting state, so pass 0 marks (X, E) for every other X
    assert sorted(pass_zero_pairs) == [["A", "E"], ["B", "E"], ["C", "E"], ["D", "E"]]


@pytest.mark.parametrize(
    "regex, expected_state_count",
    [
        ("(a|b)*abb", 4),
        ("a*b*", 3),           # includes the dead state
        ("(ab)*", 3),          # includes the dead state
        ("(a|b)*", 1),
        ("(a|b)*a(a|b)", 4),   # "second-last symbol is a" needs 4 states
        ("a|a", 3),            # same as "a": start, accept, dead
    ],
)
def test_minimal_state_counts(regex, expected_state_count):
    assert len(run_pipeline(regex).min_dfa.states) == expected_state_count


def test_equivalent_regexes_give_same_size_minimal_dfa():
    assert len(run_pipeline("(a|b)*").min_dfa.states) == len(run_pipeline("(a*b*)*").min_dfa.states)


def test_remove_unreachable_states():
    dfa = DFA(
        states=["A", "B", "Z"],
        alphabet=["a"],
        start="A",
        accepts={"B"},
        transitions={"A": {"a": "B"}, "B": {"a": "A"}, "Z": {"a": "A"}},
    )
    cleaned, removed = remove_unreachable_states(dfa)
    assert removed == ["Z"]
    assert cleaned.states == ["A", "B"]


def test_minimizing_twice_changes_nothing():
    once = run_pipeline("(a|b)*a(a|b)").min_dfa
    twice, _ = minimize_dfa(once)
    assert len(twice.states) == len(once.states)


@pytest.mark.parametrize("regex", SAMPLE_REGEXES)
def test_minimized_language_matches_answer_key(regex):
    min_dfa = run_pipeline(regex).min_dfa
    for text in all_strings("abc01", 5):
        assert accepts(min_dfa, text) == expected_match(regex, text), (regex, text)
