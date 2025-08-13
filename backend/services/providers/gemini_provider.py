import os, json, uuid, logging
from .base import BaseProvider, ProviderMessage
from typing import List, Dict, Any, Optional, Iterable

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')

try:
    import google.generativeai as genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

class GeminiProvider(BaseProvider):
    name = 'gemini'

    def __init__(self):
        if not _HAS_GEMINI or not GEMINI_API_KEY:
            raise RuntimeError('Gemini SDK or key missing')
        genai.configure(api_key=GEMINI_API_KEY)
        self.model_name = GEMINI_MODEL

    # ----- Conversions -----
    def _convert_messages(self, messages: List[Dict[str, str]]):
        converted = []
        for m in messages:
            role = m.get('role'); content = m.get('content') or ''
            if role == 'system':
                converted.append({'role':'user','parts':[f'SYSTEM: {content}']})
            elif role == 'assistant':
                converted.append({'role':'model','parts':[content]})
            else:
                converted.append({'role':'user','parts':[content]})
        return converted

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]):
        if not tools: return None
        fdecls = []
        for t in tools:
            if t.get('type') != 'function':
                continue
            f = t['function']
            fdecls.append({'name': f.get('name'), 'description': f.get('description'), 'parameters': f.get('parameters')})
        return [{'function_declarations': fdecls}]

    def _prepend_tool_instruction(self, converted_messages, tool_cfg):
        if not tool_cfg: return converted_messages
        try:
            fnames = [fd['name'] for fd in tool_cfg[0].get('function_declarations', [])]
            if fnames:
                instruction = (
                    "INSTRUKSI: Jika pertanyaan membutuhkan data Jira (issues, projects, worklogs, aggregasi) atau aksi (create/update/delete), "
                    "PANGGIL salah satu fungsi berikut dengan argumen JSON valid: " + ', '.join(fnames) + ". Jika perlu informasi, jangan berasumsi—gunakan fungsi. Jawaban final hanya diberikan setelah (atau tanpa) pemanggilan fungsi sesuai kebutuhan."
                )
                return [{'role':'user','parts':[instruction]}] + converted_messages
        except Exception:
            pass
        return converted_messages

    # ----- API -----
    def chat(self, messages, tools=None, temperature=0.1):
        from google.generativeai import GenerativeModel
        tool_cfg = self._convert_tools(tools)
        converted = self._convert_messages(messages)
        converted = self._prepend_tool_instruction(converted, tool_cfg)
        model = GenerativeModel(self.model_name, tools=tool_cfg)
        gen_kwargs = {'generation_config': {'temperature': temperature}}
        if tool_cfg:
            gen_kwargs['tool_config'] = {'function_calling_config': {'mode': 'AUTO'}}
        resp = model.generate_content(converted, **gen_kwargs)
        tool_calls = []
        try:
            for part in resp.candidates[0].content.parts:
                fcall = getattr(part, 'function_call', None)
                if fcall:
                    tool_calls.append({'id': str(uuid.uuid4()), 'function': {'name': fcall.name, 'arguments': json.dumps(fcall.args or {}, ensure_ascii=False)}})
        except Exception:
            pass
        texts = []
        try:
            for part in resp.candidates[0].content.parts:
                if getattr(part, 'text', None):
                    texts.append(part.text)
        except Exception:
            pass
        content = '\n'.join(texts) if texts else None
        return ProviderMessage(content=content, tool_calls=tool_calls)

    def stream_chat(self, messages, temperature=0.2):
        from google.generativeai import GenerativeModel
        tool_cfg = None
        converted = self._convert_messages(messages)
        converted = self._prepend_tool_instruction(converted, tool_cfg)
        model = GenerativeModel(self.model_name)
        try:
            resp = model.generate_content(converted, stream=True, generation_config={'temperature': temperature})
            for event in resp:
                try:
                    for part in event.candidates[0].content.parts:
                        if getattr(part, 'text', None):
                            yield part.text
                except Exception:
                    continue
        except Exception as e:
            logging.error(f"Gemini stream error: {e}")
            return
