from flask import Blueprint, request, jsonify
import json, sqlite3
from datetime import datetime, timedelta
from ..prompts import BASE_SYSTEM_PROMPT
from ..config import MAX_CONTEXT_MESSAGES, JIRA_USERNAME
from ..db import insert_message, fetch_recent_messages, get_pending_action, set_pending_action, clear_pending_action, touch_chat
from ..services.openai_service import get_client, check_confirmation_intent
from ..services.tool_dispatcher import execute as execute_tool
from ..extensions import socketio  # For real-time emission of assistant replies

# Blueprint providing chat session lifecycle + AI question answering with tool/function calling.
# Flow (ask endpoint):
# 1. Save user message.
# 2. If there is a pending action awaiting confirmation (stored earlier), classify reply as confirm/cancel.
# 3. If confirming: execute the stored tool and then summarise result with a second AI pass.
# 4. Else build conversation context (recent N messages + system prompt) and call OpenAI with tool definitions.
# 5. If model returns a tool call, execute it and either (a) directly build a chart fallback or (b) feed tool result back for summarisation.
# 6. Persist assistant response and return to client.
# Safety: Any tool execution errors are caught and surfaced in assistant reply.

chat_bp = Blueprint('chat', __name__)

# ---- Tool schema builder ---------------------------------------------------
def build_tools(current_date: str, month_start: str):
    """Return OpenAI tools schema list reused across endpoints.

    Pass in dynamic date strings so description text remains real-time without duplicating
    the large schema block in each endpoint. Update here to propagate everywhere.
    """
    return [
        {"type":"function","function":{"name":"aggregate_issues","description":"Agregasi issue untuk chart (kembalikan distribusi counts).","parameters":{"type":"object","properties":{"group_by":{"type":"string","enum":["status","priority","assignee","type","created_date"]},"from_date":{"type":"string","description":"YYYY-MM-DD mulai (opsional)"},"to_date":{"type":"string","description":"YYYY-MM-DD akhir (opsional)"},"jql_extra":{"type":"string","description":"Tambahan filter JQL"}},"required":["group_by"]}}},

        {"type":"function","function":{"name":"get_issues","description":f"Cari issue via JQL gunakan tanggal real-time: today={current_date} month_start={month_start}","parameters":{"type":"object","properties":{"jql_query":{"type":"string","description":"Kueri JQL lengkap"},"max_results":{"type":"integer","description":"Batas hasil (default 50)"}},"required":["jql_query"]}}},

        {"type":"function","function":{"name":"get_projects","description":"Daftar semua project Jira (key + name).","parameters":{"type":"object","properties":{}}}},
        {"type":"function","function":{"name":"get_issue_types","description":"Daftar issue types; jika project_key diberikan hanya dari project tsb.","parameters":{"type":"object","properties":{"project_key":{"type":"string"}}}}},

        {"type":"function","function":{"name":"get_worklogs","description":"Ambil worklog user saat ini dalam rentang tanggal (inklusi).","parameters":{"type":"object","properties":{"from_date":{"type":"string","description":"YYYY-MM-DD"},"to_date":{"type":"string","description":"YYYY-MM-DD"}},"required":["from_date","to_date"]}}},

        {"type":"function","function":{"name":"create_worklog","description":"Buat worklog pada issue tertentu.","parameters":{"type":"object","properties":{"issue_key":{"type":"string"},"time_spent_hours":{"type":"number"},"description":{"type":"string"}},"required":["issue_key","time_spent_hours"]}}},

        {"type":"function","function":{"name":"update_worklog","description":"Update worklog (waktu atau deskripsi).","parameters":{"type":"object","properties":{"issue_key":{"type":"string"},"worklog_id":{"type":"string"},"time_spent_hours":{"type":"number"},"description":{"type":"string"}},"required":["issue_key","worklog_id"]}}},

        {"type":"function","function":{"name":"delete_worklog","description":"Hapus worklog tertentu.","parameters":{"type":"object","properties":{"issue_key":{"type":"string"},"worklog_id":{"type":"string"}},"required":["issue_key","worklog_id"]}}},

        {"type":"function","function":{"name":"manage_issue","description":"Create / update / delete issue. Gunakan action=create|update|delete. Untuk create/update sertakan fields di details.","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["create","update","delete"]},"details":{"type":"object","description":"Field issue. For update/delete sertakan issue_key.","properties":{"issue_key":{"type":"string"},"project_key":{"type":"string"},"summary":{"type":"string"},"description":{"type":"string"},"acceptance_criteria":{"type":"string"},"priority_name":{"type":"string"},"assignee_name":{"type":"string"},"duedate":{"type":"string"},"issuetype_name":{"type":"string"}}}},"required":["action"]}}},
    ]

@chat_bp.route('/api/chat/new', methods=['POST'])
def new_chat():
    """Create a new chat row with autogenerated whimsical title."""
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    from uuid import uuid4; import random
    chat_id = str(uuid4())
    WORDS = ['Orion','Lumen','Echo','Nova','Aster','Nimbus','Quartz','Atlas','Zenith','Pulse','Vertex','Cipher','Delta','Photon','Vortex','Comet','Helix','Matrix']
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"
    c.execute('INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)', (chat_id, title, datetime.now(), datetime.now(), 'user'))
    conn.commit(); conn.close(); return jsonify({'chat_id': chat_id, 'title': title})

@chat_bp.route('/api/chat/history')
def history():
    """Return list of chats (id + title) ordered by latest update."""
    conn = sqlite3.connect('maya_tone.db'); conn.row_factory = sqlite3.Row
    c = conn.cursor(); c.execute('SELECT id, title FROM chats ORDER BY updated_at DESC')
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(rows)

@chat_bp.route('/api/chat/<chat_id>')
def messages(chat_id):
    """Return chronological messages for a chat."""
    conn = sqlite3.connect('maya_tone.db'); conn.row_factory = sqlite3.Row
    c = conn.cursor(); c.execute('SELECT content, sender FROM messages WHERE chat_id = ? ORDER BY timestamp ASC', (chat_id,))
    msgs = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(msgs)

@chat_bp.route('/api/chat/<chat_id>/delete', methods=['DELETE'])
def delete_chat(chat_id):
    """Delete chat and all messages."""
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    c.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,)); c.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    conn.commit(); conn.close(); return jsonify({'success': True})

@chat_bp.route('/api/chat/<chat_id>/title', methods=['PUT'])
def rename_chat(chat_id):
    """Rename chat (title)."""
    data = request.json or {}; title = (data.get('title','') or '').strip()
    if not title: return jsonify({'success': False, 'error':'Empty title'}), 400
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    c.execute('UPDATE chats SET title = ?, updated_at = ? WHERE id = ?', (title, datetime.now(), chat_id))
    conn.commit(); conn.close(); return jsonify({'success': True})

@chat_bp.route('/api/chat/<chat_id>/ask', methods=['POST'])
def ask(chat_id):
    """Primary conversational endpoint.

    Accepts: {"message": "..."}
    Returns: { success: bool, answer: str }

    Behaviour details:
    - Maintains conversation context (last MAX_CONTEXT_MESSAGES user/assistant messages).
    - Provides OpenAI function-calling tools for Jira aggregation & issue search.
    - Handles confirmation workflow (stored pending action) via lightweight intent classifier.
    - Emits chart spec blocks with ```chart fences when aggregation requested or fallback triggered.
    """
    payload = request.json or {}; user_message = (payload.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'})
    client = get_client();
    if not client: return jsonify({'success': False, 'answer':'OpenAI tidak tersedia.'})
    # Persist user message (frontend already adds optimistically; no emit to avoid duplicates)
    insert_message(chat_id, user_message, 'user')

    def send(answer):
        """Persist assistant message, update chat timestamp, emit to room, then respond JSON.

        Frontend (AiSearch.jsx) listens for 'new_message' events joined via 'join_chat'. Previously
        responses only appeared after a manual refresh because no Socket.IO emission occurred.
        """
        insert_message(chat_id, answer, 'assistant')
        touch_chat(chat_id)
        # Emit ONLY assistant messages to avoid duplicating optimistic user message on client
        try:
            socketio.emit('new_message', {
                'chat_id': chat_id,
                'sender': 'assistant',
                'content': answer
            }, room=chat_id)
        except Exception:
            # Fail silently; real-time is best-effort and we still return HTTP response
            pass
        return jsonify({'success': True, 'answer': answer})

    # 1. Confirmation flow check
    pending = get_pending_action(chat_id)
    if pending:
        intent = check_confirmation_intent(user_message, client).get('intent')
        clear_pending_action(chat_id)
        if intent == 'cancel': return send('❌ Baik, aksi dibatalkan.')
        if intent == 'confirm':
            action = json.loads(pending)
            name = action['name']; args = action['args']
            data_res, err = execute_tool(name, args)
            if err: return send(f"❌ Error eksekusi: {err}")
            # Second pass summarisation with tool result appended
            history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
            messages_ = [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history_msgs + [{'role':'assistant','content': f"✅ Aksi '{name}' sukses: {json.dumps(data_res, ensure_ascii=False)}"}]
            second = client.chat.completions.create(model='gpt-4o-mini', messages=messages_, temperature=0.1)
            return send(second.choices[0].message.content)

    # 2. Normal flow: build context
    history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    messages_ = [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history_msgs
    now = datetime.now(); current_date = now.strftime('%Y-%m-%d')
    month_start = now.replace(day=1).strftime('%Y-%m-%d')
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
    last_month_end = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    tools = build_tools(current_date, month_start)
    response = client.chat.completions.create(model='gpt-4o-mini', messages=messages_, tools=tools, tool_choice='auto', temperature=0.1)
    rmsg = response.choices[0].message

    # 3. No tool call case (may still ask for a chart => fallback quick aggregation)
    if not getattr(rmsg,'tool_calls', None):
        if any(k in user_message.lower() for k in ['chart','grafik','diagram','visual','pie','bar','line']):
            data_res, err = execute_tool('aggregate_issues', {'group_by':'status'})
            counts = (data_res or {}).get('counts', []) if not err else []
            labels = [c['label'] for c in counts][:40]; values = [c['value'] for c in counts][:40]
            total = sum(values) or 1
            chart = {'title':'Distribusi Issue (Fallback)','type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6']*len(values)}],'meta':{'group_by':'status','filters':{},'counts':counts},'notes':'Fallback'}
            # Build table markdown
            header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
            rows = '\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in counts[:50]])
            top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in counts[:3]])
            insight = f"Insight: Top {min(3,len(counts))}: {top3}. Total {total} issue."
            return send(f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}")
        return send(rmsg.content or 'Tidak ada jawaban.')

    # 4. Handle tool call result
    call = rmsg.tool_calls[0]; fname = call.function.name; args = json.loads(call.function.arguments)
    data_res, err = execute_tool(fname, args)
    if err: return send(f"❌ Error: {err}")

    # 4a. Short-circuit for aggregation to emit chart spec directly
    if fname == 'aggregate_issues':
        labels = [c['label'] for c in data_res['counts']][:40]; values = [c['value'] for c in data_res['counts']][:40]
        total = sum(values) or 1
        chart = {'title': f'Agg by {data_res['group_by']}','type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Gunakan filter'}
        header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
        rows = '\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in data_res['counts'][:100]])
        top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in data_res['counts'][:3]])
        insight = f"Insight: {top3}. Total {data_res['total']} issue." if data_res['counts'] else 'Insight: Tidak ada data.'
        return send(f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}")

    # 4b. Two-step summarisation for non-chart tools
    tool_call_id = call.id
    summarizer_messages = messages_ + [
        {"role":"assistant","content":None,"tool_calls":[{"id":tool_call_id,"type":"function","function":{"name":fname,"arguments":call.function.arguments}}]},
        {"tool_call_id": tool_call_id, "role": "tool", "name": fname, "content": json.dumps(data_res, ensure_ascii=False)}
    ]
    second = client.chat.completions.create(model='gpt-4o-mini', messages=summarizer_messages, temperature=0.1)
    return send(second.choices[0].message.content)


@chat_bp.route('/api/chat/<chat_id>/ask_stream', methods=['POST'])
def ask_stream(chat_id):
    """Streaming variant: streams assistant tokens via Socket.IO events.

    Events (room=chat_id):
    - assistant_start {chat_id}
    - assistant_delta {chat_id, delta}
    - assistant_end {chat_id, content}
    - assistant_error {chat_id, error}

    Limitations: If a tool/function call is required, we execute synchronously (no token stream)
    and emit a single assistant_end.
    """
    payload = request.json or {}; user_message = (payload.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'}), 400
    client = get_client();
    if not client:
        return jsonify({'success': False, 'answer': 'OpenAI tidak tersedia.'}), 500
    insert_message(chat_id, user_message, 'user')
    # Build context
    history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    messages_ = [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history_msgs
    now = datetime.now(); current_date = now.strftime('%Y-%m-%d'); month_start = now.replace(day=1).strftime('%Y-%m-%d')
    tools = build_tools(current_date, month_start)
    try:
        # First non-stream call to decide if tool call needed (cannot know tool call via streaming easily without parsing function calls mid-stream)
        preview = client.chat.completions.create(model='gpt-4o-mini', messages=messages_ + [{'role':'user','content': user_message}], tools=tools, tool_choice='auto', temperature=0.2)
        rmsg = preview.choices[0].message
        if getattr(rmsg,'tool_calls', None):
            # Emit start early so UI shows spinner even during Jira fetch
            socketio.emit('assistant_start', {'chat_id': chat_id}, room=chat_id)
            call = rmsg.tool_calls[0]; fname = call.function.name; args = json.loads(call.function.arguments)
            data_res, err = execute_tool(fname, args)
            if err:
                answer = f"❌ Error: {err}"
                insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
                socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
                return jsonify({'success': True, 'streamed': True})
            if fname == 'aggregate_issues':
                labels = [c['label'] for c in data_res['counts']][:40]; values = [c['value'] for c in data_res['counts']][:40]
                total = sum(values) or 1
                chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Gunakan filter'}
                header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
                rows = '\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in data_res['counts'][:100]])
                top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in data_res['counts'][:3]])
                insight = f"Insight: {top3}. Total {data_res['total']} issue." if data_res['counts'] else 'Insight: Tidak ada data.'
                answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
                insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
                socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
                return jsonify({'success': True, 'streamed': True})
            # Streaming summarisation for non-aggregation tool result
            tool_call_id = call.id
            # Truncate very large lists for model efficiency
            summary_payload = data_res
            try:
                if isinstance(data_res, list) and len(data_res) > 60:
                    summary_payload = { 'items_preview': data_res[:60], 'total_items': len(data_res) }
                elif isinstance(data_res, dict):
                    # If dict contains large list under 'items' key
                    for k,v in list(data_res.items()):
                        if isinstance(v, list) and len(v) > 60:
                            data_res[k] = { 'items_preview': v[:60], 'total_items': len(v) }
                            summary_payload = data_res
            except Exception:
                pass
            summarizer_messages = messages_ + [
                {'role':'user','content': user_message},
                {"role":"assistant","content":None,"tool_calls":[{"id":tool_call_id,"type":"function","function":{"name":fname,"arguments":call.function.arguments}}]},
                {"tool_call_id": tool_call_id, "role": "tool", "name": fname, "content": json.dumps(summary_payload, ensure_ascii=False)}
            ]
            try:
                stream2 = client.chat.completions.create(model='gpt-4o-mini', messages=summarizer_messages, temperature=0.2, stream=True)
                full=[]
                for chunk in stream2:
                    try:
                        delta = chunk.choices[0].delta.content
                    except Exception:
                        delta=None
                    if not delta: continue
                    full.append(delta)
                    socketio.emit('assistant_delta', {'chat_id': chat_id, 'delta': delta}, room=chat_id)
                answer = ''.join(full) or '(kosong)'
            except Exception as e:
                answer = f"❌ Error summarising: {e}"
            insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
            socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
            return jsonify({'success': True, 'streamed': True})
        # Stream plain answer
        socketio.emit('assistant_start', {'chat_id': chat_id}, room=chat_id)
        full = []
        stream = client.chat.completions.create(model='gpt-4o-mini', messages=messages_ + [{'role':'user','content': user_message}], temperature=0.2, stream=True)
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if not delta:
                continue
            full.append(delta)
            socketio.emit('assistant_delta', {'chat_id': chat_id, 'delta': delta}, room=chat_id)
        answer = ''.join(full) or '(kosong)'
        insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
        socketio.emit('assistant_end', {'chat_id': chat_id, 'content': answer}, room=chat_id)
        return jsonify({'success': True, 'streamed': True})
    except Exception as e:
        socketio.emit('assistant_error', {'chat_id': chat_id, 'error': str(e)}, room=chat_id)
        return jsonify({'success': False, 'answer': f'Error streaming: {e}'}), 500


@chat_bp.route('/api/chat/ask_new', methods=['POST'])
def ask_new():
    """Create a new chat only when the user actually sends a first message and AI responds.

    Body: {"message": "..."}
    Returns: { success, answer, chat_id, title }

    Avoids pre-creating empty chats when user merely navigates to canvas.
    """
    payload = request.json or {}
    user_message = (payload.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'}), 400
    client = get_client()
    if not client:
        return jsonify({'success': False, 'answer': 'OpenAI tidak tersedia.'}), 500
    # Create chat row (title generation logic reused from new_chat)
    import sqlite3, random
    from uuid import uuid4
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    WORDS = ['Orion','Lumen','Echo','Nova','Aster','Nimbus','Quartz','Atlas','Zenith','Pulse','Vertex','Cipher','Delta','Photon','Vortex','Comet','Helix','Matrix']
    chat_id = str(uuid4())
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"
    c.execute('INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?,?,?,?,?)', (chat_id, title, datetime.now(), datetime.now(), 'user'))
    conn.commit(); conn.close()

    # Insert user message (no socket emit yet, frontend will add optimistically or can listen)
    insert_message(chat_id, user_message, 'user')
    try:
        socketio.emit('new_message', {'chat_id': chat_id, 'sender': 'user', 'content': user_message}, room=chat_id)
    except Exception:
        pass

    # Minimal context (only system + first user message)
    messages_ = [{'role':'system','content': BASE_SYSTEM_PROMPT}, {'role':'user','content': user_message}]
    now = datetime.now(); current_date = now.strftime('%Y-%m-%d')
    month_start = now.replace(day=1).strftime('%Y-%m-%d')
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
    last_month_end = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    tools = build_tools(current_date, month_start)
    try:
        response = client.chat.completions.create(model='gpt-4o-mini', messages=messages_, tools=tools, tool_choice='auto', temperature=0.1)
    except Exception as e:
        return jsonify({'success': False, 'answer': f'LLM error: {e}'}), 500
    rmsg = response.choices[0].message
    answer = None
    # Handle potential tool call similarly (simplified: we do one step; for aggregation produce chart)
    if getattr(rmsg, 'tool_calls', None):
        call = rmsg.tool_calls[0]; fname = call.function.name; import json as _json
        try:
            args = _json.loads(call.function.arguments)
        except Exception:
            args = {}
        data_res, err = execute_tool(fname, args)
        if err:
            answer = f"❌ Error: {err}"
        else:
            if fname == 'aggregate_issues':
                labels = [c['label'] for c in data_res['counts']][:40]; values = [c['value'] for c in data_res['counts']][:40]
                total = sum(values) or 1
                chart = {'title': f'Agg by {data_res['group_by']}', 'type':'bar','labels':labels,'datasets':[{'label':'Jumlah','data':values,'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],'meta':{'group_by':data_res['group_by'],'counts':data_res['counts']},'notes':'Gunakan filter'}
                header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
                rows = '\n'.join([f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |" for c in data_res['counts'][:100]])
                top3 = ', '.join([f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)" for c in data_res['counts'][:3]])
                insight = f"Insight: {top3}. Total {data_res['total']} issue." if data_res['counts'] else 'Insight: Tidak ada data.'
                answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
            else:
                # Second pass summarisation for non-aggregation
                tool_call_id = call.id
                summarizer_messages = messages_ + [
                    {"role":"assistant","content":None,"tool_calls":[{"id":tool_call_id,"type":"function","function":{"name":fname,"arguments":call.function.arguments}}]},
                    {"tool_call_id": tool_call_id, "role": "tool", "name": fname, "content": _json.dumps(data_res, ensure_ascii=False)}
                ]
                second = client.chat.completions.create(model='gpt-4o-mini', messages=summarizer_messages, temperature=0.1)
                answer = second.choices[0].message.content
    else:
        answer = rmsg.content or 'Tidak ada jawaban.'

    insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
    try:
        socketio.emit('new_message', {'chat_id': chat_id, 'sender': 'assistant', 'content': answer}, room=chat_id)
    except Exception:
        pass
    return jsonify({'success': True, 'answer': answer, 'chat_id': chat_id, 'title': title})
