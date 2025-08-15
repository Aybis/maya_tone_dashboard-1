import json, logging
from ..config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME
    # OPENAI_API_KEY  # Commented out - regular OpenAI fallback
)

"""Azure OpenAI service helpers.

Provides:
- get_client(): returns Azure OpenAI client or None if unavailable.
- check_confirmation_intent(): classify follow-up messages for pending tool action confirmation.
"""
try:
    from openai import AzureOpenAI
    # from openai import OpenAI  # Commented out - regular OpenAI

    OPENAI_VERSION = "v1"
except ImportError:  # legacy fallback
    try:
        import openai  # type: ignore

        OPENAI_VERSION = "legacy"
    except ImportError:
        openai = None  # type: ignore
        OPENAI_VERSION = None


def get_client():
    """Return an Azure OpenAI client instance or None if unavailable."""
    if not OPENAI_VERSION or not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        return None
    
    # Azure OpenAI (Active)
    if OPENAI_VERSION == "v1":
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION
        )
    else:
        # Legacy Azure OpenAI setup
        openai.api_type = "azure"
        openai.api_key = AZURE_OPENAI_API_KEY
        openai.api_base = AZURE_OPENAI_ENDPOINT
        openai.api_version = AZURE_OPENAI_API_VERSION
        return openai
    
    # Regular OpenAI (Commented out - can be enabled if needed)
    # if OPENAI_API_KEY:
    #     return OpenAI(api_key=OPENAI_API_KEY) if OPENAI_VERSION == "v1" else openai
    
    # return None


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
        # Use Azure OpenAI deployment name
        model_name = AZURE_OPENAI_DEPLOYMENT_NAME
        # model_name = AZURE_OPENAI_DEPLOYMENT_NAME if AZURE_OPENAI_API_KEY else "gpt-4o-mini"  # Commented out - regular OpenAI fallback
        
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.warning(f"check_confirmation_intent fallback: {e}")
        low = user_message.lower()
        if any(
            w in low
            for w in ["ya", "lanjut", "yakin", "ok", "betul", "gas", "iya", "oke"]
        ):
            return {"intent": "confirm"}
        if any(
            w in low for w in ["tidak", "batal", "jangan", "stop", "cancel", "enggak"]
        ):
            return {"intent": "cancel"}
        return {"intent": "other"}
