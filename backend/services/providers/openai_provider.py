import os
from .base import BaseProvider, ProviderMessage
from typing import List, Dict, Any
import logging

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_DEFAULT_MODEL = os.getenv('OPENAI_DEFAULT_MODEL', 'gpt-4o-mini')

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

class OpenAIProvider(BaseProvider):
    name = 'openai'

    def __init__(self):
        if not _HAS_OPENAI or not OPENAI_API_KEY:
            raise RuntimeError('OpenAI SDK or key missing')
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_DEFAULT_MODEL

    def chat(self, messages, tools=None, temperature=0.1):
        kwargs = {}
        if tools:
            kwargs['tools'] = tools
            kwargs['tool_choice'] = 'auto'
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, **kwargs)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, 'tool_calls', None)
        if tool_calls:
            converted = []
            for tc in tool_calls:
                converted.append({'id': tc.id,'function': {'name': tc.function.name,'arguments': tc.function.arguments}})
            return ProviderMessage(content=msg.content, tool_calls=converted)
        return ProviderMessage(content=msg.content)

    def stream_chat(self, messages, temperature=0.2):
        stream = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, stream=True)
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if not delta:
                continue
            yield delta
