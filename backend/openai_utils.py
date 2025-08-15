import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .config import (
    CURRENT_DATE,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME
)

try:
    from openai import AzureOpenAI
    # from openai import OpenAI  # Commented out - regular OpenAI

    OPENAI_VERSION = "v1"
except ImportError:
    try:
        import openai

        OPENAI_VERSION = "legacy"
    except ImportError:
        OPENAI_VERSION = None

BASE_SYSTEM_PROMPT = (
    f"""Anda adalah asisten AI bernama Maya... (trimmed for modular file)"""
)

# NOTE: For brevity, the full original BASE_SYSTEM_PROMPT content should be moved here.
# In a real refactor we would paste the entire string. For now we keep the existing in app.py until migrated fully.


def init_openai_client(api_key=None):
    if not OPENAI_VERSION or not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        return None
    
    try:
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
        # elif api_key:
        #     return OpenAI(api_key=api_key) if OPENAI_VERSION == "v1" else openai
        
        # return None
    except Exception:
        return None


def build_messages(system_prompt: str, history: List[Dict[str, str]]):
    return [{"role": "system", "content": system_prompt}] + history
