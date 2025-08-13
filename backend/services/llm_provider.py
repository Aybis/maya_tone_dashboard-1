"""Provider factory & classification helper (compact version).

Actual provider implementations live under services/providers/*. This file is
intentionally small so future providers only require adding to _PROVIDER_MAP.
"""
import os, logging
from typing import Optional, Dict, Type
from .providers.base import BaseProvider
from .providers.openai_provider import OpenAIProvider
from .providers.azure_provider import AzureOpenAIProvider
from .providers.gemini_provider import GeminiProvider
from .provider_logging import LoggingProvider

DEFAULT_PROVIDER = os.getenv('DEFAULT_LLM_PROVIDER', 'gemini').lower()

_PROVIDER_MAP: Dict[str, Type[BaseProvider]] = {
    'openai': OpenAIProvider,
    'azure': AzureOpenAIProvider,
    'gemini': GeminiProvider,
}

def get_provider(name: Optional[str]) -> Optional[BaseProvider]:
    n = (name or DEFAULT_PROVIDER or 'gemini').lower()
    cls = _PROVIDER_MAP.get(n)
    if not cls: return None
    try:
        return LoggingProvider(cls())
    except Exception as e:
        logging.warning(f"Provider init failed for {n}: {e}")
        return None

def list_providers():
    return [
        {'name': key, 'label': key.capitalize() if key!='azure' else 'Azure OpenAI', 'default': DEFAULT_PROVIDER==key}
        for key in _PROVIDER_MAP.keys()
    ]

def classify_confirmation(provider: BaseProvider, user_message: str) -> str:
    try:
        return provider.classify_confirmation(user_message)
    except Exception:
        low = user_message.lower()
        if any(w in low for w in ["ya","lanjut","yakin","ok","betul","gas","iya","oke","benar"]): return 'confirm'
        if any(w in low for w in ["tidak","batal","jangan","stop","cancel","enggak","gajadi"]): return 'cancel'
        return 'other'
