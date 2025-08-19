from flask import Blueprint, jsonify
from ..jira_utils import JiraManager
from ..config import JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD

# Dashboard blueprint: exposes consolidated lightweight summary metrics for quick UI rendering.
# Uses JiraManager.get_dashboard_stats() which bundles counts & distributions used by the React dashboard.
dashboard_bp = Blueprint("dashboard", __name__)
_manager = None


def _mgr():
    """JiraManager using session credentials."""
    return JiraManager()


@dashboard_bp.route("/api/dashboard-stats")
def stats():
    """Return JSON structure consumed by frontend Dashboard page.

    Structure example:
      {
        "summary": {"my_open_tickets": int, ...},
        "distributions": {"status": {...}, "priority": {...}, ...},
        "recent_tickets": [ { key, summary, status, priority, updated, assignee, url }, ... ]
      }
    """
    return jsonify(_mgr().get_dashboard_stats())
