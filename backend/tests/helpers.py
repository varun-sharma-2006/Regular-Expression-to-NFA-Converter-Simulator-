"""
Shared helpers for the tests.

`expected_match` uses Python's built-in `re` module ONLY as an independent
"answer key" to check our own algorithms. The project itself never uses
`re`: every algorithm in automata/ is written by hand.
"""

import itertools
import re

from automata.parser import EPSILON


def all_strings(alphabet: str, max_length: int) -> list[str]:
    """Every string over `alphabet` of length 0..max_length (including "")."""
    strings = []
    for length in range(max_length + 1):
        for letters in itertools.product(alphabet, repeat=length):
            strings.append("".join(letters))
    return strings


def expected_match(our_regex: str, text: str) -> bool:
    """Answer key: does `text` fully match `our_regex`? (ε -> empty group)"""
    python_regex = our_regex.replace(EPSILON, "(?:)")
    return re.fullmatch(python_regex, text) is not None


# Regexes used across several test files.
SAMPLE_REGEXES = [
    "(a|b)*abb",
    "a*b*",
    "(ab)*",
    "a(b|c)*",
    "(a|b)*a(a|b)",
    "a+b?",
    "(a|ε)b",
    "ε",
    "a",
    "(0|1)*1",
    "((a|b)(a|b))*",
    "a?b+|c",
]
