"""Tests for automata/thompson.py (Phase 2)."""

import pytest

from automata.parser import EPSILON, parse_regex
from automata.subset import epsilon_closure, move
from automata.thompson import thompson_construction
from tests.helpers import SAMPLE_REGEXES, all_strings, expected_match


def build_nfa(regex):
    return thompson_construction(parse_regex(regex)["postfix"])


def nfa_accepts(nfa, text):
    """Simulate an NFA directly: keep the SET of current states."""
    current = epsilon_closure(nfa, [nfa.start])
    for symbol in text:
        current = epsilon_closure(nfa, move(nfa, current, symbol))
    return nfa.accept in current


def test_single_symbol_has_two_states_and_one_edge():
    nfa, steps = build_nfa("a")
    assert len(nfa.states) == 2
    assert nfa.get_targets(nfa.start, "a") == {nfa.accept}
    assert steps[0]["rule"] == "Symbol"


def test_union_rule_adds_new_start_with_two_epsilon_moves():
    nfa, steps = build_nfa("a|b")
    assert len(nfa.states) == 6
    assert len(nfa.get_targets(nfa.start, EPSILON)) == 2
    assert steps[-1]["rule"] == "Union"


def test_star_rule_allows_skipping():
    nfa, _ = build_nfa("a*")
    # start can reach accept using only ε-moves (zero repetitions)
    assert nfa.accept in nfa.get_targets(nfa.start, EPSILON)


def test_plus_rule_has_no_skip_edge():
    nfa, _ = build_nfa("a+")
    assert nfa.accept not in epsilon_closure(nfa, [nfa.start])


def test_running_example_state_count():
    # (a|b)*abb: 2 states per symbol (5 symbols) + 2 for | + 2 for * = 14
    nfa, steps = build_nfa("(a|b)*abb")
    assert len(nfa.states) == 14
    assert nfa.alphabet == {"a", "b"}
    # one rule per postfix token: ab|*a.b.b. has 10 tokens
    assert len(steps) == 10


def test_accept_state_has_no_outgoing_edges():
    # Thompson property: the final accept state has no outgoing transitions
    for regex in SAMPLE_REGEXES:
        nfa, _ = build_nfa(regex)
        assert nfa.transitions[nfa.accept] == {}


@pytest.mark.parametrize("regex", SAMPLE_REGEXES)
def test_nfa_language_matches_answer_key(regex):
    nfa, _ = build_nfa(regex)
    for text in all_strings("abc01", 4):
        assert nfa_accepts(nfa, text) == expected_match(regex, text), (regex, text)


def test_each_step_lists_what_it_created():
    nfa, steps = build_nfa("(a|b)*abb")
    # every state and every edge is created by exactly one step
    all_new_states = [state for step in steps for state in step["new_states"]]
    all_new_edges = [edge for step in steps for edge in step["new_edges"]]
    assert sorted(all_new_states) == nfa.states
    assert len(all_new_edges) == len(nfa.to_dict()["edges"])
    # the union step creates 2 states and 4 ε-edges
    union_step = steps[2]
    assert union_step["rule"] == "Union"
    assert len(union_step["new_states"]) == 2
    assert len(union_step["new_edges"]) == 4
    # a concatenation step creates no state and one ε-edge
    concat_step = steps[5]
    assert concat_step["new_states"] == []
    assert len(concat_step["new_edges"]) == 1
