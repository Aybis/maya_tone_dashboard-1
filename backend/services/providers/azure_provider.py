import os
from .base import BaseProvider, ProviderMessage
from typing import List, Dict, Any
import logging

AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')

try:
    from openai import AzureOpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

class AzureOpenAIProvider(BaseProvider):
    name = 'azure'

    def __init__(self):
        if not _HAS_OPENAI or not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
            raise RuntimeError('Azure OpenAI SDK or env vars missing')
        self.client = AzureOpenAI(api_key=AZURE_OPENAI_API_KEY, api_version=AZURE_OPENAI_API_VERSION, azure_endpoint=AZURE_OPENAI_ENDPOINT)
        self.model = AZURE_OPENAI_DEPLOYMENT

    def chat(self, messages, tools=None, temperature=0.1):
        kwargs = {}
        if tools:
            kwargs['tools'] = tools
            kwargs['tool_choice'] = 'auto'
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, **kwargs)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, 'tool_calls', None)
        converted = []
        if tool_calls:
            for tc in tool_calls:
                converted.append({'id': tc.id, 'function': {'name': tc.function.name, 'arguments': tc.function.arguments}})
        return ProviderMessage(content=msg.content, tool_calls=converted)

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
