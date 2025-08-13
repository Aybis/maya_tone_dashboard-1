"""Logging wrapper for LLM providers to trace calls, duration, tools usage."""
from __future__ import annotations
import time, logging, json
from typing import Iterable, List, Dict, Any, Optional
from .providers.base import BaseProvider, ProviderMessage

class LoggingProvider(BaseProvider):
    def __init__(self, inner: BaseProvider):
        self._inner = inner
        self.name = inner.name

    def chat(self, messages: List[Dict[str,str]], tools: Optional[List[Dict[str,Any]]] = None, temperature: float = 0.1) -> ProviderMessage:
        t0 = time.time()
        try:
            resp = self._inner.chat(messages, tools=tools, temperature=temperature)
            dt = (time.time()-t0)*1000
            logging.info(f"LLM[{self.name}] chat ok {dt:.1f}ms tools={bool(tools)} tool_calls={len(resp.tool_calls) if resp.tool_calls else 0} tokens_in~{len(json.dumps(messages))}")
            return resp
        except Exception as e:
            dt = (time.time()-t0)*1000
            logging.warning(f"LLM[{self.name}] chat error {dt:.1f}ms err={e}")
            raise

    def stream_chat(self, messages: List[Dict[str,str]], temperature: float = 0.2) -> Iterable[str]:
        t0 = time.time()
        yielded = 0
        try:
            for delta in self._inner.stream_chat(messages, temperature=temperature):
                yielded += len(delta or '')
                yield delta
            dt = (time.time()-t0)*1000
            logging.info(f"LLM[{self.name}] stream ok {dt:.1f}ms chars={yielded}")
        except Exception as e:
            dt = (time.time()-t0)*1000
            logging.warning(f"LLM[{self.name}] stream error {dt:.1f}ms err={e}")
            raise

    def classify_confirmation(self, user_message: str) -> str:
        return self._inner.classify_confirmation(user_message)
