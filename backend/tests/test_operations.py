"""Tests for automata/operations.py, automata/product.py and run_language_operation."""

import pytest

from automata.operations import (
    complement_dfa,
    count_strings,
    describe_language,
    is_empty,
    is_infinite,
    shortest_strings,
)
from automata.pipeline import regex_to_min_dfa, run_language_operation
from automata.product import complete_dfa, run_dfa
from automata.simulate import simulate_nfa
from automata.thompson import thompson_construction
from automata.parser import parse_regex
from tests.helpers import all_strings, expected_match

# ---------------------------------------------------------------------------
# Language operations, checked against the answer key on every short string
# ---------------------------------------------------------------------------

PAIRS = [("(a|b)*abb", "(a|b)*b"), ("a*b*", "(ab)*"), ("a(b|c)*", "(a|b)*a(a|b)"), ("a+", "ε|b")]

RULES = {
    "union": lambda in1, in2: in1 or in2,
    "intersection": lambda in1, in2: in1 and in2,
    "difference": lambda in1, in2: in1 and not in2,
    "symmetric_difference": lambda in1, in2: in1 != in2,
}


@pytest.mark.parametrize("regex1, regex2", PAIRS)
@pytest.mark.parametrize("operation", list(RULES))
def test_binary_operations(regex1, regex2, operation):
    result = run_language_operation(regex1, regex2, operation)
    dfa = result["result_dfa"]
    # rebuild a tiny DFA object from the dictionary to run strings on it
    from automata.subset import DFA
    transitions = {}
    for edge in dfa["edges"]:
        transitions.setdefault(edge["from"], {})[edge["symbol"]] = edge["to"]
    for state in dfa["states"]:
        transitions.setdefault(state, {})
    result_dfa = DFA(dfa["states"], dfa["alphabet"], dfa["start"], set(dfa["accepts"]), transitions)
    for text in all_strings("abc", 4):
        expected = RULES[operation](expected_match(regex1, text), expected_match(regex2, text))
        assert run_dfa(result_dfa, text) == expected, (operation, regex1, regex2, text)


def test_complement_needs_alphabet():
    # complement of a* over {a} is empty; over {a, b} it is "contains a b"
    over_a = run_language_operation("a*", "", "complement")
    assert over_a["properties"]["empty"]
    over_ab = run_language_operation("a*", "", "complement", "b")
    assert over_ab["properties"]["shortest_strings"][:3] == ["b", "ab", "ba"]


def test_complement_of_complete_dfa():
    dfa = regex_to_min_dfa("(a|b)*abb")
    complement = complement_dfa(dfa)
    for text in all_strings("ab", 5):
        assert run_dfa(complement, text) != run_dfa(dfa, text)


def test_complete_dfa_adds_dead_state_for_new_symbol():
    dfa = complete_dfa(regex_to_min_dfa("a*"), ["b"])
    assert dfa.alphabet == ["a", "b"]
    assert dfa.dead_state is not None
    assert dfa.next_state(dfa.start, "b") == dfa.dead_state


def test_intersection_can_be_empty():
    result = run_language_operation("(a|b)*abb", "(a|b)(a|b)", "intersection")
    assert result["properties"]["empty"]
    assert result["regex_back"]["regex"] is None


def test_product_table_lists_pairs():
    result = run_language_operation("a*", "b*", "union")
    assert result["product_table"][0]["pair"] is not None
    assert result["product_states"] >= 2


def test_unknown_operation():
    with pytest.raises(ValueError):
        run_language_operation("a", "b", "concatenate")


# ---------------------------------------------------------------------------
# Language properties
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "regex, infinite, count",
    [
        ("(a|b)*abb", True, None),
        ("a|bc", False, 2),
        ("(a|b)(a|b)", False, 4),
        ("a?b?", False, 4),         # ε, a, b, ab
        ("ε", False, 1),
        ("ab+", True, None),
    ],
)
def test_finite_or_infinite(regex, infinite, count):
    dfa = regex_to_min_dfa(regex)
    assert is_infinite(dfa) is infinite
    if count is not None:
        assert count_strings(dfa) == count


def test_shortest_strings_in_order():
    dfa = regex_to_min_dfa("(a|b)*abb")
    assert shortest_strings(dfa, 4) == ["abb", "aabb", "babb", "aaabb"]
    assert shortest_strings(regex_to_min_dfa("a*"), 3) == ["", "a", "aa"]


def test_describe_language():
    description = describe_language(regex_to_min_dfa("a?b?"))
    assert description["finite"] and description["count"] == 4
    assert description["accepts_empty_string"]
    assert description["shortest_strings"][0] == "ε"


def test_empty_language_detection():
    dfa = complement_dfa(regex_to_min_dfa("a*"))
    assert is_empty(dfa)


# ---------------------------------------------------------------------------
# NFA simulation
# ---------------------------------------------------------------------------

def nfa_for(regex):
    return thompson_construction(parse_regex(regex)["postfix"])[0]


@pytest.mark.parametrize("regex", ["(a|b)*abb", "a*b*", "(ab)*", "a+b?", "(a|ε)b"])
def test_nfa_simulation_matches_answer_key(regex):
    nfa = nfa_for(regex)
    for text in all_strings("abc", 4):
        assert simulate_nfa(nfa, text)["accepted"] == expected_match(regex, text), (regex, text)


def test_nfa_simulation_records_sets():
    nfa = nfa_for("(a|b)*abb")
    run = simulate_nfa(nfa, "abb")
    assert len(run["sets"]) == 4
    assert run["sets"][0] == [0, 2, 4, 6, 7, 8]     # ε-closure of the start = DFA state A
    assert nfa.accept in run["sets"][-1]
    assert run["path"][0].startswith("{q0")


def test_nfa_simulation_stops_on_empty_set():
    run = simulate_nfa(nfa_for("ab"), "ba")
    assert not run["accepted"]
    assert run["sets"][-1] == []
