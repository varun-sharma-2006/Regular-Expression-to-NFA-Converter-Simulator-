"""Tests for automata/direct_dfa.py (regex -> DFA with followpos)."""

import pytest

from automata.direct_dfa import build_direct_dfa, build_syntax_tree
from automata.minimize import minimize_dfa
from automata.parser import parse_regex
from automata.product import are_equivalent
from automata.simulate import accepts
from tests.helpers import SAMPLE_REGEXES, all_strings, expected_match


def direct(regex):
    return build_direct_dfa(parse_regex(regex)["postfix"])


def test_textbook_followpos_for_running_example():
    # Dragon Book, Fig. 3.60: (a|b)*abb#
    _, _, symbol_at, followpos = build_syntax_tree(parse_regex("(a|b)*abb")["postfix"])
    assert symbol_at == {1: "a", 2: "b", 3: "a", 4: "b", 5: "b", 6: "#"}
    assert followpos == {1: {1, 2, 3}, 2: {1, 2, 3}, 3: {4}, 4: {5}, 5: {6}, 6: set()}


def test_root_values_for_running_example():
    root, _, _, _ = build_syntax_tree(parse_regex("(a|b)*abb")["postfix"])
    assert root.firstpos == {1, 2, 3}
    assert root.lastpos == {6}
    assert root.nullable is False


def test_running_example_gives_4_states_directly():
    # Direct method: 4 states (Thompson + subset gave 5; both minimize to 4).
    dfa, details = direct("(a|b)*abb")
    assert len(dfa.states) == 4
    assert details["dfa_table"][0]["positions"] == [1, 2, 3]
    assert dfa.accepts == {"D"}


@pytest.mark.parametrize(
    "regex, nullable",
    [("a*", True), ("a+", False), ("a?", True), ("ε", True), ("a|ε", True), ("ab", False), ("(a?)+", True)],
)
def test_nullable(regex, nullable):
    # the root is (regex).# so look at its LEFT child, the regex itself
    root, _, _, _ = build_syntax_tree(parse_regex(regex)["postfix"])
    assert root.children[0].nullable is nullable


@pytest.mark.parametrize("regex", SAMPLE_REGEXES)
def test_direct_dfa_language_matches_answer_key(regex):
    dfa, _ = direct(regex)
    for text in all_strings("abc01", 4):
        assert accepts(dfa, text) == expected_match(regex, text), (regex, text)


@pytest.mark.parametrize("regex", SAMPLE_REGEXES)
def test_both_methods_give_the_same_minimal_dfa_size(regex):
    from automata.pipeline import regex_to_min_dfa
    direct_min, _ = minimize_dfa(direct(regex)[0])
    subset_min = regex_to_min_dfa(regex)
    assert len(direct_min.states) == len(subset_min.states)
    assert are_equivalent(direct_min, subset_min)


def test_tree_has_one_edge_per_child():
    _, details = direct("(a|b)*abb")
    tree = details["tree"]
    # augmented (a|b)*abb# : 6 leaves + 1 union + 1 star + 4 concats = 12 nodes
    assert len(tree["nodes"]) == 12
    assert len(tree["edges"]) == 11       # a tree with n nodes has n-1 edges
