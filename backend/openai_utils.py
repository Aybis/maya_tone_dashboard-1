import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .config import CURRENT_DATE

try:
    from openai import OpenAI
    OPENAI_VERSION = 'v1'
except ImportError:
    try:
        import openai
        OPENAI_VERSION = 'legacy'
    except ImportError:
        OPENAI_VERSION = None

BASE_SYSTEM_PROMPT = f"""Anda adalah asisten AI bernama Maya... (trimmed for modular file)"""

# NOTE: For brevity, the full original BASE_SYSTEM_PROMPT content should be moved here.
# In a real refactor we would paste the entire string. For now we keep the existing in app.py until migrated fully.


def init_openai_client(api_key):
    if not api_key or not OPENAI_VERSION:
        return None
    try:
        return OpenAI(api_key=api_key) if OPENAI_VERSION == 'v1' else openai
    except Exception:
        return None


def build_messages(system_prompt: str, history: List[Dict[str, str]]):
    return [{ 'role': 'system', 'content': system_prompt }] + history
