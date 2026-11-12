"""
LLM Service — wraps the Google GenAI SDK.
Get your API key at: https://ai.google.dev/
"""
import json
import time
import logging
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY must be configured to use Gemini.")
    # Provider calls must have a hard upper bound. Without this, a stalled
    # network connection can leave a trip in CREATING for many minutes.
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=120_000),
    )


def chat_with_agent(conversation_history: list[dict], system_prompt: str) -> tuple[str, int, int]:
    """
    Send conversation to the configured free-tier chat model.
    Returns: (reply_text, prompt_tokens, completion_tokens)
    """
    client = _get_client()
    contents = [
        types.Content(
            role="user" if msg["role"] == "user" else "model",
            parts=[types.Part.from_text(text=msg["content"])],
        )
        for msg in conversation_history
    ]
    try:
        start = time.time()
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
        logger.info("Gemini chat request completed in %d ms", int((time.time() - start) * 1000))

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        reply = response.text
        if not reply:
            raise ValueError("Gemini returned an empty chat response.")
        return reply, prompt_tokens, completion_tokens
    except Exception:
        logger.exception("Gemini chat API error")
        raise


def generate_trip_plan_json(prompt: str) -> dict:
    """
    Ask Gemini to produce a structured JSON travel plan.
    """
    client = _get_client()
    full_prompt = f"""
{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown code blocks, no extra text.
"""
    def parse_response(response) -> dict:
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(max_output_tokens=8192),
        )
        return parse_response(response)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error from LLM: {e}\nRaw: {response.text[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        # Gemini can return 503/504 when a model is busy or the request
        # exceeds the provider deadline. Try the lighter configured model
        # before the Celery retry cycle marks the trip failed.
        error_text = str(e).upper()
        if "503" in error_text or "504" in error_text or "DEADLINE_EXCEEDED" in error_text:
            fallback_models = [settings.GEMINI_CHAT_MODEL, "gemini-3.5-flash-lite"]
            for fallback_model in dict.fromkeys(fallback_models):
                if fallback_model == settings.GEMINI_MODEL:
                    continue
                try:
                    logger.warning("Trip-plan model unavailable; retrying with %s", fallback_model)
                    fallback_response = client.models.generate_content(
                        model=fallback_model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(max_output_tokens=8192),
                    )
                    return parse_response(fallback_response)
                except Exception as fallback_error:
                    logger.warning("Fallback model %s failed: %s", fallback_model, fallback_error)
        logger.exception("generate_trip_plan_json error")
        raise
