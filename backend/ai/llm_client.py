"""
llm_client.py - the ONLY file that talks to an LLM provider.

Every other AI file calls ask_llm(system_prompt, user_message) and gets text
back, so switching provider means changing the .env file, not the code.

Configuration (read from environment variables, loaded from backend/.env):
    LLM_PROVIDER   "anthropic" (default), "gemini", "groq" or "openai"
                   gemini and groq have FREE API keys and need no other setting.
                   "openai" also works with any OpenAI-compatible server
                   (OpenRouter, Ollama, ...) via LLM_BASE_URL.
    LLM_API_KEY    your secret key - NEVER written in the code
    LLM_MODEL      optional; a sensible default is used per provider
    LLM_BASE_URL   optional; only for other OpenAI-compatible servers

If no key is set, is_configured() returns False and the app keeps working:
only the AI buttons show "AI is not configured".
"""

from __future__ import annotations

import os

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
}

# Gemini and Groq offer OpenAI-compatible endpoints, so the same client code
# works for them; only the address differs.
PRESET_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
}

# Anthropic models that support the server-side refusal fallback option.
_MODELS_WITH_FALLBACKS = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")


class AINotConfiguredError(Exception):
    """Raised when an AI feature is used but no API key is configured."""


class AIRequestError(Exception):
    """Raised when the LLM provider returns an error (bad key, network, ...)."""


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").strip().lower()


def get_model() -> str:
    model = os.getenv("LLM_MODEL", "").strip()
    if model:
        return model
    return DEFAULT_MODELS.get(get_provider(), "")


def is_configured() -> bool:
    """True if a provider we support is chosen and an API key is present."""
    has_key = os.getenv("LLM_API_KEY", "").strip() != ""
    return has_key and get_provider() in DEFAULT_MODELS


def ask_llm(system_prompt: str, user_message: str, max_tokens: int = 16000) -> str:
    """
    Send one question to the configured LLM and return its text answer.
    Raises AINotConfiguredError or AIRequestError on problems.
    """
    if not is_configured():
        raise AINotConfiguredError(
            "AI is not configured: LLM_API_KEY in backend/.env is empty. Click the "
            "AI badge at the top right for the setup steps. Everything else still works."
        )
    provider = get_provider()
    if provider == "anthropic":
        return _ask_anthropic(system_prompt, user_message, max_tokens)
    return _ask_openai_compatible(system_prompt, user_message, max_tokens)


def _ask_anthropic(system_prompt: str, user_message: str, max_tokens: int) -> str:
    """Call Claude with the official `anthropic` SDK."""
    import anthropic  # imported here so the app runs even if it isn't installed

    client = anthropic.Anthropic(api_key=os.getenv("LLM_API_KEY"))
    model = get_model()
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    try:
        if model.startswith(_MODELS_WITH_FALLBACKS):
            # If the model declines a request, the API retries it on a
            # suitable fallback model inside the same call.
            response = client.beta.messages.create(
                **request,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        else:
            response = client.messages.create(**request)
    except anthropic.AuthenticationError:
        raise AIRequestError("The API key was rejected. Check LLM_API_KEY in backend/.env.")
    except anthropic.RateLimitError:
        raise AIRequestError("Rate limit reached. Wait a moment and try again.")
    except anthropic.APIConnectionError:
        raise AIRequestError("Could not reach the AI provider. Check your internet connection.")
    except anthropic.APIStatusError as error:
        raise AIRequestError(f"AI provider error ({error.status_code}): {error.message}")

    if response.stop_reason == "refusal":
        raise AIRequestError("The AI declined this request.")

    # The answer is a list of content blocks; we keep only the text blocks.
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _ask_openai_compatible(system_prompt: str, user_message: str, max_tokens: int) -> str:
    """Call any OpenAI-compatible chat completions API with the `openai` SDK."""
    import openai

    base_url = os.getenv("LLM_BASE_URL", "").strip() or PRESET_BASE_URLS.get(get_provider())
    client = openai.OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=get_model(),
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
    except openai.AuthenticationError:
        raise AIRequestError("The API key was rejected. Check LLM_API_KEY in backend/.env.")
    except openai.APIConnectionError:
        raise AIRequestError("Could not reach the AI provider. Check LLM_BASE_URL / internet.")
    except openai.APIError as error:
        # Some providers (e.g. Gemini) report a wrong key as a generic 400 error.
        if "api key" in str(error).lower() or "api_key" in str(error).lower():
            raise AIRequestError("The API key was rejected. Check LLM_API_KEY in backend/.env.")
        raise AIRequestError(f"AI provider error: {error}")
    return (response.choices[0].message.content or "").strip()
