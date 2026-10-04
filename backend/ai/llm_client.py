"""
llm_client.py - the ONLY file that talks to an LLM provider.

Every other AI file calls ask_llm(system_prompt, user_message) and gets text
back, so switching provider means changing the .env file, not the code.

The app uses a FREE AI: Google Gemini by default, with Groq as a free backup.
Both offer an "OpenAI-compatible" API, so one piece of code (the `openai`
package) talks to either of them; only the web address differs.

Configuration (read from environment variables, loaded from backend/.env):
    LLM_PROVIDER   "gemini" (default, free) or "groq" (free).
                   Advanced: "openai" for OpenAI itself or any other
                   OpenAI-compatible server (e.g. Ollama) via LLM_BASE_URL.
    LLM_API_KEY    your secret key - NEVER written in the code
    LLM_MODEL      optional; a sensible default is used per provider
    LLM_BASE_URL   optional; only for other OpenAI-compatible servers

If no key is set, is_configured() returns False and the app keeps working:
only the AI buttons show "AI is not configured".
"""

from __future__ import annotations

import os

DEFAULT_PROVIDER = "gemini"

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
}

# The web address of each free provider's OpenAI-compatible API.
PRESET_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
}

# If a model is busy (503), over its free limit (429) or retired (404), the
# next model in this list is tried automatically. Every Gemini model has its
# OWN free-tier limit, so falling back also gives more free requests.
FALLBACK_MODELS = {
    "gemini": ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"],
}

# Seconds to wait for one answer. The deployed server (gunicorn) stops a
# request after 120 s, and NL -> regex may ask up to 3 times, so 30 s each.
REQUEST_TIMEOUT_SECONDS = 30

# The model that answered the last request (shown by the "Test connection" button).
last_model_used: str | None = None


class AINotConfiguredError(Exception):
    """Raised when an AI feature is used but no API key is configured."""


class AIRequestError(Exception):
    """Raised when the LLM provider returns an error (bad key, network, ...)."""


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "").strip().lower() or DEFAULT_PROVIDER


def get_model() -> str:
    model = os.getenv("LLM_MODEL", "").strip()
    if model:
        return model
    return DEFAULT_MODELS.get(get_provider(), "")


def has_key() -> bool:
    return os.getenv("LLM_API_KEY", "").strip() != ""


def is_configured() -> bool:
    """True if a provider we support is chosen and an API key is present."""
    return has_key() and get_provider() in DEFAULT_MODELS


def ask_llm(system_prompt: str, user_message: str, max_tokens: int = 2000) -> str:
    """
    Send one question to the configured LLM and return its text answer.
    `max_tokens` caps the length of the answer; callers pass a size that
    fits what they ask for.
    Raises AINotConfiguredError or AIRequestError on problems.
    """
    if has_key() and get_provider() not in DEFAULT_MODELS:
        raise AINotConfiguredError(
            f"LLM_PROVIDER '{get_provider()}' in backend/.env is not supported. "
            "Use gemini or groq (both free): click the AI badge at the top right."
        )
    if not is_configured():
        raise AINotConfiguredError(
            "AI is not configured: LLM_API_KEY in backend/.env is empty. Click the "
            "AI badge at the top right for the setup steps. Everything else still works."
        )
    return _ask_openai_compatible(system_prompt, user_message, max_tokens)


def models_to_try() -> list[str]:
    """The configured model first, then the provider's fallback models (no duplicates)."""
    models = [get_model()]
    for model in FALLBACK_MODELS.get(get_provider(), []):
        if model not in models:
            models.append(model)
    return models


def _ask_openai_compatible(system_prompt: str, user_message: str, max_tokens: int) -> str:
    """
    Call any OpenAI-compatible chat completions API with the `openai` SDK.
    If a model is busy, over its limit or retired, try the next fallback model.
    """
    global last_model_used
    import openai

    base_url = os.getenv("LLM_BASE_URL", "").strip() or PRESET_BASE_URLS.get(get_provider())
    # No automatic retries of the SAME model: free keys allow very few
    # requests per minute, so we move on to the next model instead.
    client = openai.OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=base_url,
        max_retries=0,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    problems = []   # what went wrong with each model, for the final message
    for model in models_to_try():
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            last_model_used = model
            return (response.choices[0].message.content or "").strip()
        except openai.AuthenticationError:
            raise AIRequestError("The API key was rejected. Check LLM_API_KEY in backend/.env.")
        except openai.APIConnectionError:
            raise AIRequestError("Could not reach the AI provider. Check your internet connection.")
        except openai.RateLimitError:
            problems.append(f"{model}: request limit reached")
        except openai.InternalServerError:
            problems.append(f"{model}: busy (high demand)")
        except openai.APIError as error:
            text = str(error).lower()
            # Some providers (e.g. Gemini) report a wrong key as a generic 400 error.
            if "api key" in text or "api_key" in text:
                raise AIRequestError("The API key was rejected. Check LLM_API_KEY in backend/.env.")
            if getattr(error, "status_code", None) == 404 or "not_found" in text:
                problems.append(f"{model}: not available for this key")
                continue
            raise AIRequestError(f"AI provider error: {error}")

    raise AIRequestError(
        "All AI models are busy or over the free limit right now ("
        + "; ".join(problems)
        + "). Wait one minute and try again."
    )
