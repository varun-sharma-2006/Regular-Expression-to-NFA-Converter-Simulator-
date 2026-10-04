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

AI routes that call the LLM are limited per visitor (AI_REQUESTS_PER_MINUTE),
because on a deployed server every request is paid with the owner's key.

Run it with:   python app.py          (set FLASK_DEBUG=1 for auto-reload + debugger)
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

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
from ai import llm_client                                     # noqa: E402
from ai.nl_to_regex import generate_regex                     # noqa: E402
from ai.settings_file import InvalidSettingsError, save_ai_settings  # noqa: E402
from ai.verifier import verify_regex                          # noqa: E402
from automata.equivalence import check_equivalence            # noqa: E402
from automata.parser import EPSILON, RegexSyntaxError         # noqa: E402
from automata.pipeline import run_language_operation, run_pipeline  # noqa: E402
from automata.simulate import simulate_dfa, simulate_nfa      # noqa: E402
from automata.subset import AutomatonTooLargeError            # noqa: E402
from quiz import make_quiz                                    # noqa: E402

FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

# Limits that keep the server responsive. Subset construction can create
# up to 2^n DFA states in the worst case, so very long regexes are refused.
MAX_REGEX_LENGTH = 100
MAX_STRING_LENGTH = 200
MAX_EXAMPLES = 50

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

# On Render the app sits behind a proxy, so request.remote_addr would be the
# proxy's address for EVERY visitor. ProxyFix takes the real visitor address
# from the X-Forwarded-For header the proxy adds. (Render sets RENDER=true.)
if os.getenv("RENDER"):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)


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


@app.errorhandler(AutomatonTooLargeError)
def handle_automaton_too_large(error: AutomatonTooLargeError):
    return error_response(str(error), 400, too_large=True)


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

@lru_cache(maxsize=64)
def cached_pipeline(regex: str):
    """
    run_pipeline, remembered for the last 64 regexes. Testing strings sends
    the same regex again and again, so the automata are built only once.
    (Errors are not cached: an invalid regex simply raises again.)
    """
    return run_pipeline(regex)


@app.post("/api/convert")
def convert():
    """Run the whole pipeline and return every stage."""
    regex = read_regex(get_json_body())
    return jsonify(cached_pipeline(regex).to_dict())


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
    result = cached_pipeline(regex)
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


LOCAL_ADDRESSES = {"127.0.0.1", "::1", "localhost"}

# Routes that send a request to the LLM (and so cost money).
AI_LIMITED_ROUTES = {"/api/ai/test", "/api/ai/nl-to-regex", "/api/ai/explain"}
AI_REQUESTS_PER_MINUTE = int(os.getenv("AI_REQUESTS_PER_MINUTE", "10"))

# visitor address -> times of their recent AI requests. Kept in memory, so
# each gunicorn worker counts separately (2 workers -> up to 2x the limit).
ai_request_times: dict[str, deque[float]] = defaultdict(deque)
ai_request_lock = threading.Lock()


def ai_limit_reached(visitor: str) -> bool:
    """Record one AI request for `visitor`; True if they are over the limit."""
    now = time.monotonic()
    with ai_request_lock:
        if len(ai_request_times) > 10000:
            # Forget visitors with no request in the last minute (saves memory).
            for address in [a for a, t in ai_request_times.items() if not t or now - t[-1] >= 60]:
                del ai_request_times[address]
        times = ai_request_times[visitor]
        while times and now - times[0] >= 60:
            times.popleft()
        if len(times) >= AI_REQUESTS_PER_MINUTE:
            return True
        times.append(now)
        return False


@app.before_request
def refresh_settings_for_ai_routes():
    if not request.path.startswith("/api/ai/"):
        return None
    reload_ai_settings()
    # Only paid LLM calls are limited: without a key, explanations are
    # built in (free), and on your own computer you pay with your own key.
    if (
        request.path in AI_LIMITED_ROUTES
        and is_configured()
        and request.remote_addr not in LOCAL_ADDRESSES
        and ai_limit_reached(request.remote_addr or "unknown")
    ):
        return error_response(
            f"Too many AI requests: at most {AI_REQUESTS_PER_MINUTE} per minute. "
            "Please wait a moment and try again.",
            429,
        )
    return None


@app.post("/api/ai/configure")
def ai_configure():
    """
    Save the provider and key typed into the AI setup window into backend/.env.
    SAFETY: only allowed from this computer (localhost). On a public server
    (e.g. Render) requests come from the internet and are refused, so nobody
    can change the key of a deployed app.
    """
    if request.remote_addr not in LOCAL_ADDRESSES:
        return error_response("Keys can only be saved from the computer running the server.", 403)
    body = get_json_body()
    try:
        save_ai_settings(BACKEND_DIR / ".env", str(body.get("provider", "")), str(body.get("key", "")))
    except InvalidSettingsError as error:
        return error_response(str(error))
    reload_ai_settings()
    return jsonify({"saved": True, "configured": is_configured(), "provider": get_provider(), "model": get_model()})


@app.post("/api/ai/test")
def ai_test():
    """Check the key and the connection with a very small question."""
    reply = ask_llm("You are a connection test. Reply with exactly the word OK.", "ping", max_tokens=500)
    model = llm_client.last_model_used or get_model()
    return jsonify({"ok": True, "provider": get_provider(), "model": model, "reply": reply[:200]})


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
    # The debugger can run code from the browser, so it is opt-in.
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
