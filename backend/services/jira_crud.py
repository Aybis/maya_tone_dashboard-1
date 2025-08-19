"""Jira CRUD & worklog helper functions (now using session credentials)."""

from datetime import datetime, timedelta
from ..utils.session_jira import get_session_credentials
from typing import Dict, Any

try:
    from jira import JIRA  # type: ignore
except ImportError:
    JIRA = None


def jira_client():
    base_url, username, password = get_session_credentials()
    if not JIRA or not all([base_url, username, password]):
        return None
    try:
        return JIRA(server=base_url, basic_auth=(username, password))
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
            out.append(
                {
                    "key": issue.key,
                    "fields": {
                        "summary": f.summary,
                        "status": {"name": f.status.name if f.status else None},
                        "assignee": {
                            "displayName": (
                                f.assignee.displayName if f.assignee else None
                            )
                        },
                        "priority": {"name": f.priority.name if f.priority else None},
                        "created": f.created,
                        "updated": f.updated,
                        "dueDate": f.duedate,
                        "reporter": {"displayName": f.reporter.displayName},
                        "issuetype": {"name": f.issuetype.name}
                    },
                }
            )
        return out, None
    except Exception as e:
        return None, f"Error eksekusi JQL: {e}"


def get_all_projects():
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        # Get current user
        current_user = client.current_user()
        username = current_user if isinstance(current_user, str) else current_user.name
        
        # Search for open issues where the current user is involved (assignee, reporter, or has worked on)
        jql = f"(assignee = '{username}' OR reporter = '{username}' OR worklogAuthor = '{username}') AND resolution = Unresolved"
        issues = client.search_issues(jql, maxResults=1000, fields="project")
        
        # Extract unique projects from the issues
        project_keys = set()
        for issue in issues:
            project_keys.add(issue.fields.project.key)
        
        # Get project details for the projects the user has issues in
        user_projects = []
        for project_key in project_keys:
            try:
                project = client.project(project_key)
                user_projects.append({"key": project.key, "name": project.name})
            except Exception:
                # Skip projects that can't be accessed
                continue
        
        return user_projects, None
    except Exception as e:
        return None, f"Error mengambil projek: {e}"


def get_issue_types(project_key=None):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        if project_key:
            meta = client.project(project_key)
            return [{"name": t.name} for t in meta.issueTypes], None
        return [{"name": t.name} for t in client.issue_types()], None
    except Exception as e:
        return None, f"Error issue types: {e}"


def get_worklogs(from_date: str, to_date: str, username: str):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{from_date}' AND worklogDate <= '{to_date}'"
        issues = client.search_issues(jql, maxResults=200)
        rows = []
        for issue in issues:
            try:
                for w in client.worklogs(issue.key):
                    started = getattr(w, "started", "")
                    if started and from_date <= started[:10] <= to_date:
                        author_name = getattr(
                            getattr(w, "author", None), "name", ""
                        ) or getattr(getattr(w, "author", None), "displayName", "")
                        if author_name == username:
                            rows.append(
                                {
                                    "id": w.id,
                                    "issueKey": issue.key,
                                    "issueSummary": issue.fields.summary,
                                    "comment": getattr(w, "comment", ""),
                                    "timeSpent": getattr(w, "timeSpent", ""),
                                    "started": started,
                                    "author": author_name,
                                }
                            )
            except Exception:
                continue
        return rows, None
    except Exception as e:
        return None, f"Error mengambil worklog: {e}"


def create_worklog(issue_key, time_spent_hours, description):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        wl = client.add_worklog(
            issue=issue_key,
            timeSpentSeconds=int(float(time_spent_hours) * 3600),
            comment=description,
            started=datetime.now(),
        )
        return {
            "id": wl.id,
            "issueKey": issue_key,
            "timeSpent": wl.timeSpent,
            "comment": wl.comment,
            "started": wl.started,
        }, None
    except Exception as e:
        return None, f"Gagal membuat worklog: {e}"


def update_worklog(issue_key, worklog_id, time_spent_hours=None, description=None):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        data = {}
        if time_spent_hours is not None:
            data["timeSpentSeconds"] = int(float(time_spent_hours) * 3600)
        if description is not None:
            data["comment"] = description
        if not data:
            return None, "Tidak ada data untuk diupdate."
        wl = client.worklog(issue_key, worklog_id)
        wl.update(**data)
        return {"id": wl.id, "issueKey": issue_key}, None
    except Exception as e:
        return None, f"Gagal update worklog: {e}"


def delete_worklog(issue_key, worklog_id):
    client = jira_client()
    if not client:
        return False, "Jira client tidak terinisialisasi."
    try:
        wl = client.worklog(issue_key, worklog_id)
        wl.delete()
        return True, None
    except Exception as e:
        return False, f"Gagal hapus worklog: {e}"


def create_issue(details: Dict[str, Any]):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        if not details.get("summary") or not details.get("project_key"):
            return None, "Summary dan Project key diperlukan."
        issue_data = {
            "project": {"key": details["project_key"]},
            "summary": details["summary"],
            "issuetype": {"name": details.get("issuetype_name", "Task")},
        }
        if details.get("description"):
            issue_data["description"] = details["description"]
        if details.get("acceptance_criteria"):
            issue_data["customfield_10561"] = details["acceptance_criteria"]
        if details.get("priority_name"):
            issue_data["priority"] = {"name": details["priority_name"]}
        if details.get("assignee_name"):
            issue_data["assignee"] = {"name": details["assignee_name"]}
        if details.get("duedate"):
            issue_data["duedate"] = details["duedate"]
        issue = client.create_issue(fields=issue_data)
        return {"key": issue.key}, None
    except Exception as e:
        return None, f"Gagal membuat issue: {e}"


def update_issue(issue_key, updates: Dict[str, Any]):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        field_updates = {}
        for key, value in updates.items():
            if key == "assignee_name":
                # Map pseudo field 'assignee_name' to real Jira 'assignee'
                if value is None:
                    field_updates["assignee"] = None  # Unassign
                else:
                    field_updates["assignee"] = {"name": value}
            elif key == "priority_name":
                field_updates["priority"] = {"name": value}
            elif key == "issuetype_name":
                field_updates["issuetype"] = {"name": value}
            else:
                field_updates[key] = value

        issue = client.issue(issue_key)
        issue.update(fields=field_updates)
        return {"key": issue_key}, None
    except Exception as e:
        return None, f"Gagal update issue: {e}"


def delete_issue(issue_key):
    client = jira_client()
    if not client:
        return False, "Jira client tidak terinisialisasi."
    try:
        client.issue(issue_key).delete()
        return True, None
    except Exception as e:
        return False, f"Gagal hapus issue: {e}"

def export_worklog_data(start_date: str, end_date: str, username: str, full_name: str):
    """Export worklog data in the specified table format for date range."""
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    
    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Validate date range
        if start_dt > end_dt:
            return {
                "table": "| No | Issue Key | Issue Summary | Hours | MD | Work Date | Username | Full Name | Project Name | Activities Type |\n|---|---|---|---|---|---|---|---|---|---|\n| 1 |  | Invalid date range | 0 | 1 | " + start_date + " | " + username + " | " + full_name + " |  |  |"
            }, None
        
        # Get all worklogs for the user in the date range
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{start_date}' AND worklogDate <= '{end_date}'"
        issues = client.search_issues(jql, maxResults=500, expand="changelog")
        
        # Collect all worklogs with issue details
        worklog_data = []
        project_cache = {}
        
        for issue in issues:
            try:
                # Get project name (cache to avoid repeated API calls)
                project_key = issue.fields.project.key
                if project_key not in project_cache:
                    project_cache[project_key] = issue.fields.project.name
                project_name = project_cache[project_key]
                
                # Get worklogs for this issue
                for worklog in client.worklogs(issue.key):
                    started = getattr(worklog, "started", "")
                    if started and start_date <= started[:10] <= end_date:
                        author_name = getattr(
                            getattr(worklog, "author", None), "name", ""
                        ) or getattr(getattr(worklog, "author", None), "displayName", "")
                        
                        if author_name == username:
                            # Convert time spent to hours
                            time_spent_seconds = getattr(worklog, "timeSpentSeconds", 0)
                            hours = round(time_spent_seconds / 3600, 2) if time_spent_seconds else 0
                            
                            # Get worklog description (not issue summary)
                            description = getattr(worklog, "comment", "") or "—"
                            
                            # Get activity type from worklog (default to "Development" if not available)
                            activity_type = getattr(worklog, "activityType", None)
                            if activity_type:
                                activity_type = getattr(activity_type, "name", "Development")
                            else:
                                activity_type = "Development"
                            
                            worklog_data.append({
                                "issue_key": issue.key,
                                "description": description,
                                "hours": hours,
                                "work_date": started[:10],
                                "project_name": project_name,
                                "activity_type": activity_type,
                                "created": getattr(worklog, "created", started)
                            })
            except Exception:
                continue
        
        # Get issues assigned to user for days with no worklogs
        assigned_issues_jql = f"assignee = '{username}' AND created <= '{end_date}' AND (resolved is EMPTY OR resolved >= '{start_date}')"
        try:
            assigned_issues = client.search_issues(assigned_issues_jql, maxResults=200)
            assigned_issues_map = {issue.key: issue.fields.summary for issue in assigned_issues}
        except Exception:
            assigned_issues_map = {}
        
        # Generate table for each day in range
        table_rows = []
        current_date = start_dt
        day_no = 1
        
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            day_worklogs = [w for w in worklog_data if w["work_date"] == date_str]
            
            if day_worklogs:
                # Create separate rows for each worklog, but repeat day info for visual "merged" effect
                for i, worklog in enumerate(day_worklogs):
                    # Show day number only for the first worklog, but repeat other day info for all
                    row_day_no = day_no if i == 0 else ""
                    row_md = "1"
                    row_work_date = date_str
                    row_username = username
                    row_full_name = full_name
                    row_project_name = worklog['project_name']
                    row_activity_type = worklog['activity_type']
                    
                    table_rows.append(
                        f"| {row_day_no} | {worklog['issue_key']} | {worklog['description']} | {worklog['hours']} | {row_md} | {row_work_date} | {row_username} | {row_full_name} | {row_project_name} | {row_activity_type} |"
                    )
            else:
                # No worklogs for this day - show issue title according to issue key
                if assigned_issues_map:
                    # Get first available issue key and its title
                    issue_key = next(iter(assigned_issues_map.keys()), "")
                    issue_title = assigned_issues_map.get(issue_key, "")
                else:
                    issue_key = ""
                    issue_title = ""
                
                table_rows.append(
                    f"| {day_no} | {issue_key} | {issue_title} | 0 | 1 | {date_str} | {username} | {full_name} |  |  |"
                )
            
            current_date += timedelta(days=1)
            day_no += 1
        
        # Build complete table
        header = "| No | Issue Key | Issue Summary | Hours | MD | Work Date | Username | Full Name | Project Name | Activities Type |"
        separator = "|---|---|---|---|---|---|---|---|---|---|"
        table = header + "\n" + separator + "\n" + "\n".join(table_rows)
        
        return {"table": table}, None
        
    except Exception as e:
        return None, f"Error exporting worklog data: {e}"
