"""Tests for quiz.py (practice mode)."""

import pytest

from automata.pipeline import regex_to_min_dfa
from automata.simulate import simulate_dfa
from quiz import make_quiz


@pytest.mark.parametrize("level", ["easy", "medium", "hard"])
@pytest.mark.parametrize("seed", range(5))
def test_quiz_answers_are_correct(level, seed):
    quiz = make_quiz(level, seed=seed)
    dfa = regex_to_min_dfa(quiz["regex"])
    questions = quiz["questions"]
    assert len(questions) == 8

    # the three "is w accepted?" questions
    for question in questions[:3]:
        text = question["question"].split("'")[1]
        expected = "yes" if simulate_dfa(dfa, text)["accepted"] else "no"
        assert question["answer"] == expected

    assert questions[4]["answer"] == str(len(dfa.states))


def test_quiz_is_reproducible_with_seed():
    assert make_quiz("medium", seed=7) == make_quiz("medium", seed=7)


@pytest.mark.parametrize("seed", range(20))
def test_quiz_regex_is_never_trivial(seed):
    regex = make_quiz("easy", seed=seed)["regex"]
    assert len(regex) >= 3
    assert any(operator in regex for operator in "|*+?")
