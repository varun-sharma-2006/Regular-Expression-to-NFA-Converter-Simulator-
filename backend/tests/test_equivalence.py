"""Tests for automata/equivalence.py (Phase 5)."""

import pytest

from automata.equivalence import check_equivalence
from automata.parser import RegexSyntaxError
from tests.helpers import expected_match


@pytest.mark.parametrize(
    "regex1, regex2",
    [
        ("(a|b)*", "(a*b*)*"),
        ("a*", "ε|aa*"),
        ("a+", "aa*"),
        ("a?", "a|ε"),
        ("(ab)*a", "a(ba)*"),
        ("(a|b)*abb", "(b|a)*abb"),
        ("a|b", "b|a"),
    ],
)
def test_equivalent_pairs(regex1, regex2):
    result = check_equivalence(regex1, regex2)
    assert result["equivalent"], result
    assert result["counterexample"] is None


@pytest.mark.parametrize(
    "regex1, regex2, shortest_counterexample",
    [
        ("a*", "a+", ""),               # ε is in a* but not in a+
        ("(a|b)*abb", "(a|b)*ab", "ab"),
        ("ab", "ba", "ab"),
        ("a*b*", "(a|b)*", "ba"),
        ("a", "a|c", "c"),              # different alphabets
    ],
)
def test_non_equivalent_pairs_give_shortest_counterexample(regex1, regex2, shortest_counterexample):
    result = check_equivalence(regex1, regex2)
    assert not result["equivalent"]
    assert result["counterexample"] == shortest_counterexample
    # the counterexample really separates the two languages
    word = result["counterexample"]
    assert expected_match(regex1, word) != expected_match(regex2, word)


def test_accepted_by_points_to_the_correct_regex():
    result = check_equivalence("a*", "a+")
    assert result["accepted_by"] == "regex1"
    result = check_equivalence("a+", "a*")
    assert result["accepted_by"] == "regex2"


def test_invalid_regex_raises():
    with pytest.raises(RegexSyntaxError):
        check_equivalence("a|", "a")
