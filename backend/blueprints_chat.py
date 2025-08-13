from flask import Blueprint, request, jsonify
import json, sqlite3
from datetime import datetime, timedelta
from uuid import uuid4
from .config import OPENAI_API_KEY, JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD, MAX_CONTEXT_MESSAGES
from .prompts import BASE_SYSTEM_PROMPT
from .db import insert_message, fetch_recent_messages, get_pending_action, clear_pending_action, set_pending_action, touch_chat
from .jira_utils import aggregate_issues

try:
    from openai import OpenAI
    OPENAI_VERSION = 'v1'
except ImportError:
    try:
        import openai
        OPENAI_VERSION = 'legacy'
    except ImportError:
        OPENAI_VERSION = None

try:
    from jira import JIRA
except ImportError:
    JIRA = None

chat_bp = Blueprint('chat_bp', __name__)

# Helper init

def init_openai_client():
    if not OPENAI_VERSION or not OPENAI_API_KEY: return None
    return OpenAI(api_key=OPENAI_API_KEY) if OPENAI_VERSION == 'v1' else openai

def init_jira():
    if not JIRA or not all([JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD]):
        return None
    return JIRA(server=JIRA_BASE_URL, basic_auth=(JIRA_USERNAME, JIRA_PASSWORD))

# Simple function wrappers already exist in app.py; import if refactored further
from .app import _execute_tool_function, check_confirmation_intent, init_jira_client_crud, execute_jql_search, get_all_projects, get_issue_types, get_worklogs_from_jira, create_jira_worklog, update_jira_worklog, delete_jira_worklog, create_jira_issue_api, update_jira_issue_api, delete_jira_issue_api

@chat_bp.route('/api/chat/<chat_id>/ask', methods=['POST'])
def ask(chat_id):
    data = request.json or {}
    user_message = data.get('message','').strip()
    if not user_message:
        return jsonify({'success': False, 'answer': 'Pesan tidak boleh kosong.'})
    client = init_openai_client()
    if not client:
        return jsonify({'success': False, 'answer': 'OpenAI tidak tersedia.'})

    insert_message(chat_id, user_message, 'user')

    def send(answer):
        insert_message(chat_id, answer, 'assistant')
        touch_chat(chat_id)
        return jsonify({'success': True, 'answer': answer})

    # Confirmation branch
    pending_json = get_pending_action(chat_id)
    if pending_json:
        intent = check_confirmation_intent(user_message, client).get('intent')
        clear_pending_action(chat_id)
        if intent == 'cancel':
            return send('❌ Baik, aksi dibatalkan.')
        if intent == 'confirm':
            action = json.loads(pending_json)
            jira_client = init_jira_client_crud(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)
            data_result, err = _execute_tool_function(action['name'], action['args'], jira_client)
            if err:
                return send(f"❌ Error eksekusi: {err}")
            history = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
            messages = [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history + [{ 'role':'assistant', 'content': f"✅ Aksi '{action['name']}' sukses: {json.dumps(data_result, ensure_ascii=False)}" }]
            second = client.chat.completions.create(model='gpt-4o-mini', messages=messages, temperature=0.1)
            return send(second.choices[0].message.content)
        # else fallthrough

    # Normal flow
    history = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    messages = [{'role':'system','content': BASE_SYSTEM_PROMPT}] + history

    # Tools definition (duplicate of app for now; could be centralized)
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    month_start = now.replace(day=1).strftime('%Y-%m-%d')
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
    last_month_end = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

    tools = [
      {"type": "function", "function": {"name": "aggregate_issues", "description": "Agregasi issue untuk chart (status, priority, assignee, type, created_date).", "parameters": {"type":"object","properties": {"group_by":{"type":"string","enum":["status","priority","assignee","type","created_date"]},"from_date":{"type":"string"},"to_date":{"type":"string"},"jql_extra":{"type":"string"}}, "required":["group_by"]}}},
      {"type": "function", "function": {"name": "get_issues", "description": f"Query JQL bebas. Hari ini {current_date}.", "parameters": {"type":"object","properties": {"jql_query":{"type":"string"}}, "required":["jql_query"]}}}
    ]

    response = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools, tool_choice='auto', temperature=0.1)
    rmsg = response.choices[0].message
    if not rmsg.tool_calls:
        # If user asked chart but model refused (thinks out-of-scope) we add nudge: detect keywords
        if any(k in user_message.lower() for k in ['chart','grafik','diagram','visual','pie','bar','line']):
            # Force fallback aggregate status
            fallback = { 'group_by':'status' }
            agg_data, _ = aggregate_issues(chat_bp.jira_manager, **fallback) if hasattr(chat_bp,'jira_manager') else ({'counts':[]}, None)
            labels = [c['label'] for c in agg_data.get('counts',[])][:10]
            values = [c['value'] for c in agg_data.get('counts',[])][:10]
            chart_json = {
              'title': 'Distribusi Issue (Fallback)',
              'type': 'bar',
              'labels': labels,
              'datasets': [{ 'label':'Jumlah', 'data': values, 'backgroundColor':['#3b82f6']*len(values), 'borderColor':['#1d4ed8']*len(values)}],
              'meta': {'group_by':'status','from':agg_data.get('from'),'to':agg_data.get('to'),'filters':{'status':labels,'assignee':[],'project':[]}},
              'notes': 'Fallback karena tool call tidak terjadi.'
            }
            return send(f"```chart\n{json.dumps(chart_json, ensure_ascii=False)}\n```\nDistribusi fallback berdasarkan status (max 10). Anda bisa meminta filter atau tipe chart lain.")
        return send(rmsg.content)

    # Execute first tool only (simplified)
    call = rmsg.tool_calls[0]
    fname = call.function.name
    fargs = json.loads(call.function.arguments)

    if fname == 'aggregate_issues':
        agg_data, err = aggregate_issues(chat_bp.jira_manager, **fargs)
        if err:
            return send(f"❌ Error aggregate: {err}")
        labels = [c['label'] for c in agg_data['counts']][:30]
        values = [c['value'] for c in agg_data['counts']][:30]
        chart_json = {
          'title': f'Agg issues by {agg_data["group_by"]}',
          'type': 'bar',
          'labels': labels,
          'datasets': [{ 'label':'Jumlah','data': values, 'backgroundColor':['#3b82f6','#06b6d4','#8b5cf6','#f59e0b','#ef4444']*(len(values)//5+1)}],
          'meta': {'group_by': agg_data['group_by'], 'from': agg_data.get('from'), 'to': agg_data.get('to'), 'filters': {'status':[], 'assignee':[], 'project':[]}},
          'notes': 'Gunakan filter lanjutan bila diperlukan.'
        }
        return send(f"```chart\n{json.dumps(chart_json, ensure_ascii=False)}\n```\nTotal {agg_data['total']} issue. Minta tipe lain (pie/line) atau filter (assignee=...)")

    # fallback generic
    return send(rmsg.content or 'Tidak ada jawaban.')
