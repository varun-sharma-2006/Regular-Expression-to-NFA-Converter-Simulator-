"""
Random ("fuzz") testing of the whole pipeline.

Hand-written tests only check examples we thought of. Here we GENERATE
hundreds of random regexes and check every one of them against an
independent answer key (Python's `re`, used only inside tests).

The random generator uses a fixed seed, so every run tests the same regexes
and a failure can always be reproduced.

For each random regex we check:
    1. the DFA, the minimized DFA and the DIRECT (followpos) DFA agree with
       the answer key on every string over {a, b, c} of length 0..5;
    2. the minimized DFA really is minimal: minimizing it again removes nothing;
    3. the equivalence checker proves the DFA and minimized DFA are the same
       language, and that the regex is equivalent to itself;
    4. DFA -> regex (state elimination) gives a regex PROVED equivalent;
    5. language operations on neighbouring random regexes agree with the
       answer key (intersection, union, difference).
"""

import random

import pytest

from automata.dfa_to_regex import dfa_to_regex
from automata.equivalence import are_equivalent, check_equivalence
from automata.minimize import minimize_dfa
from automata.operations import combine_dfas
from automata.pipeline import regex_to_min_dfa, run_pipeline
from automata.product import run_dfa
from automata.simulate import accepts
from tests.helpers import all_strings, expected_match

NUMBER_OF_REGEXES = 500
RANDOM_SEED = 2024
TEST_STRINGS = all_strings("abc", 5)   # 364 strings, including ε


def random_regex(generator: random.Random, depth: int) -> str:
    """
    Build a random regex recursively. Smaller `depth` = simpler regex.
    Every operator of our syntax can appear: concatenation, |, *, +, ?, ( ), ε.
    """
    if depth == 0 or generator.random() < 0.3:
        return generator.choice(["a", "b", "c", "ε"])
    kind = generator.choice(["concat", "union", "star", "plus", "optional", "group"])
    if kind == "concat":
        return random_regex(generator, depth - 1) + random_regex(generator, depth - 1)
    if kind == "union":
        return random_regex(generator, depth - 1) + "|" + random_regex(generator, depth - 1)
    if kind == "group":
        return "(" + random_regex(generator, depth - 1) + ")"
    operator = {"star": "*", "plus": "+", "optional": "?"}[kind]
    return "(" + random_regex(generator, depth - 1) + ")" + operator


def make_random_regexes() -> list[str]:
    generator = random.Random(RANDOM_SEED)
    return [random_regex(generator, 4) for _ in range(NUMBER_OF_REGEXES)]


RANDOM_REGEXES = make_random_regexes()


def test_generator_covers_every_operator():
    """Sanity check: the random regexes really use all of our syntax."""
    all_text = "".join(RANDOM_REGEXES)
    for symbol in ["a", "b", "c", "ε", "|", "*", "+", "?", "("]:
        assert symbol in all_text


@pytest.mark.parametrize("regex", RANDOM_REGEXES)
def test_random_regex(regex):
    result = run_pipeline(regex)

    # 1. Both DFAs agree with the independent answer key on every test string.
    for text in TEST_STRINGS:
        expected = expected_match(regex, text)
        assert accepts(result.dfa, text) == expected, (regex, text, "DFA")
        assert accepts(result.min_dfa, text) == expected, (regex, text, "minimized DFA")
        assert accepts(result.direct_dfa, text) == expected, (regex, text, "direct DFA")

    # 2. The minimized DFA cannot be made any smaller.
    minimized_again, _ = minimize_dfa(result.min_dfa)
    assert len(minimized_again.states) == len(result.min_dfa.states), regex

    # 3. Minimization did not change the language (an exact proof, not sampling),
    #    and a regex is always equivalent to itself.
    assert are_equivalent(result.dfa, result.min_dfa), regex
    assert check_equivalence(regex, regex)["equivalent"], regex

    # 4. Converting the minimized DFA back to a regex gives the same language.
    regex_back, _, _ = dfa_to_regex(result.min_dfa)
    assert regex_back is not None, regex
    assert are_equivalent(regex_to_min_dfa(regex_back), result.min_dfa), (regex, regex_back)


OPERATION_RULES = {
    "intersection": lambda in1, in2: in1 and in2,
    "union": lambda in1, in2: in1 or in2,
    "difference": lambda in1, in2: in1 and not in2,
}


@pytest.mark.parametrize("index", range(0, 100))
def test_random_language_operations(index):
    regex1 = RANDOM_REGEXES[index]
    regex2 = RANDOM_REGEXES[index + 1]
    dfa1 = regex_to_min_dfa(regex1)
    dfa2 = regex_to_min_dfa(regex2)
    for operation, rule in OPERATION_RULES.items():
        product, _ = combine_dfas(dfa1, dfa2, operation)
        for text in all_strings("abc", 4):
            expected = rule(expected_match(regex1, text), expected_match(regex2, text))
            assert run_dfa(product, text) == expected, (operation, regex1, regex2, text)
