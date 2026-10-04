"""
parser.py - Stage 1 of the pipeline: regular expression -> postfix expression.

WHY do we convert to postfix?
    A regex like (a|b)*abb is written in *infix* form: binary operators sit
    between their operands and we need parentheses + precedence rules to know
    what applies to what. Thompson's construction (next stage) is much easier
    in *postfix* form (ab|*a.b.b.), because postfix has no parentheses and no
    precedence: we read it left to right with a stack, and every operator
    simply applies to the NFA fragment(s) on top of the stack.

The steps in this file:
    1. clean_regex               remove spaces
    2. expand_character_classes  shorthand [abc] / [a-c] -> (a|b|c)
    3. validate_regex            reject bad input early with a clear message
    4. insert_explicit_concat    make hidden concatenation visible: "ab" -> "a.b"
    5. infix_to_postfix          shunting-yard algorithm (Dijkstra): "a.b" -> "ab."
    6. parse_regex               runs 1-5 and returns everything the UI shows

Supported syntax:
    symbols    : a-z, A-Z and 0-9
    classes    : [abc] means (a|b|c), [a-d] means (a|b|c|d)  (shorthand only)
    ε          : the empty string
    operators  : |  (union)        lowest precedence
                 .  (concatenation, inserted by us, never typed by the user)
                 *  (zero or more)  \
                 +  (one or more)    } highest precedence, unary, postfix
                 ?  (zero or one)   /
    grouping   : ( )
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants: the special characters of our regex language
# ---------------------------------------------------------------------------

EPSILON = "ε"
CONCAT = "."      # explicit concatenation operator (added by insert_explicit_concat)
UNION = "|"
STAR = "*"
PLUS = "+"
OPTIONAL = "?"
OPEN_PAREN = "("
CLOSE_PAREN = ")"
OPEN_CLASS = "["
CLOSE_CLASS = "]"

# Unary operators apply to ONE operand written just before them (e.g. a*).
UNARY_OPERATORS = {STAR, PLUS, OPTIONAL}

# Binary operators combine TWO operands (e.g. a|b, a.b).
BINARY_OPERATORS = {CONCAT, UNION}

# Higher number = binds tighter. This encodes the precedence rule
#   * + ?   >   concatenation   >   |
# so that "ab*" means a(b*), and "a|bc" means a|(bc).
PRECEDENCE = {
    STAR: 3,
    PLUS: 3,
    OPTIONAL: 3,
    CONCAT: 2,
    UNION: 1,
}


class RegexSyntaxError(ValueError):
    """
    Raised when the user's regex is not valid.

    `position` is the 1-based position of the problem in the cleaned regex
    (or None when the problem is not at one specific character). The frontend
    can use it to point at the mistake.
    """

    def __init__(self, message: str, position: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position


# ---------------------------------------------------------------------------
# Small helper functions to classify characters
# ---------------------------------------------------------------------------

def is_symbol(char: str) -> bool:
    """Return True if `char` is an input symbol of the alphabet (a-z, A-Z or 0-9)."""
    is_lowercase = "a" <= char <= "z"
    is_uppercase = "A" <= char <= "Z"
    is_digit = "0" <= char <= "9"
    return is_lowercase or is_uppercase or is_digit


def symbol_kind(char: str) -> str:
    """Which group a symbol belongs to; a range like [a-z] must stay inside one group."""
    if "a" <= char <= "z":
        return "lowercase letter"
    if "A" <= char <= "Z":
        return "uppercase letter"
    return "digit"


def is_operand(char: str) -> bool:
    """
    Return True if `char` is an operand: a symbol or ε.
    Operands are the 'leaves' of the regex; operators combine them.
    """
    return is_symbol(char) or char == EPSILON


def ends_operand(char: str) -> bool:
    """
    Return True if a complete operand can END with this character.

    Examples: in "a*", "(a|b)" and "ε", the last characters '*', ')' and 'ε'
    each close a complete sub-expression. After such a character, the next
    thing may be an operator, or a new operand (which means concatenation).
    """
    return is_operand(char) or char == CLOSE_PAREN or char in UNARY_OPERATORS


def starts_operand(char: str) -> bool:
    """
    Return True if a new operand can START with this character.
    A new operand is either a symbol, ε, or a parenthesised group.
    """
    return is_operand(char) or char == OPEN_PAREN


# ---------------------------------------------------------------------------
# Step 1: cleaning
# ---------------------------------------------------------------------------

def clean_regex(regex: str) -> str:
    """
    Remove all whitespace, so "(a | b)* abb" becomes "(a|b)*abb".
    Spaces have no meaning in our regex language; removing them first means
    every later step can ignore them.
    """
    cleaned_characters = []
    for char in regex:
        if not char.isspace():
            cleaned_characters.append(char)
    return "".join(cleaned_characters)


# ---------------------------------------------------------------------------
# Step 2: character classes (a shorthand, expanded before anything else)
# ---------------------------------------------------------------------------

def expand_character_classes(regex: str) -> str:
    """
    Replace every character class by an ordinary union in parentheses:
        [abc]  -> (a|b|c)
        [a-d]  -> (a|b|c|d)        a range of consecutive symbols
        [a-c0] -> (a|b|c|0)
        [x]    -> x
    Classes are only a SHORTHAND: after this step the regex uses nothing but
    the basic operators, so no other stage needs to know about classes.
    Duplicates are removed, keeping the first occurrence.
    """
    result = []
    index = 0
    while index < len(regex):
        char = regex[index]

        if char == CLOSE_CLASS:
            raise RegexSyntaxError(f"']' at position {index + 1} has no matching '['.", index + 1)

        if char != OPEN_CLASS:
            result.append(char)
            index += 1
            continue

        # Find the closing ']' of this class.
        class_start = index
        close_index = regex.find(CLOSE_CLASS, index + 1)
        if close_index == -1:
            raise RegexSyntaxError(
                f"'[' at position {class_start + 1} is never closed with ']'.", class_start + 1
            )
        content = regex[index + 1:close_index]
        if content == "":
            raise RegexSyntaxError(
                f"Empty character class '[]' at position {class_start + 1}.", class_start + 1
            )

        symbols: list[str] = []
        position = 0
        while position < len(content):
            first = content[position]
            absolute = class_start + 2 + position  # 1-based position in the regex
            if not is_symbol(first):
                raise RegexSyntaxError(
                    f"'{first}' at position {absolute} is not allowed inside [ ]. "
                    "Only symbols and ranges like a-z are allowed.",
                    absolute,
                )
            is_range = position + 2 < len(content) and content[position + 1] == "-"
            if is_range:
                last = content[position + 2]
                if not is_symbol(last) or symbol_kind(first) != symbol_kind(last) or first > last:
                    raise RegexSyntaxError(
                        f"Invalid range '{first}-{last}' at position {absolute}. "
                        "Use ranges like a-f, A-F or 0-9 (same kind, in order).",
                        absolute,
                    )
                for code in range(ord(first), ord(last) + 1):
                    symbols.append(chr(code))
                position += 3
            else:
                symbols.append(first)
                position += 1

        unique_symbols = []
        for symbol in symbols:
            if symbol not in unique_symbols:
                unique_symbols.append(symbol)

        if len(unique_symbols) == 1:
            result.append(unique_symbols[0])
        else:
            result.append("(" + "|".join(unique_symbols) + ")")
        index = close_index + 1

    return "".join(result)


# ---------------------------------------------------------------------------
# Step 3: validation
# ---------------------------------------------------------------------------

def validate_regex(regex: str) -> None:
    """
    Check that `regex` (already cleaned) is a well-formed regular expression.
    Returns nothing if it is valid, otherwise raises RegexSyntaxError.

    We scan left to right and remember the previous character, because most
    mistakes are about what is allowed to come AFTER what. For example:
        "*a"   -> '*' has nothing before it to repeat
        "a||b" -> the second '|' has no left side
        "(a"   -> parenthesis never closed
        "()"   -> empty group (the user should write ε instead)
    Catching these here gives friendly messages instead of a crash later.
    """
    if regex == "":
        raise RegexSyntaxError(
            "The regular expression is empty. Try something like (a|b)*abb."
        )

    open_paren_count = 0          # how many '(' are still waiting for a ')'
    previous: str | None = None   # the character just before the current one

    for index, char in enumerate(regex):
        position = index + 1      # 1-based position, easier for humans to read

        # Rule 1: only characters from our alphabet and operators are allowed.
        is_known_character = (
            is_operand(char)
            or char in UNARY_OPERATORS
            or char in (UNION, OPEN_PAREN, CLOSE_PAREN)
        )
        if not is_known_character:
            raise RegexSyntaxError(
                f"Invalid character '{char}' at position {position}. "
                "Allowed: letters a-z and A-Z, digits 0-9, ε, [ ] classes, "
                "and the operators | * + ? ( ).",
                position,
            )

        # Rule 2: *, + and ? repeat the thing just before them,
        # so there must be a complete operand right before them.
        if char in UNARY_OPERATORS:
            if previous is None or not ends_operand(previous):
                raise RegexSyntaxError(
                    f"'{char}' at position {position} has nothing to apply to. "
                    "It must come right after a symbol, ε, or ')'.",
                    position,
                )

        # Rule 3: '|' needs a complete operand on its LEFT side.
        # (Its right side is checked when we see the next character / the end.)
        elif char == UNION:
            if previous is None or not ends_operand(previous):
                raise RegexSyntaxError(
                    f"'|' at position {position} is missing an expression on its left side.",
                    position,
                )

        elif char == OPEN_PAREN:
            open_paren_count += 1

        # Rule 4: ')' must match an earlier '(' and must close a non-empty group.
        elif char == CLOSE_PAREN:
            if open_paren_count == 0:
                raise RegexSyntaxError(
                    f"')' at position {position} has no matching '('.",
                    position,
                )
            if previous == OPEN_PAREN:
                raise RegexSyntaxError(
                    f"Empty parentheses '()' at position {position}. "
                    "Use ε if you mean the empty string.",
                    position,
                )
            if previous == UNION:
                raise RegexSyntaxError(
                    f"'|' at position {position - 1} is missing an expression on its right side.",
                    position - 1,
                )
            open_paren_count -= 1

        previous = char

    # Rule 5: after the whole string, every '(' must have been closed ...
    if open_paren_count > 0:
        raise RegexSyntaxError(
            f"Missing ')': {open_paren_count} '(' never closed."
        )

    # ... and the regex must not end in the middle of a union like "a|".
    if previous == UNION:
        raise RegexSyntaxError(
            f"'|' at position {len(regex)} is missing an expression on its right side.",
            len(regex),
        )


# ---------------------------------------------------------------------------
# Step 4: insert explicit concatenation
# ---------------------------------------------------------------------------

def insert_explicit_concat(regex: str) -> str:
    """
    Make concatenation visible by inserting '.' wherever it is implied.

    In "ab" the concatenation is invisible: there is no operator between a and
    b. The shunting-yard algorithm only works with operators it can SEE, so we
    insert '.' between every pair (left, right) where:
        left  ENDS an operand    (symbol, ε, ')', '*', '+', '?')   and
        right STARTS an operand  (symbol, ε, '(')

    Examples:
        ab          -> a.b
        (a|b)*abb   -> (a|b)*.a.b.b
        a(b|c)      -> a.(b|c)
        a|b         -> a|b        (no concatenation: '|' is already an operator)
    """
    result_characters = []
    for index, current in enumerate(regex):
        if index > 0:
            previous = regex[index - 1]
            if ends_operand(previous) and starts_operand(current):
                result_characters.append(CONCAT)
        result_characters.append(current)
    return "".join(result_characters)


# ---------------------------------------------------------------------------
# Step 5: infix -> postfix (shunting-yard algorithm)
# ---------------------------------------------------------------------------

def _make_step(symbol_read: str, action: str, stack: list[str], output: list[str]) -> dict:
    """
    Take a snapshot of the algorithm's state for the step-by-step table.
    We join the lists into strings so the table is easy to display.
    """
    return {
        "symbol": symbol_read,
        "action": action,
        "stack": "".join(stack),
        "output": "".join(output),
    }


def infix_to_postfix(regex_with_concat: str) -> tuple[str, list[dict]]:
    """
    Convert an infix regex (with explicit '.') to postfix using the
    shunting-yard algorithm. Returns (postfix_string, steps).

    `steps` is a list of rows {symbol, action, stack, output} that records the
    state after each character is read; the frontend shows it as a table.

    The rules, for each character we read:
      * operand (symbol or ε)  -> goes straight to the output.
      * unary operator * + ?   -> goes straight to the output. It is a postfix
                                  operator with the highest precedence, so it
                                  applies to the operand that is ALREADY at the
                                  end of the output. Nothing on the stack can
                                  bind tighter, so there is nothing to pop.
      * '('                    -> push onto the stack (marks a group start).
      * ')'                    -> pop operators to the output until '(' is on
                                  top, then throw the '(' away.
      * binary operator . or | -> first pop every operator on the stack with
                                  precedence >= this one (>= gives LEFT
                                  associativity: a|b|c = (a|b)|c), stopping at
                                  '('. Then push this operator.
      * at the end             -> pop everything left on the stack to output.

    The input must already be validated; this function assumes it is correct.
    """
    output: list[str] = []
    stack: list[str] = []
    steps: list[dict] = []

    for char in regex_with_concat:

        if is_operand(char):
            output.append(char)
            action = f"Operand '{char}': add to output"

        elif char in UNARY_OPERATORS:
            output.append(char)
            action = f"Unary operator '{char}': applies to the previous operand, add to output"

        elif char == OPEN_PAREN:
            stack.append(char)
            action = "'(': push onto stack"

        elif char == CLOSE_PAREN:
            popped_operators = []
            while stack[-1] != OPEN_PAREN:
                operator = stack.pop()
                output.append(operator)
                popped_operators.append(operator)
            stack.pop()  # discard the matching '('
            if popped_operators:
                action = (
                    f"')': pop {', '.join(popped_operators)} to output "
                    "until '(' is found, then discard '('"
                )
            else:
                action = "')': discard the matching '('"

        else:
            # A binary operator: CONCAT '.' or UNION '|'.
            popped_operators = []
            while (
                stack
                and stack[-1] != OPEN_PAREN
                and PRECEDENCE[stack[-1]] >= PRECEDENCE[char]
            ):
                operator = stack.pop()
                output.append(operator)
                popped_operators.append(operator)
            stack.append(char)
            if popped_operators:
                action = (
                    f"Operator '{char}': pop {', '.join(popped_operators)} "
                    f"(precedence >= '{char}') to output, then push '{char}'"
                )
            else:
                action = f"Operator '{char}': push onto stack"

        steps.append(_make_step(char, action, stack, output))

    # Input finished: whatever operators remain on the stack go to the output,
    # top of the stack first.
    remaining_operators = []
    while stack:
        operator = stack.pop()
        output.append(operator)
        remaining_operators.append(operator)
    if remaining_operators:
        end_action = f"End of input: pop {', '.join(remaining_operators)} to output"
    else:
        end_action = "End of input: stack is already empty"
    steps.append(_make_step("(end)", end_action, stack, output))

    postfix = "".join(output)
    return postfix, steps


# ---------------------------------------------------------------------------
# Step 6: the whole parser in one call
# ---------------------------------------------------------------------------

def parse_regex(regex: str) -> dict:
    """
    Run the full parsing stage and return every intermediate result, so the
    web page can show the conversion step by step.

    Returns a dictionary:
        original : what the user typed
        cleaned  : without spaces
        expanded : with character classes replaced by unions (same as cleaned if none)
        explicit : with explicit concatenation '.'
        postfix  : the postfix expression (input for Thompson's construction)
        steps    : the shunting-yard table

    Raises RegexSyntaxError if the regex is invalid.
    """
    cleaned = clean_regex(regex)
    expanded = expand_character_classes(cleaned)
    try:
        validate_regex(expanded)
    except RegexSyntaxError as error:
        if expanded != cleaned:
            # Positions refer to the expanded form, so show it to the user.
            raise RegexSyntaxError(f"{error.message} (in the expanded form {expanded})", error.position)
        raise
    explicit = insert_explicit_concat(expanded)
    postfix, steps = infix_to_postfix(explicit)
    return {
        "original": regex,
        "cleaned": cleaned,
        "expanded": expanded,
        "explicit": explicit,
        "postfix": postfix,
        "steps": steps,
    }
