import json, logging
from ..config import OPENAI_API_KEY

"""OpenAI service helpers.

Handles dual import path (new openai>=1.x vs legacy) and provides:
- get_client(): returns appropriate client or None if unavailable.
- check_confirmation_intent(): classify follow-up messages for pending tool action confirmation.
"""
try:
    from openai import OpenAI
    OPENAI_VERSION = 'v1'
except ImportError:  # legacy fallback
    try:
        import openai  # type: ignore
        OPENAI_VERSION = 'legacy'
    except ImportError:
        openai = None  # type: ignore
        OPENAI_VERSION = None

def get_client():
    """Return an OpenAI client instance (new SDK or legacy) or None if key/missing package."""
    if not OPENAI_API_KEY or not OPENAI_VERSION:
        return None
    return OpenAI(api_key=OPENAI_API_KEY) if OPENAI_VERSION == 'v1' else openai

def check_confirmation_intent(user_message: str, client):
    """Classify user follow-up as confirm / cancel / other.

    Strategy:
    1. Attempt model classification with constrained JSON schema.
    2. On error/timeouts, fallback to simple keyword heuristics (Indonesian + common English variants).

    Returns: {"intent": "confirm" | "cancel" | "other"}
    """
    system_prompt = """
    Analisis respons pengguna untuk konfirmasi. Balas HANYA JSON {"intent":"confirm"|"cancel"|"other"}.
    confirm: ya, lanjut, betul, ok, gas, yakin, benar, silahkan, iya, oke
    cancel: jangan, batal, tidak, stop, gajadi, cancel, enggak
    selain itu: other
    """
    if not client:
        return {"intent": "other"}
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.warning(f"check_confirmation_intent fallback: {e}")
        low = user_message.lower()
        if any(w in low for w in ["ya","lanjut","yakin","ok","betul","gas","iya","oke"]):
            return {"intent": "confirm"}
        if any(w in low for w in ["tidak","batal","jangan","stop","cancel","enggak"]):
            return {"intent": "cancel"}
        return {"intent": "other"}
