from datetime import datetime, timedelta
from collections import Counter
from requests.auth import HTTPBasicAuth
import requests
from typing import List, Dict, Any, Optional
from .utils.session_jira import get_session_credentials

class JiraManager:
    def __init__(self, base_url: str = None, username: str = None, password: str = None):
        # Try session credentials first, fallback to params
        session_url, session_user, session_pass = get_session_credentials()
        
        self.base_url = (session_url or base_url or '').rstrip('/')
        self.username = session_user or username
        self.password = session_pass or password
        
        if self.base_url and self.username and self.password:
            self.session = requests.Session()
            self.session.auth = HTTPBasicAuth(self.username, self.password)
        else:
            self.session = None

    def get_current_user(self) -> Dict[str, Any]:
        if not self.session:
            return {}
        try:
            r = self.session.get(f"{self.base_url}/rest/api/2/myself"); r.raise_for_status(); return r.json()
        except Exception:
            return {}

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        if not self.session:
            return []
        try:
            params = {'jql': jql, 'maxResults': max_results,
                      'fields': 'key,summary,status,assignee,reporter,created,updated,priority,issuetype,description,project'}
            r = self.session.get(f"{self.base_url}/rest/api/2/search", params=params); r.raise_for_status(); return r.json().get('issues', [])
        except Exception:
            return []

    def get_dashboard_stats(self) -> Dict[str, Any]:
        current_user = self.get_current_user()
        username = current_user.get('name') or 'currentUser()'
        queries = {
            'my_open': f'assignee = "{username}" AND status not in ("Done", "Closed")' if username != 'currentUser()' else 'assignee = currentUser() AND status not in ("Done", "Closed")',
            'my_total': f'assignee = "{username}"' if username != 'currentUser()' else 'assignee = currentUser()',
            'reported_by_me': f'reporter = "{username}"' if username != 'currentUser()' else 'reporter = currentUser()',
            'recent_activity': 'updated >= -7d',
            'high_priority': 'priority in ("High", "Highest")',
            'all_open': 'status not in ("Done", "Closed", "Resolved")',
            'created_this_month': 'created >= -30d',
            'resolved_this_month': 'status changed to ("Done", "Closed", "Resolved") DURING (-30d, now())'
        }
        stats = {}; detail = {}
        for k, q in queries.items():
            issues = self.search_issues(q, 100)
            stats[k] = len(issues); detail[k] = issues
        status_counts = Counter(); priority_counts = Counter(); assignee_counts = Counter(); type_counts = Counter()
        all_issues = self.search_issues('updated >= -30d', 200)
        for issue in all_issues:
            f = issue.get('fields', {})
            status_counts[(f.get('status') or {}).get('name', 'Unknown')] += 1
            priority_counts[(f.get('priority') or {}).get('name', 'Medium')] += 1
            assignee_counts[(f.get('assignee') or {}).get('displayName', 'Unassigned')] += 1
            type_counts[(f.get('issuetype') or {}).get('name', 'Unknown')] += 1
        prev_month = self.search_issues('created >= -60d AND created <= -30d', 100)
        prev_count = len(prev_month); curr_count = stats.get('created_this_month', 0)
        growth = ((curr_count - prev_count) / prev_count * 100) if prev_count else (100 if curr_count else 0)
        return {
            'summary': {
                'my_open_tickets': stats.get('my_open', 0),
                'my_total_tickets': stats.get('my_total', 0),
                'reported_by_me': stats.get('reported_by_me', 0),
                'recent_activity': stats.get('recent_activity', 0),
                'high_priority': stats.get('high_priority', 0),
                'all_open_tickets': stats.get('all_open', 0),
                'created_this_month': stats.get('created_this_month', 0),
                'resolved_this_month': stats.get('resolved_this_month', 0)
            },
            'distributions': {
                'status': dict(status_counts.most_common()),
                'priority': dict(priority_counts.most_common()),
                'assignees': dict(assignee_counts.most_common(10)),
                'types': dict(type_counts.most_common())
            },
            'trends': {
                'created_this_month': curr_count,
                'created_last_month': prev_count,
                'growth_rate': round(growth, 1)
            },
            'recent_tickets': self._format_tickets(detail.get('recent_activity', [])[:10])
        }

    def _format_tickets(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for issue in issues:
            f = issue.get('fields', {})
            out.append({
                'key': issue.get('key'),
                'summary': f.get('summary', 'No summary'),
                'status': (f.get('status') or {}).get('name', 'Unknown'),
                'assignee': (f.get('assignee') or {}).get('displayName', 'Unassigned'),
                'priority': (f.get('priority') or {}).get('name', 'Medium'),
                'updated': (f.get('updated') or '')[:10],
                'url': f"{self.base_url}/browse/{issue.get('key')}"
            })
        return out

# Aggregation for visualization
from typing import Optional, Tuple
from collections import Counter as _Counter

def aggregate_issues(jira_manager: JiraManager, group_by: str, from_date: Optional[str] = None, to_date: Optional[str] = None, jql_extra: Optional[str] = None, max_results: int = 500) -> Tuple[Optional[dict], Optional[str]]:
    if jira_manager is None:
        return None, 'Jira manager belum terinisialisasi.'
    allowed = {"status", "priority", "assignee", "type", "created_date"}
    if group_by not in allowed:
        return None, f"group_by harus salah satu dari {allowed}"
    clauses = []
    date_field = 'created' if group_by == 'created_date' else 'updated'
    if from_date: clauses.append(f'{date_field} >= "{from_date}"')
    if to_date: clauses.append(f'{date_field} <= "{to_date}"')
    if jql_extra: clauses.append(f'({jql_extra})')
    jql = ' AND '.join(clauses) if clauses else f'{date_field} >= -30d'
    issues = jira_manager.search_issues(jql, max_results)
    counter = _Counter()
    distinct_status = set(); distinct_assignee = set(); distinct_project = set(); distinct_priority = set(); distinct_type = set()
    for issue in issues:
        f = issue.get('fields', {})
        if group_by == 'status': key = (f.get('status') or {}).get('name', 'Unknown')
        elif group_by == 'priority': key = (f.get('priority') or {}).get('name', 'Medium')
        elif group_by == 'assignee': key = (f.get('assignee') or {}).get('displayName', 'Unassigned')
        elif group_by == 'type': key = (f.get('issuetype') or {}).get('name', 'Unknown')
        elif group_by == 'created_date': key = (f.get('created') or '')[:10] or 'Unknown'
        else: key = 'Unknown'
        counter[key] += 1
        # collect distincts
        distinct_status.add((f.get('status') or {}).get('name', 'Unknown'))
        distinct_priority.add((f.get('priority') or {}).get('name', 'Medium'))
        distinct_assignee.add((f.get('assignee') or {}).get('displayName', 'Unassigned'))
        distinct_type.add((f.get('issuetype') or {}).get('name', 'Unknown'))
        proj = (f.get('project') or {}).get('key') if f.get('project') else None
        if proj: distinct_project.add(proj)
    items = sorted(counter.items(), key=lambda x: (x[0] if group_by == 'created_date' else -x[1], x[0] if group_by != 'created_date' else ''))
    data = [{ 'label': k, 'value': v } for k, v in (items if group_by == 'created_date' else sorted(counter.items(), key=lambda x: (-x[1], x[0])))]
    return ({
        'group_by': group_by,
        'from': from_date,
        'to': to_date,
        'total': sum(counter.values()),
        'counts': data,
        'jql': jql,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'distincts': {
            'status': sorted(distinct_status - {None}),
            'assignee': sorted(distinct_assignee - {None}),
            'project': sorted(distinct_project - {None}),
            'priority': sorted(distinct_priority - {None}),
            'type': sorted(distinct_type - {None})
        }
    }, None)
