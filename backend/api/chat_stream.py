from flask import Blueprint, request, jsonify
from datetime import datetime
import json
from ..db import insert_message, touch_chat
from ..services.llm_provider import get_provider, DEFAULT_PROVIDER
from ..services.chat_flow import build_context_messages, prepare_tools
from ..services.tool_dispatcher import execute as execute_tool
from ..extensions import socketio
from ..services.gemini_heuristics import gemini_fallback_tool
from ..config import MAX_CONTEXT_MESSAGES
from ..prompts import BASE_SYSTEM_PROMPT

chat_stream_bp = Blueprint('chat_stream', __name__)

@chat_stream_bp.route('/api/chat/<chat_id>/ask_stream', methods=['POST'])
def ask_stream(chat_id):
    payload = request.json or {}; user_message = (payload.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'}), 400
    from ..db import get_chat_provider
    provider_name = get_chat_provider(chat_id) or DEFAULT_PROVIDER
    provider = get_provider(provider_name)
    if not provider:
        return jsonify({'success': False, 'answer': f'LLM provider {provider_name} tidak tersedia.'}), 500
    insert_message(chat_id, user_message, 'user')
    # Build context and tools
    ctx = build_context_messages(chat_id)
    tools = prepare_tools()
    try:
        preview = provider.chat(ctx + [{'role':'user','content': user_message}], tools=tools, temperature=0.2)
        if getattr(preview,'tool_calls', None):
            socketio.emit('assistant_start', {'chat_id': chat_id}, room=chat_id)
            call = preview.tool_calls[0]; import json as _json
            try: args = _json.loads(call['function']['arguments'])
            except Exception: args = {}
            data_res, err = execute_tool(call['function']['name'], args)
            if err:
                answer = f"❌ Error: {err}"; insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
                socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
                return jsonify({'success': True, 'streamed': True})
            fname = call['function']['name']
            if fname == 'aggregate_issues':
                labels = [c['label'] for c in data_res['counts']][:40]; values = [c['value'] for c in data_res['counts']][:40]; total=sum(values) or 1
                chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Gunakan filter'}
                header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"; rows='\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in data_res['counts'][:100]])
                top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in data_res['counts'][:3]])
                insight = f"Insight: {top3}. Total {data_res['total']} issue." if data_res['counts'] else 'Insight: Tidak ada data.'
                answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
                insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
                socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
                return jsonify({'success': True, 'streamed': True})
            # summarisation streaming
            tool_call_id = call['id']
            summarizer_messages = ctx + [
                {'role':'user','content': user_message},
                {"role":"assistant","content":None,"tool_calls":[{"id":tool_call_id,"type":"function","function":{"name":fname,"arguments":call['function']['arguments']}}]},
                {"tool_call_id": tool_call_id, "role": "tool", "name": fname, "content": json.dumps(data_res, ensure_ascii=False)}
            ]
            socketio.emit('assistant_start', {'chat_id': chat_id}, room=chat_id)
            full=[]
            try:
                for delta in provider.stream_chat(summarizer_messages, temperature=0.2):
                    full.append(delta); socketio.emit('assistant_delta', {'chat_id': chat_id, 'delta': delta}, room=chat_id)
                answer=''.join(full) or '(kosong)'
            except Exception as e:
                answer=f"❌ Error summarising: {e}"
            insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
            socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
            return jsonify({'success': True, 'streamed': True})
        # plain streaming
        socketio.emit('assistant_start', {'chat_id': chat_id}, room=chat_id)
        full=[]
        for delta in provider.stream_chat(ctx + [{'role':'user','content': user_message}], temperature=0.2):
            if not delta: continue
            full.append(delta); socketio.emit('assistant_delta', {'chat_id': chat_id, 'delta': delta}, room=chat_id)
        answer=''.join(full) or '(kosong)'
        if provider_name == 'gemini':
            guess = gemini_fallback_tool(user_message)
            if guess:
                fname, args = guess
                data_res, err = execute_tool(fname, args)
                if not err:
                    if fname == 'aggregate_issues':
                        labels = [c['label'] for c in data_res['counts']][:30]; values = [c['value'] for c in data_res['counts']][:30]
                        chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Heuristik Gemini'}
                        answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```"
                    else:
                        answer += "\n\nHeuristik data:\n" + json.dumps(data_res, ensure_ascii=False)[:4000]
        insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
        socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
        return jsonify({'success': True, 'streamed': True})
    except Exception as e:
        socketio.emit('assistant_error', {'chat_id': chat_id, 'error': str(e)}, room=chat_id)
        return jsonify({'success': False, 'answer': f'Error streaming: {e}'}), 500
