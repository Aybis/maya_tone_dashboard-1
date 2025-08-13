import json
from types import SimpleNamespace
from backend.services.chat_flow import first_pass, handle_confirmation, ChatFlowResult

class DummyProvider:
    name = 'dummy'
    def __init__(self, msg):
        self._msg = msg
    def chat(self, messages, tools=None, temperature=0.1):
        return self._msg

# Simulate no tool call answer
class Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

def test_first_pass_plain(monkeypatch, tmp_path):
    # monkeypatch required DB fetch_recent_messages
    from backend import db as dbmod
    monkeypatch.setattr(dbmod, 'fetch_recent_messages', lambda chat_id, n: [])
    monkeypatch.setattr(dbmod, 'get_pending_action', lambda chat_id: None)
    monkeypatch.setattr(dbmod, 'clear_pending_action', lambda chat_id: None)
    from backend.services import chat_flow
    monkeypatch.setattr(chat_flow, 'execute_tool', lambda n,a: ({'counts':[]}, None))
    p = DummyProvider(Msg(content='hello'))
    res = first_pass(p, 'chat1', 'hi')
    assert isinstance(res, ChatFlowResult)
    assert res.answer == 'hello'
