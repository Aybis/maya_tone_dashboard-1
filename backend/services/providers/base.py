from __future__ import annotations
import json, logging
from typing import List, Dict, Any, Optional, Iterable

class ProviderMessage:
    def __init__(self, content: Optional[str], tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.content = content
        self.tool_calls = tool_calls or []

class BaseProvider:
    name: str
    supports_tools: bool = True

    def chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, temperature: float = 0.1) -> ProviderMessage:  # pragma: no cover
        raise NotImplementedError

    def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Iterable[str]:  # pragma: no cover
        raise NotImplementedError

    def classify_confirmation(self, user_message: str) -> str:
        system_prompt = (
            "Analisis respons pengguna untuk konfirmasi. Balas HANYA JSON {\"intent\":\"confirm\"|\"cancel\"|\"other\"}.\n"
            "confirm: ya, lanjut, betul, ok, gas, yakin, benar, silahkan, iya, oke\n"
            "cancel: jangan, batal, tidak, stop, gajadi, cancel, enggak\n"
            "selain itu: other"
        )
        try:
            msg = self.chat([
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ], tools=None, temperature=0.0)
            if msg.content:
                data = json.loads(msg.content)
                intent = data.get('intent')
                if intent in ('confirm','cancel','other'):
                    return intent
        except Exception as e:
            logging.warning(f"confirmation intent model fallback: {e}")
        low = user_message.lower()
        if any(w in low for w in ["ya","lanjut","yakin","ok","betul","gas","iya","oke","benar"]):
            return 'confirm'
        if any(w in low for w in ["tidak","batal","jangan","stop","cancel","enggak","gajadi"]):
            return 'cancel'
        return 'other'
