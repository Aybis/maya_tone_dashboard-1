from flask import Blueprint, request, jsonify
from datetime import datetime
import json, sqlite3
from ..db import insert_message, touch_chat, get_pending_action
from ..services.llm_provider import get_provider, list_providers, classify_confirmation, DEFAULT_PROVIDER
from ..services.chat_flow import handle_confirmation, first_pass, ChatFlowResult, prepare_tools
from ..services.chat_flow import build_context_messages
from ..services.tool_dispatcher import execute as execute_tool
from ..extensions import socketio
from ..prompts import BASE_SYSTEM_PROMPT
from ..db import fetch_recent_messages, clear_pending_action
from ..config import MAX_CONTEXT_MESSAGES
from ..services.tools_schema import build_jira_tools

chat_sync_bp = Blueprint('chat_sync', __name__)

@chat_sync_bp.route('/api/chat/new', methods=['POST'])
def new_chat():
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    from uuid import uuid4; import random
    chat_id = str(uuid4())
    WORDS = ['Orion','Lumen','Echo','Nova','Aster','Nimbus','Quartz','Atlas','Zenith','Pulse','Vertex','Cipher','Delta','Photon','Vortex','Comet','Helix','Matrix']
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"
    c.execute('INSERT INTO chats (id, title, created_at, updated_at, user_id, provider) VALUES (?, ?, ?, ?, ?, ?)', (chat_id, title, datetime.now(), datetime.now(), 'user', DEFAULT_PROVIDER))
    conn.commit(); conn.close(); return jsonify({'chat_id': chat_id, 'title': title, 'provider': DEFAULT_PROVIDER})

@chat_sync_bp.route('/api/chat/history')
def history():
    conn = sqlite3.connect('maya_tone.db'); conn.row_factory = sqlite3.Row
    c = conn.cursor(); c.execute('SELECT id, title, provider FROM chats ORDER BY updated_at DESC')
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(rows)

@chat_sync_bp.route('/api/chat/<chat_id>')
def messages(chat_id):
    conn = sqlite3.connect('maya_tone.db'); conn.row_factory = sqlite3.Row
    c = conn.cursor(); c.execute('SELECT content, sender FROM messages WHERE chat_id = ? ORDER BY timestamp ASC', (chat_id,))
    msgs = [dict(r) for r in c.fetchall()]; conn.close(); return jsonify(msgs)

@chat_sync_bp.route('/api/chat/<chat_id>/delete', methods=['DELETE'])
def delete_chat(chat_id):
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    c.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,)); c.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    conn.commit(); conn.close(); return jsonify({'success': True})

@chat_sync_bp.route('/api/chat/<chat_id>/title', methods=['PUT'])
def rename_chat(chat_id):
    data = request.json or {}; title = (data.get('title','') or '').strip()
    if not title: return jsonify({'success': False, 'error':'Empty title'}), 400
    conn = sqlite3.connect('maya_tone.db'); c = conn.cursor()
    c.execute('UPDATE chats SET title = ?, updated_at = ? WHERE id = ?', (title, datetime.now(), chat_id))
    conn.commit(); conn.close(); return jsonify({'success': True})

@chat_sync_bp.route('/api/chat/<chat_id>/ask', methods=['POST'])
def ask(chat_id):
    payload = request.json or {}; user_message = (payload.get('message') or '').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'})
    from ..db import get_chat_provider, insert_message
    provider_name = get_chat_provider(chat_id) or DEFAULT_PROVIDER
    provider = get_provider(provider_name)
    if not provider:
        return jsonify({'success': False, 'answer': f'LLM provider {provider_name} tidak tersedia.'})
    insert_message(chat_id, user_message, 'user')
    # Confirmation path
    conf = handle_confirmation(provider, chat_id, user_message)
    if conf:
        if conf.messages_for_second_pass:
            second = provider.chat(conf.messages_for_second_pass, tools=None, temperature=0.1)
            answer = second.content or '(kosong)'
        else:
            answer = conf.answer or '(kosong)'
        insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
        try:
            socketio.emit('new_message', {'chat_id': chat_id,'sender':'assistant','content': answer}, room=chat_id)
        except Exception: pass
        return jsonify({'success': True, 'answer': answer})
    # Normal flow
    result = first_pass(provider, chat_id, user_message)
    if result.messages_for_second_pass:
        second = provider.chat(result.messages_for_second_pass, tools=None, temperature=0.1)
        answer = second.content or '(kosong)'
    else:
        answer = result.answer or '(kosong)'
    insert_message(chat_id, answer, 'assistant'); touch_chat(chat_id)
    try:
        socketio.emit('new_message', {'chat_id': chat_id,'sender':'assistant','content': answer}, room=chat_id)
    except Exception: pass
    return jsonify({'success': True, 'answer': answer})

@chat_sync_bp.route('/api/llm/providers')
def providers():
    return jsonify(list_providers())

@chat_sync_bp.route('/api/chat/<chat_id>/provider', methods=['GET','PUT'])
def chat_provider(chat_id):
    from ..db import get_chat_provider, set_chat_provider
    if request.method == 'GET':
        return jsonify({'provider': get_chat_provider(chat_id) or DEFAULT_PROVIDER})
    data = request.json or {}
    new_provider = (data.get('provider') or '').lower()
    if new_provider not in [p['name'] for p in list_providers()]:
        return jsonify({'success': False, 'error': 'Provider tidak valid'}), 400
    if data.get('create_new', True):
        conn = sqlite3.connect('maya_tone.db'); c = conn.cursor(); import random
        from uuid import uuid4
        c.execute('SELECT title FROM chats WHERE id = ?', (chat_id,))
        row = c.fetchone(); old_title = row[0] if row else 'Chat'
        new_chat_id = str(uuid4())
        c.execute('INSERT INTO chats (id, title, created_at, updated_at, user_id, provider) VALUES (?,?,?,?,?,?)', (new_chat_id, old_title + ' (switched)', datetime.now(), datetime.now(), 'user', new_provider))
        conn.commit(); conn.close()
        return jsonify({'success': True, 'chat_id': new_chat_id, 'provider': new_provider, 'switched': True})
    set_chat_provider(chat_id, new_provider)
    return jsonify({'success': True, 'chat_id': chat_id, 'provider': new_provider, 'switched': False})
