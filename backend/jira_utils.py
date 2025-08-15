from datetime import datetime, timedelta
from collections import Counter
from requests.auth import HTTPBasicAuth
import requests
from typing import List, Dict, Any, Optional
from .utils.session_jira import get_session_credentials
import numpy as np


class JiraManager:
    def __init__(
        self, base_url: str = None, username: str = None, password: str = None
    ):
        # Try session credentials first, fallback to params
        session_url, session_user, session_pass = get_session_credentials()

        self.base_url = (session_url or base_url or "").rstrip("/")
        self.username = session_user or username
        self.password = session_pass or password

        if self.base_url and self.username and self.password:
            self.session = requests.Session()
            self.session.auth = HTTPBasicAuth(self.username, self.password)
        else:
            self.session = None

    def get_current_user(self) -> Dict[str, Any]:
        try:
            r = self.session.get(f"{self.base_url}/rest/api/2/myself")
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        try:
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": "key,summary,status,assignee,reporter,created,updated,priority,issuetype,description,project,duedate,worklog",
            }
            r = self.session.get(f"{self.base_url}/rest/api/2/search", params=params)
            r.raise_for_status()
            return r.json().get("issues", [])
        except Exception:
            return []

    def get_worklog(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get worklog entries for a specific issue"""
        try:
            r = self.session.get(
                f"{self.base_url}/rest/api/2/issue/{issue_key}/worklog"
            )
            r.raise_for_status()
            return r.json().get("worklogs", [])
        except Exception:
            return []

    def get_personal_stats(self) -> Dict[str, Any]:
        """Get personalized stats for today, risks, and capacity"""
        current_user = self.get_current_user()
        username = current_user.get("name") or "currentUser()"
        today = datetime.now().date()

        # Today's stats
        today_stats = self._get_today_stats(username)

        # Risk stats
        risk_stats = self._get_risk_stats(username)

        # Capacity stats
        capacity_stats = self._get_capacity_stats(username, today)

        return {"today": today_stats, "risks": risk_stats, "capacity": capacity_stats}

    def _get_today_stats(self, username: str) -> Dict[str, Any]:
        """Get today's due and review stats"""
        today = datetime.now().strftime("%Y-%m-%d")

        # Due today
        due_today_jql = (
            f'assignee = "{username}" AND duedate = "{today}"'
            if username != "currentUser()"
            else f'assignee = currentUser() AND duedate = "{today}"'
        )
        due_today = self.search_issues(due_today_jql, 100)

        # Overdue
        overdue_jql = (
            f'assignee = "{username}" AND duedate < "{today}" AND status not in ("Done", "Closed", "Resolved")'
            if username != "currentUser()"
            else f'assignee = currentUser() AND duedate < "{today}" AND status not in ("Done", "Closed", "Resolved")'
        )
        overdue = self.search_issues(overdue_jql, 100)

        # Reviews waiting (issues in review status or with review-related labels)
        reviews_jql = (
            f'assignee = "{username}" AND (status in ("In Review", "Code Review", "Peer Review") OR labels in ("needs-review", "review-pending"))'
            if username != "currentUser()"
            else f'assignee = currentUser() AND (status in ("In Review", "Code Review", "Peer Review") OR labels in ("needs-review", "review-pending"))'
        )
        reviews = self.search_issues(reviews_jql, 100)

        return {
            "due_today": len(due_today),
            "overdue": len(overdue),
            "reviews_waiting": len(reviews),
        }

    def _get_risk_stats(self, username: str) -> Dict[str, Any]:
        """Get risk-related stats"""
        # Predicted slips (issues that are approaching due date but not progressing)
        today = datetime.now().date()
        near_due = today + timedelta(days=5)

        predicted_slips_jql = (
            f'assignee = "{username}" AND duedate >= "{today}" AND duedate <= "{near_due}" AND status not in ("Done", "Closed", "Resolved", "In Progress") AND updated <= "-3d"'
            if username != "currentUser()"
            else f'assignee = currentUser() AND duedate >= "{today}" AND duedate <= "{near_due}" AND status not in ("Done", "Closed", "Resolved", "In Progress") AND updated <= "-3d"'
        )
        predicted_slips = self.search_issues(predicted_slips_jql, 100)

        # Blocked issues
        blocked_jql = (
            f'assignee = "{username}" AND (status = "Blocked" OR labels in ("blocked", "waiting-on-external"))'
            if username != "currentUser()"
            else f'assignee = currentUser() AND (status = "Blocked" OR labels in ("blocked", "waiting-on-external"))'
        )
        blocked = self.search_issues(blocked_jql, 100)

        # Aging p90 - get all open issues and calculate 90th percentile of days since last update
        aging_jql = (
            f'assignee = "{username}" AND status not in ("Done", "Closed", "Resolved")'
            if username != "currentUser()"
            else f'assignee = currentUser() AND status not in ("Done", "Closed", "Resolved")'
        )
        aging_issues = self.search_issues(aging_jql, 200)

        aging_days = []
        for issue in aging_issues:
            updated_str = issue.get("fields", {}).get("updated", "")
            if updated_str:
                try:
                    updated_date = datetime.fromisoformat(
                        updated_str.replace("Z", "+00:00")
                    ).date()
                    days_since_update = (datetime.now().date() - updated_date).days
                    aging_days.append(days_since_update)
                except:
                    pass

        aging_p90 = int(np.percentile(aging_days, 90)) if aging_days else 0

        return {
            "predicted_slips": len(predicted_slips),
            "blocked_count": len(blocked),
            "aging_p90_days": aging_p90,
        }

    def _get_capacity_stats(
        self, username: str, today: datetime.date
    ) -> Dict[str, Any]:
        """Get capacity and time tracking stats"""
        # Get issues worked on today
        today_str = today.strftime("%Y-%m-%d")

        # Find issues updated today by the user
        worked_today_jql = (
            f'assignee = "{username}" AND updated >= "{today_str}"'
            if username != "currentUser()"
            else f'assignee = currentUser() AND updated >= "{today_str}"'
        )
        worked_today = self.search_issues(worked_today_jql, 100)

        # Calculate hours logged today (this is simplified - in real implementation you'd use worklog API)
        hours_logged = 0
        for issue in worked_today[:10]:  # Limit to avoid too many API calls
            try:
                worklog = self.get_worklog(issue.get("key"))
                for entry in worklog:
                    started_date = datetime.fromisoformat(
                        entry.get("started", "").replace("Z", "+00:00")
                    ).date()
                    if started_date == today:
                        hours_logged += entry.get("timeSpentSeconds", 0) / 3600
            except:
                pass

        # Target hours (could be configurable)
        target_hours = 8

        # Suggested logs (issues that might need time logging)
        suggested_logs = len(
            [
                i
                for i in worked_today
                if "In Progress"
                in str(i.get("fields", {}).get("status", {}).get("name", ""))
            ]
        )

        return {
            "hours_logged_today": round(hours_logged, 1),
            "target_hours_today": target_hours,
            "suggested_logs": suggested_logs,
        }

    def get_dashboard_stats(self) -> Dict[str, Any]:
        current_user = self.get_current_user()
        username = current_user.get("name") or "currentUser()"
        queries = {
            "my_open": (
                f'assignee = "{username}" AND status not in ("Done", "Closed")'
                if username != "currentUser()"
                else 'assignee = currentUser() AND status not in ("Done", "Closed")'
            ),
            "my_total": (
                f'assignee = "{username}"'
                if username != "currentUser()"
                else "assignee = currentUser()"
            ),
            "reported_by_me": (
                f'reporter = "{username}"'
                if username != "currentUser()"
                else "reporter = currentUser()"
            ),
            "recent_activity": "updated >= -7d",
            "high_priority": 'priority in ("High", "Highest")',
            "all_open": 'status not in ("Done", "Closed", "Resolved")',
            "created_this_month": "created >= -30d",
            "resolved_this_month": 'status changed to ("Done", "Closed", "Resolved") DURING (-30d, now())',
        }
        stats = {}
        detail = {}
        for k, q in queries.items():
            issues = self.search_issues(q, 100)
            stats[k] = len(issues)
            detail[k] = issues
        status_counts = Counter()
        priority_counts = Counter()
        assignee_counts = Counter()
        type_counts = Counter()
        all_issues = self.search_issues("updated >= -30d", 200)
        for issue in all_issues:
            f = issue.get("fields", {})
            status_counts[(f.get("status") or {}).get("name", "Unknown")] += 1
            priority_counts[(f.get("priority") or {}).get("name", "Medium")] += 1
            assignee_counts[
                (f.get("assignee") or {}).get("displayName", "Unassigned")
            ] += 1
            type_counts[(f.get("issuetype") or {}).get("name", "Unknown")] += 1
        prev_month = self.search_issues("created >= -60d AND created <= -30d", 100)
        prev_count = len(prev_month)
        curr_count = stats.get("created_this_month", 0)
        growth = (
            ((curr_count - prev_count) / prev_count * 100)
            if prev_count
            else (100 if curr_count else 0)
        )

        # Add personal stats
        personal_stats = self.get_personal_stats()

        return {
            "summary": {
                "my_open_tickets": stats.get("my_open", 0),
                "my_total_tickets": stats.get("my_total", 0),
                "reported_by_me": stats.get("reported_by_me", 0),
                "recent_activity": stats.get("recent_activity", 0),
                "high_priority": stats.get("high_priority", 0),
                "all_open_tickets": stats.get("all_open", 0),
                "created_this_month": stats.get("created_this_month", 0),
                "resolved_this_month": stats.get("resolved_this_month", 0),
            },
            "personal": personal_stats,
            "distributions": {
                "status": dict(status_counts.most_common()),
                "priority": dict(priority_counts.most_common()),
                "assignees": dict(assignee_counts.most_common(10)),
                "types": dict(type_counts.most_common()),
            },
            "trends": {
                "created_this_month": curr_count,
                "created_last_month": prev_count,
                "growth_rate": round(growth, 1),
            },
            "recent_tickets": self._format_tickets(
                detail.get("recent_activity", [])[:10]
            ),
        }

    def _format_tickets(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for issue in issues:
            f = issue.get("fields", {})
            out.append(
                {
                    "key": issue.get("key"),
                    "summary": f.get("summary", "No summary"),
                    "status": (f.get("status") or {}).get("name", "Unknown"),
                    "assignee": (f.get("assignee") or {}).get(
                        "displayName", "Unassigned"
                    ),
                    "priority": (f.get("priority") or {}).get("name", "Medium"),
                    "updated": (f.get("updated") or "")[:10],
                    "url": f"{self.base_url}/browse/{issue.get('key')}",
                }
            )
        return out


# Aggregation for visualization
from typing import Optional, Tuple
from collections import Counter as _Counter


def aggregate_issues(
    jira_manager: JiraManager,
    group_by: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    jql_extra: Optional[str] = None,
    max_results: int = 500,  # This limits Jira API results, not chart groups
) -> Tuple[Optional[dict], Optional[str]]:
    if jira_manager is None:
        return None, "Jira manager belum terinisialisasi."
    
    allowed = {"status", "priority", "assignee", "type", "created_date"}
    if group_by not in allowed:
        return None, f"group_by harus salah satu dari {allowed}"
    
    clauses = []
    date_field = "created" if group_by == "created_date" else "updated"
    if from_date:
        clauses.append(f'{date_field} >= "{from_date}"')
    if to_date:
        clauses.append(f'{date_field} <= "{to_date}"')
    if jql_extra:
        clauses.append(f"({jql_extra})")
    
    jql = " AND ".join(clauses) if clauses else f"{date_field} >= -30d"
    
    issues = jira_manager.search_issues(jql, max_results)
    counter = _Counter()
    
    # Collect distinct values
    distinct_status = set()
    distinct_assignee = set()
    distinct_project = set()
    distinct_priority = set()
    distinct_type = set()
    
    for issue in issues:
        f = issue.get("fields", {})
        
        # Determine the grouping key
        if group_by == "status":
            key = (f.get("status") or {}).get("name", "Unknown")
        elif group_by == "priority":
            key = (f.get("priority") or {}).get("name", "Medium")
        elif group_by == "assignee":
            key = (f.get("assignee") or {}).get("displayName", "Unassigned")
        elif group_by == "type":
            key = (f.get("issuetype") or {}).get("name", "Unknown")
        elif group_by == "created_date":
            key = (f.get("created") or "")[:10] or "Unknown"
        else:
            key = "Unknown"
        
        counter[key] += 1
        
        # Collect distincts for filters
        distinct_status.add((f.get("status") or {}).get("name", "Unknown"))
        distinct_priority.add((f.get("priority") or {}).get("name", "Medium"))
        distinct_assignee.add((f.get("assignee") or {}).get("displayName", "Unassigned"))
        distinct_type.add((f.get("issuetype") or {}).get("name", "Unknown"))
        proj = (f.get("project") or {}).get("key") if f.get("project") else None
        if proj:
            distinct_project.add(proj)
    
    # Sort the data appropriately
    if group_by == "created_date":
        # For dates, sort chronologically (ascending by date)
        data = [
            {"label": k, "value": v}
            for k, v in sorted(counter.items(), key=lambda x: x[0])  # Sort by date string
        ]
    else:
        # For all other groupings, sort by count (descending) then by label
        data = [
            {"label": k, "value": v}
            for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))  # Sort by count desc, then label asc
        ]
    
    return (
        {
            "group_by": group_by,
            "from": from_date,
            "to": to_date,
            "total": sum(counter.values()),
            "counts": data,  # This is now properly sorted
            "jql": jql,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "distincts": {
                "status": sorted(distinct_status - {None}),
                "assignee": sorted(distinct_assignee - {None}),
                "project": sorted(distinct_project - {None}),
                "priority": sorted(distinct_priority - {None}),
                "type": sorted(distinct_type - {None}),
            },
        },
        None,
    )