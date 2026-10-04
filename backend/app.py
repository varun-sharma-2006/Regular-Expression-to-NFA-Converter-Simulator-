"""
app.py - the Flask web server.

It does two jobs:
    1. Serves the frontend files (index.html, style.css, js/...) at http://127.0.0.1:5000
    2. Offers a JSON API. The browser sends a request, Python runs the automata
       algorithms, and the result goes back as JSON for the page to display.

API routes (all POST routes take and return JSON):
    POST /api/convert           {regex}                         -> all stages
    POST /api/simulate          {regex, string, automaton}      -> accepted? + path
                                (automaton = "min_dfa", "dfa" or "nfa")
    POST /api/equivalence       {regex1, regex2}                -> equivalent? + counterexample
    POST /api/operations        {regex1, regex2, operation, alphabet} -> result DFA + properties
    GET  /api/quiz?level=easy|medium|hard                       -> random practice quiz
    POST /api/verify            {regex, positives, negatives, expected}
    GET  /api/ai/status                                         -> is AI configured?
    POST /api/ai/test                                           -> send a tiny test question to the AI
    POST /api/ai/nl-to-regex    {description}                   -> regex + full pipeline
    POST /api/ai/explain        {stage, data, regex}            -> explanation text

Run it with:   python app.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

# Load the API key etc. from backend/.env BEFORE importing the AI modules.
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

from ai.builtin_explainer import explain_step_builtin       # noqa: E402
from ai.explainer import explain_step                       # noqa: E402
from ai.llm_client import (                                   # noqa: E402
    AINotConfiguredError,
    AIRequestError,
    ask_llm,
    get_model,
    get_provider,
    is_configured,
)
from ai.nl_to_regex import generate_regex                     # noqa: E402
from ai.verifier import verify_regex                          # noqa: E402
from automata.equivalence import check_equivalence            # noqa: E402
from automata.parser import EPSILON, RegexSyntaxError         # noqa: E402
from automata.pipeline import run_language_operation, run_pipeline  # noqa: E402
from automata.simulate import simulate_dfa, simulate_nfa      # noqa: E402
from quiz import make_quiz                                    # noqa: E402

FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

# Limits that keep the server responsive. Subset construction can create
# up to 2^n DFA states in the worst case, so very long regexes are refused.
MAX_REGEX_LENGTH = 100
MAX_STRING_LENGTH = 200
MAX_EXAMPLES = 50

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def error_response(message: str, status: int = 400, **extra):
    """Every error has the same JSON shape: {"error": "...", ...}."""
    body = {"error": message}
    body.update(extra)
    return jsonify(body), status


def get_json_body() -> dict:
    """Read the request body as a dict (empty dict if missing or not JSON)."""
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return body
    return {}


def read_regex(body: dict, key: str = "regex") -> str:
    """Get a regex from the body and check its length."""
    regex = str(body.get(key, ""))
    if len(regex) > MAX_REGEX_LENGTH:
        raise RegexSyntaxError(f"The regular expression is too long (max {MAX_REGEX_LENGTH} characters).")
    return regex


def read_list(body: dict, key: str) -> list[str]:
    """Get a list of example strings from the body."""
    value = body.get(key, [])
    if not isinstance(value, list):
        return []
    items = [str(item) for item in value][:MAX_EXAMPLES]
    return [item[:MAX_STRING_LENGTH] for item in items]


@app.errorhandler(RegexSyntaxError)
def handle_regex_error(error: RegexSyntaxError):
    """Any invalid regex anywhere becomes a 400 with a clear message."""
    return error_response(error.message, 400, position=error.position)


@app.errorhandler(AINotConfiguredError)
def handle_ai_not_configured(error: AINotConfiguredError):
    return error_response(str(error), 503, ai_not_configured=True)


@app.errorhandler(AIRequestError)
def handle_ai_request_error(error: AIRequestError):
    return error_response(str(error), 502)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# Part A: automata simulator
# ---------------------------------------------------------------------------

@app.post("/api/convert")
def convert():
    """Run the whole pipeline and return every stage."""
    regex = read_regex(get_json_body())
    return jsonify(run_pipeline(regex).to_dict())


@app.post("/api/simulate")
def simulate():
    """Test one string on the ε-NFA ("nfa"), the DFA ("dfa") or the minimized DFA ("min_dfa", default)."""
    body = get_json_body()
    regex = read_regex(body)
    text = str(body.get("string", ""))
    if len(text) > MAX_STRING_LENGTH:
        return error_response(f"The test string is too long (max {MAX_STRING_LENGTH} characters).")
    if text.strip() == EPSILON:
        text = ""
    result = run_pipeline(regex)
    automaton = body.get("automaton")
    if automaton == "nfa":
        return jsonify({**simulate_nfa(result.nfa, text), "kind": "nfa"})
    dfa = result.dfa if automaton == "dfa" else result.min_dfa
    return jsonify({**simulate_dfa(dfa, text), "kind": "dfa"})


@app.post("/api/equivalence")
def equivalence():
    body = get_json_body()
    return jsonify(check_equivalence(read_regex(body, "regex1"), read_regex(body, "regex2")))


@app.post("/api/operations")
def operations():
    """Complement / union / intersection / difference / symmetric difference."""
    body = get_json_body()
    operation = str(body.get("operation", ""))
    regex1 = read_regex(body, "regex1")
    regex2 = read_regex(body, "regex2") if operation != "complement" else ""
    alphabet = "".join(ch for ch in str(body.get("alphabet", "")) if ch.isalnum())[:62]
    try:
        return jsonify(run_language_operation(regex1, regex2, operation, alphabet))
    except ValueError as error:
        if isinstance(error, RegexSyntaxError):
            raise
        return error_response(str(error))


@app.get("/api/quiz")
def quiz():
    level = request.args.get("level", "medium")
    return jsonify(make_quiz(level))


# ---------------------------------------------------------------------------
# Part B: AI features
# ---------------------------------------------------------------------------

@app.post("/api/verify")
def verify():
    """The verifier uses only automata, so it works without an API key."""
    body = get_json_body()
    regex = read_regex(body)
    expected = str(body.get("expected", "") or "")[:MAX_REGEX_LENGTH]
    return jsonify(verify_regex(regex, read_list(body, "positives"), read_list(body, "negatives"), expected))


def reload_ai_settings() -> None:
    """
    Re-read backend/.env, so a key pasted into it works WITHOUT restarting
    the server. (Skipped in tests, which set their own environment.)
    """
    if not app.testing:
        load_dotenv(BACKEND_DIR / ".env", override=True)


@app.before_request
def refresh_settings_for_ai_routes():
    if request.path.startswith("/api/ai/"):
        reload_ai_settings()


@app.post("/api/ai/test")
def ai_test():
    """Check the key and the connection with a very small question."""
    reply = ask_llm("You are a connection test. Reply with exactly the word OK.", "ping")
    return jsonify({"ok": True, "provider": get_provider(), "model": get_model(), "reply": reply[:200]})


@app.get("/api/ai/status")
def ai_status():
    configured = is_configured()
    return jsonify({
        "configured": configured,
        "provider": get_provider() if configured else None,
        "model": get_model() if configured else None,
    })


@app.post("/api/ai/nl-to-regex")
def nl_to_regex():
    """English -> regex (LLM), then the regex goes through the full pipeline."""
    description = str(get_json_body().get("description", "")).strip()
    if not description:
        return error_response("Please type a description first.")
    if len(description) > 1000:
        return error_response("The description is too long (max 1000 characters).")
    generated = generate_regex(description)
    if generated["regex"] is None:
        return error_response(generated["error"], 422, attempts=generated["attempts"])
    pipeline = run_pipeline(generated["regex"]).to_dict()
    return jsonify({**generated, "pipeline": pipeline})


@app.post("/api/ai/explain")
def explain():
    """
    Explain one stage. With an API key the AI tutor answers; without one we
    return a built-in explanation made from the stage's real data.
    """
    body = get_json_body()
    stage = str(body.get("stage", ""))
    data = body.get("data", {})
    regex = str(body.get("regex", ""))[:MAX_REGEX_LENGTH]
    if not stage:
        return error_response("Missing 'stage'.")
    if not is_configured():
        return jsonify({"explanation": explain_step_builtin(stage, data), "source": "built-in"})
    return jsonify({"explanation": explain_step(stage, data, regex), "source": "ai"})


if __name__ == "__main__":
    print("AutomataAI running at http://127.0.0.1:5000")
    print("AI features:", "ON (" + get_provider() + ")" if is_configured() else "OFF (no LLM_API_KEY in backend/.env)")
    app.run(debug=True)
