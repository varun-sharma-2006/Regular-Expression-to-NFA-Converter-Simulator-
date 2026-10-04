"""
Tests for automata/parser.py (Phase 1).

Run from the backend/ folder with:   python -m pytest -v
"""

import pytest

from automata.parser import (
    RegexSyntaxError,
    clean_regex,
    expand_character_classes,
    infix_to_postfix,
    insert_explicit_concat,
    parse_regex,
    validate_regex,
)


# ---------------------------------------------------------------------------
# clean_regex
# ---------------------------------------------------------------------------

def test_clean_regex_removes_spaces_and_tabs():
    assert clean_regex(" (a | b)*\tabb ") == "(a|b)*abb"


# ---------------------------------------------------------------------------
# validate_regex: valid inputs must NOT raise
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "regex",
    [
        "a",
        "ε",
        "(a|b)*abb",
        "a*b*",
        "(ab)*",
        "a(b|c)*",
        "(a|b)*a(a|b)",
        "a+b?",
        "0|1|01",
        "((a))",
        "a**",      # (a*)* is unusual but still a valid regex
        "a|ε",
    ],
)
def test_validate_accepts_valid_regexes(regex):
    validate_regex(regex)  # no exception means the test passes


# ---------------------------------------------------------------------------
# validate_regex: invalid inputs must raise with a helpful message
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "regex, expected_message_part",
    [
        ("", "empty"),
        ("@", "Invalid character '@'"),
        ("a.b", "Invalid character '.'"),
        ("a&b", "Invalid character '&'"),
        ("*a", "nothing to apply to"),
        ("(*a)", "nothing to apply to"),
        ("a|*b", "nothing to apply to"),
        ("|a", "left side"),
        ("a||b", "left side"),
        ("(|a)", "left side"),
        ("a|", "right side"),
        ("(a|)", "right side"),
        ("()", "Empty parentheses"),
        ("a)", "no matching '('"),
        ("(a", "Missing ')'"),
        ("((a)", "Missing ')'"),
    ],
)
def test_validate_rejects_invalid_regexes(regex, expected_message_part):
    with pytest.raises(RegexSyntaxError) as error_info:
        validate_regex(regex)
    assert expected_message_part in str(error_info.value)


def test_error_reports_position():
    with pytest.raises(RegexSyntaxError) as error_info:
        validate_regex("ab#c")
    assert error_info.value.position == 3


# ---------------------------------------------------------------------------
# insert_explicit_concat
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "regex, expected",
    [
        ("a", "a"),
        ("ab", "a.b"),
        ("a|b", "a|b"),
        ("(a|b)*abb", "(a|b)*.a.b.b"),
        ("a*b*", "a*.b*"),
        ("(ab)*", "(a.b)*"),
        ("a(b|c)*", "a.(b|c)*"),
        ("(a|b)*a(a|b)", "(a|b)*.a.(a|b)"),
        ("(a)(b)", "(a).(b)"),
        ("a?b+", "a?.b+"),
        ("aε", "a.ε"),
    ],
)
def test_insert_explicit_concat(regex, expected):
    assert insert_explicit_concat(regex) == expected


# ---------------------------------------------------------------------------
# infix_to_postfix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "regex, expected_postfix",
    [
        ("a", "a"),
        ("ab", "ab."),
        ("a|b", "ab|"),
        ("a*", "a*"),
        ("(a|b)*abb", "ab|*a.b.b."),
        ("a*b*", "a*b*."),
        ("(ab)*", "ab.*"),
        ("a(b|c)*", "abc|*."),
        ("(a|b)*a(a|b)", "ab|*a.ab|."),
        # precedence: concatenation binds tighter than union
        ("a|bc", "abc.|"),
        ("ab|c", "ab.c|"),
        # left associativity
        ("a|b|c", "ab|c|"),
        ("abc", "ab.c."),
        # star binds tighter than concatenation: ab* = a(b*)
        ("ab*", "ab*."),
        ("a+b?", "a+b?."),
        ("a|ε", "aε|"),
    ],
)
def test_infix_to_postfix(regex, expected_postfix):
    postfix, _steps = infix_to_postfix(insert_explicit_concat(regex))
    assert postfix == expected_postfix


def test_shunting_yard_steps_table():
    explicit = insert_explicit_concat("(a|b)*abb")
    postfix, steps = infix_to_postfix(explicit)

    # one row per character read, plus one final "(end)" row
    assert len(steps) == len(explicit) + 1

    # first row: '(' is pushed, output still empty
    assert steps[0]["symbol"] == "("
    assert steps[0]["stack"] == "("
    assert steps[0]["output"] == ""

    # row for ')': '|' was popped to the output and '(' discarded
    close_paren_row = steps[4]
    assert close_paren_row["symbol"] == ")"
    assert close_paren_row["stack"] == ""
    assert close_paren_row["output"] == "ab|"

    # last row: stack empty, output equals the final postfix
    assert steps[-1]["symbol"] == "(end)"
    assert steps[-1]["stack"] == ""
    assert steps[-1]["output"] == postfix


# ---------------------------------------------------------------------------
# parse_regex (whole stage)
# ---------------------------------------------------------------------------

def test_parse_regex_returns_all_stages():
    result = parse_regex("(a | b)* abb")
    assert result["original"] == "(a | b)* abb"
    assert result["cleaned"] == "(a|b)*abb"
    assert result["explicit"] == "(a|b)*.a.b.b"
    assert result["postfix"] == "ab|*a.b.b."
    assert len(result["steps"]) > 0


def test_parse_regex_raises_on_invalid_input():
    with pytest.raises(RegexSyntaxError):
        parse_regex("a||b")


# ---------------------------------------------------------------------------
# Uppercase symbols and character classes
# ---------------------------------------------------------------------------

def test_uppercase_letters_are_symbols():
    assert parse_regex("Ab*")["postfix"] == "Ab*."


@pytest.mark.parametrize(
    "regex, expected",
    [
        ("[abc]", "(a|b|c)"),
        ("[a-d]", "(a|b|c|d)"),
        ("[a-c0]", "(a|b|c|0)"),
        ("[0-2]x", "(0|1|2)x"),
        ("[x]", "x"),
        ("[aab]", "(a|b)"),           # duplicates removed
        ("[A-C]*", "(A|B|C)*"),
        ("a[bc]*d", "a(b|c)*d"),
    ],
)
def test_expand_character_classes(regex, expected):
    assert expand_character_classes(regex) == expected


@pytest.mark.parametrize(
    "regex, expected_message_part",
    [
        ("[ab", "never closed"),
        ("ab]", "no matching '['"),
        ("[]", "Empty character class"),
        ("[a|b]", "not allowed inside"),
        ("[c-a]", "Invalid range"),
        ("[a-Z]", "Invalid range"),
        ("[a-9]", "Invalid range"),
    ],
)
def test_invalid_character_classes(regex, expected_message_part):
    with pytest.raises(RegexSyntaxError) as error_info:
        parse_regex(regex)
    assert expected_message_part in str(error_info.value)


def test_parse_regex_reports_expanded_form():
    result = parse_regex("[ab]*abb")
    assert result["expanded"] == "(a|b)*abb"
    assert result["postfix"] == "ab|*a.b.b."


def test_error_after_expansion_mentions_expanded_form():
    with pytest.raises(RegexSyntaxError) as error_info:
        parse_regex("[ab]||c")
    assert "expanded form" in str(error_info.value)
