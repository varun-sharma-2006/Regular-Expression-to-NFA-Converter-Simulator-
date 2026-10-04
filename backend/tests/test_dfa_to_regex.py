"""Tests for automata/dfa_to_regex.py (state elimination)."""

import pytest

from automata.dfa_to_regex import (
    dfa_to_regex,
    regex_concat,
    regex_star,
    regex_union,
    useful_states,
    uses_only_supported_symbols,
)
from automata.equivalence import check_equivalence
from automata.pipeline import regex_to_min_dfa
from tests.helpers import SAMPLE_REGEXES


@pytest.mark.parametrize(
    "function, arguments, expected",
    [
        (regex_union, (None, "a"), "a"),
        (regex_union, ("a", "a"), "a"),
        (regex_union, ("a", "b"), "a|b"),
        (regex_union, ("ε", "a"), "a?"),
        (regex_union, ("ε", "a*"), "a*"),
        (regex_union, ("ε", "ab"), "(ab)?"),
        (regex_concat, ("ε", "a"), "a"),
        (regex_concat, ("a", None), None),
        (regex_concat, ("a|b", "c"), "(a|b)c"),
        (regex_star, (None,), "ε"),
        (regex_star, ("a",), "a*"),
        (regex_star, ("a*",), "a*"),
        (regex_star, ("a+",), "a*"),
        (regex_star, ("ab",), "(ab)*"),
        (regex_star, ("(a|b)",), "(a|b)*"),
        (regex_star, ("(a)(b)",), "((a)(b))*"),
    ],
)
def test_regex_building_helpers(function, arguments, expected):
    assert function(*arguments) == expected


def test_dead_state_is_useless():
    dfa = regex_to_min_dfa("(ab)*")
    assert dfa.dead_state not in useful_states(dfa)


@pytest.mark.parametrize("regex", SAMPLE_REGEXES + ["a", "(a|b)*", "a(a|b)*b|b(a|b)*a", "(aa)*|(bbb)*"])
def test_round_trip_gives_equivalent_regex(regex):
    result, _, steps = dfa_to_regex(regex_to_min_dfa(regex))
    assert result is not None
    assert uses_only_supported_symbols(result)
    assert check_equivalence(regex, result)["equivalent"], (regex, result)


def test_every_state_is_eliminated_once():
    dfa = regex_to_min_dfa("(a|b)*abb")
    _, initial_edges, steps = dfa_to_regex(dfa)
    assert sorted(step["eliminated"] for step in steps) == sorted(dfa.states)
    assert any(edge["from"] == "start" for edge in initial_edges)
    assert steps[-1]["edges_left"][0]["from"] == "start"
    assert steps[-1]["edges_left"][0]["to"] == "final"


def test_simple_results_stay_simple():
    assert dfa_to_regex(regex_to_min_dfa("a*"))[0] == "a*"
    assert dfa_to_regex(regex_to_min_dfa("ab"))[0] == "ab"
