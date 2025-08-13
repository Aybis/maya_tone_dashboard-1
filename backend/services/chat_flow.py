"""Chat flow orchestration: building context, handling confirmation, tool exec, summarisation.

This module isolates the logic used by both sync and streaming endpoints so
route handlers become thin. It does NOT handle Socket.IO emission; streaming
handler still deals with incremental deltas.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from ..prompts import BASE_SYSTEM_PROMPT
from ..config import MAX_CONTEXT_MESSAGES
from ..db import fetch_recent_messages, get_pending_action, clear_pending_action
from .llm_provider import classify_confirmation
from .tools_schema import build_jira_tools
from .tool_dispatcher import execute as execute_tool
from .gemini_heuristics import gemini_fallback_tool

class ChatFlowResult:
    def __init__(self, answer: Optional[str]=None, tool_call: Optional[Dict[str,Any]]=None, tool_result: Any=None, tool_error: Optional[str]=None, messages_for_second_pass: Optional[List[Dict[str,Any]]]=None, direct_chart: Optional[str]=None):
        self.answer = answer
        self.tool_call = tool_call
        self.tool_result = tool_result
        self.tool_error = tool_error
        self.messages_for_second_pass = messages_for_second_pass
        self.direct_chart = direct_chart


def build_context_messages(chat_id: str) -> List[Dict[str,str]]:
    history = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    return [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history


def prepare_tools() -> List[Dict[str,Any]]:
    now = datetime.now(); current_date = now.strftime('%Y-%m-%d'); month_start = now.replace(day=1).strftime('%Y-%m-%d')
    return build_jira_tools(current_date, month_start)


def handle_confirmation(provider, chat_id: str, user_message: str):
    pending = get_pending_action(chat_id)
    if not pending:
        return None
    intent = classify_confirmation(provider, user_message)
    clear_pending_action(chat_id)
    if intent == 'cancel':
        return ChatFlowResult(answer='❌ Baik, aksi dibatalkan.')
    if intent == 'confirm':
        action = json.loads(pending)
        name = action['name']; args = action['args']
        data_res, err = execute_tool(name, args)
        if err:
            return ChatFlowResult(answer=f"❌ Error eksekusi: {err}")
        # Build second pass messages
        ctx = build_context_messages(chat_id)
        second_messages = ctx + [{'role':'assistant','content': f"✅ Aksi '{name}' sukses: {json.dumps(data_res, ensure_ascii=False)}"}]
        return ChatFlowResult(messages_for_second_pass=second_messages)
    return ChatFlowResult(answer=None)  # treat as normal flow


def first_pass(provider, chat_id: str, user_message: str) -> ChatFlowResult:
    ctx = build_context_messages(chat_id)
    tools = prepare_tools()
    first = provider.chat(ctx, tools=tools, temperature=0.1)
    if not getattr(first, 'tool_calls', None):
        # chart heuristic fallback or Gemini heuristic
        if any(k in user_message.lower() for k in ['chart','grafik','diagram','visual','pie','bar','line']):
            data_res, err = execute_tool('aggregate_issues', {'group_by':'status'})
            counts = (data_res or {}).get('counts', []) if not err else []
            labels = [c['label'] for c in counts][:40]; values = [c['value'] for c in counts][:40]
            total = sum(values) or 1
            chart = {'title':'Distribusi Issue (Fallback)','type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6']*len(values)}],'meta':{'group_by':'status','filters':{},'counts':counts},'notes':'Fallback'}
            header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
            rows = '\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in counts[:50]])
            top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in counts[:3]])
            insight = f"Insight: Top {min(3,len(counts))}: {top3}. Total {total} issue."
            chart_block = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
            return ChatFlowResult(answer=chart_block)
        # Gemini heuristic explicit
        if provider.name == 'gemini':
            guess = gemini_fallback_tool(user_message)
            if guess:
                fname, args = guess
                data_res, err = execute_tool(fname, args)
                if not err:
                    if fname == 'aggregate_issues':
                        labels = [c['label'] for c in data_res['counts']][:30]; values = [c['value'] for c in data_res['counts']][:30]
                        chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Heuristik Gemini'}
                        return ChatFlowResult(answer=f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```")
                    else:
                        return ChatFlowResult(answer=json.dumps(data_res, ensure_ascii=False)[:4000])
        return ChatFlowResult(answer=first.content or 'Tidak ada jawaban.')
    # tool call present
    call = first.tool_calls[0]; fname = call['function']['name']
    import json as _json
    try:
        args = _json.loads(call['function']['arguments'])
    except Exception:
        args = {}
    data_res, err = execute_tool(fname, args)
    if err:
        return ChatFlowResult(answer=f"❌ Error: {err}")
    if fname == 'aggregate_issues':
        labels = [c['label'] for c in data_res['counts']][:40]; values = [c['value'] for c in data_res['counts']][:40]; total = sum(values) or 1
        chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Gunakan filter'}
        header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"; rows='\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in data_res['counts'][:100]])
        top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in data_res['counts'][:3]])
        insight = f"Insight: {top3}. Total {data_res['total']} issue." if data_res['counts'] else 'Insight: Tidak ada data.'
        chart_block = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
        return ChatFlowResult(answer=chart_block)
    # two step summarisation
    tool_call_id = call['id']
    ctx = build_context_messages(chat_id)
    summarizer_messages = ctx + [
        {"role":"assistant","content":None,"tool_calls":[{"id":tool_call_id,"type":"function","function":{"name":fname,"arguments":call['function']['arguments']}}]},
        {"tool_call_id": tool_call_id, "role": "tool", "name": fname, "content": json.dumps(data_res, ensure_ascii=False)}
    ]
    return ChatFlowResult(tool_call=call, tool_result=data_res, messages_for_second_pass=summarizer_messages)
