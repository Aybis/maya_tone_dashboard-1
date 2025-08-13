"""Heuristic fallback for Gemini when function calling not emitted."""
from __future__ import annotations
from datetime import datetime, timedelta
import re
from typing import Optional, Tuple, Dict, Any

def gemini_fallback_tool(user_message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    msg = user_message.lower()
    if any(k in msg for k in ['worklog','log time','my hours','jam kerja']):
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d')
        return ('get_worklogs', {'from_date': from_date, 'to_date': to_date})
    if any(k in msg for k in ['chart','grafik','diagram','distribusi','distribution','count']):
        if 'priority' in msg: return ('aggregate_issues', {'group_by':'priority'})
        if 'assignee' in msg or 'assign' in msg: return ('aggregate_issues', {'group_by':'assignee'})
        if 'type' in msg or 'issuetype' in msg: return ('aggregate_issues', {'group_by':'type'})
        if 'date' in msg or 'created' in msg: return ('aggregate_issues', {'group_by':'created_date'})
        return ('aggregate_issues', {'group_by':'status'})
    if ('assign' in msg or 'ditugaskan' in msg or 'assigned' in msg) and ('me' in msg or 'saya' in msg or 'ku' in msg):
        return ('get_issues', {'jql_query': 'assignee = currentUser() ORDER BY updated DESC'})
    m = re.search(r'created by ([A-Za-z0-9_\.-]+)', msg)
    if m:
        uname = m.group(1)
        return ('get_issues', {'jql_query': f'creator = "{uname}" ORDER BY created DESC'})
    return None
