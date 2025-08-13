"""Jira CRUD & worklog helper functions (extracted from monolithic app)."""
from datetime import datetime
from ..config import JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD
from typing import Dict, Any
try:
    from jira import JIRA  # type: ignore
except ImportError:
    JIRA = None

def jira_client():
    if not JIRA or not all([JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD]):
        return None
    try:
        return JIRA(server=JIRA_BASE_URL, basic_auth=(JIRA_USERNAME, JIRA_PASSWORD))
    except Exception:
        return None

def execute_jql_search(jql_query: str, max_results: int = 50):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        issues = client.search_issues(jql_query, maxResults=max_results)
        out = []
        for issue in issues:
            f = issue.fields
            out.append({
                'key': issue.key,
                'fields': {
                    'summary': f.summary,
                    'status': {'name': f.status.name if f.status else None},
                    'assignee': {'displayName': f.assignee.displayName if f.assignee else None},
                    'priority': {'name': f.priority.name if f.priority else None},
                    'created': f.created,
                    'updated': f.updated
                }
            })
        return out, None
    except Exception as e:
        return None, f"Error eksekusi JQL: {e}"

def get_all_projects():
    client = jira_client();
    if not client: return None, "Jira client tidak tersedia"
    try:
        return [{'key': p.key, 'name': p.name} for p in client.projects()], None
    except Exception as e: return None, f"Error mengambil projek: {e}"

def get_issue_types(project_key=None):
    client = jira_client();
    if not client: return None, "Jira client tidak tersedia"
    try:
        if project_key:
            meta = client.project(project_key)
            return [{'name': t.name} for t in meta.issueTypes], None
        return [{'name': t.name} for t in client.issue_types()], None
    except Exception as e: return None, f"Error issue types: {e}"

def get_worklogs(from_date: str, to_date: str, username: str):
    client = jira_client();
    if not client: return None, "Jira client tidak tersedia"
    try:
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{from_date}' AND worklogDate <= '{to_date}'"
        issues = client.search_issues(jql, maxResults=200)
        rows = []
        for issue in issues:
            try:
                for w in client.worklogs(issue.key):
                    started = getattr(w, 'started', '')
                    if started and from_date <= started[:10] <= to_date:
                        author_name = getattr(getattr(w, 'author', None), 'name', '') or getattr(getattr(w, 'author', None), 'displayName', '')
                        if author_name == username:
                            rows.append({
                                'id': w.id,
                                'issueKey': issue.key,
                                'issueSummary': issue.fields.summary,
                                'comment': getattr(w, 'comment', ''),
                                'timeSpent': getattr(w, 'timeSpent', ''),
                                'started': started,
                                'author': author_name
                            })
            except Exception:
                continue
        return rows, None
    except Exception as e: return None, f"Error mengambil worklog: {e}"

def create_worklog(issue_key, time_spent_hours, description):
    client = jira_client();
    if not client: return None, "Jira client tidak terinisialisasi."
    try:
        wl = client.add_worklog(issue=issue_key, timeSpentSeconds=int(float(time_spent_hours)*3600), comment=description, started=datetime.now())
        return {"id": wl.id, "issueKey": issue_key, "timeSpent": wl.timeSpent, "comment": wl.comment, "started": wl.started}, None
    except Exception as e: return None, f"Gagal membuat worklog: {e}"

def update_worklog(issue_key, worklog_id, time_spent_hours=None, description=None):
    client = jira_client();
    if not client: return None, "Jira client tidak terinisialisasi."
    try:
        data = {}
        if time_spent_hours is not None: data['timeSpentSeconds'] = int(float(time_spent_hours)*3600)
        if description is not None: data['comment'] = description
        if not data: return None, "Tidak ada data untuk diupdate."
        wl = client.worklog(issue_key, worklog_id); wl.update(**data)
        return {"id": wl.id, "issueKey": issue_key}, None
    except Exception as e: return None, f"Gagal update worklog: {e}"

def delete_worklog(issue_key, worklog_id):
    client = jira_client();
    if not client: return False, "Jira client tidak terinisialisasi."
    try:
        wl = client.worklog(issue_key, worklog_id); wl.delete(); return True, None
    except Exception as e: return False, f"Gagal hapus worklog: {e}"

def create_issue(details: Dict[str, Any]):
    client = jira_client();
    if not client: return None, "Jira client tidak terinisialisasi."
    try:
        if not details.get('summary') or not details.get('project_key'):
            return None, "Summary dan Project key diperlukan."
        issue_data = {"project": {"key": details['project_key']}, "summary": details['summary'], "issuetype": {"name": details.get('issuetype_name','Task')}}
        if details.get('description'): issue_data['description'] = details['description']
        if details.get('acceptance_criteria'): issue_data['customfield_10561'] = details['acceptance_criteria']
        if details.get('priority_name'): issue_data['priority'] = {"name": details['priority_name']}
        if details.get('assignee_name'): issue_data['assignee'] = {"name": details['assignee_name']}
        if details.get('duedate'): issue_data['duedate'] = details['duedate']
        issue = client.create_issue(fields=issue_data)
        return {"key": issue.key}, None
    except Exception as e: return None, f"Gagal membuat issue: {e}"

def update_issue(issue_key, updates: Dict[str, Any]):
    client = jira_client();
    if not client: return None, "Jira client tidak terinisialisasi."
    try:
        field_updates = {}
        for key, value in updates.items():
            if key == 'assignee_name':
                # Map pseudo field 'assignee_name' to real Jira 'assignee'
                if value is None:
                    field_updates['assignee'] = None  # Unassign
                else:
                    field_updates['assignee'] = {"name": value}
            elif key == 'priority_name':
                field_updates['priority'] = {"name": value}
            elif key == 'issuetype_name':
                field_updates['issuetype'] = {"name": value}
            else:
                field_updates[key] = value
        
        issue = client.issue(issue_key)
        issue.update(fields=field_updates)
        return {"key": issue_key}, None
    except Exception as e: 
        return None, f"Gagal update issue: {e}"

def delete_issue(issue_key):
    client = jira_client();
    if not client: return False, "Jira client tidak terinisialisasi."
    try:
        client.issue(issue_key).delete(); return True, None
    except Exception as e: return False, f"Gagal hapus issue: {e}"
