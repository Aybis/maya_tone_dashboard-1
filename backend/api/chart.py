from flask import Blueprint, request, jsonify
from ..jira_utils import aggregate_issues, JiraManager
from ..config import JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD

# Blueprint exposing direct (non-LLM) chart aggregation so the frontend or
# other services can fetch aggregated counts quickly without invoking the chat flow.
chart_bp = Blueprint("chart", __name__)
_manager = None


def _mgr():
    """JiraManager using session credentials."""
    return JiraManager()


@chart_bp.route("/api/chart/aggregate", methods=["POST"])
def aggregate():
    """Aggregate Jira issues and return a ready-to-render chart spec.

    Request JSON:
      {
        "group_by": "status" | "priority" | "assignee" | "type" | "created_date",
        "from": "YYYY-MM-DD"?,
        "to": "YYYY-MM-DD"?,
        "filters": { "status":[], "assignee":[], "project":[] }?,
        "type": "bar" | "doughnut" | "line" | "pie"?,
        "max_groups": 5?  # Limit number of groups in chart
        "max_issues": 500? # Limit number of issues from Jira API
      }

    Response JSON (success):
      { success: true, chart: { title, type, labels, datasets:[...], meta:{...} , notes, distincts? }, raw: <original aggregation> }
    """
    data = request.json or {}
    group_by = data.get("group_by", "status")
    from_date = data.get("from") or None
    to_date = data.get("to") or None
    filters = data.get("filters", {}) or {}
    chart_type = data.get("type")
    max_groups = data.get("max_groups")  # Limit chart groups
    max_issues = data.get("max_issues", 500)  # Limit Jira API results

    # Build JQL filter clauses from lists (ignore 'all' semantics)
    clauses = []

    def quote_list(values):
        return ",".join(f'"{v}"' for v in values if v and str(v).lower() != "all")

    if filters.get("status"):
        q = quote_list(filters["status"])
        if q:
            clauses.append(f"status in ({q})")
    if filters.get("assignee"):
        q = quote_list(filters["assignee"])
        if q:
            clauses.append(f"assignee in ({q})")
    if filters.get("project"):
        q = quote_list(filters["project"])
        if q:
            clauses.append(f"project in ({q})")
    jql_extra = " AND ".join(clauses) if clauses else None

    # Call aggregate_issues with both max_issues and max_groups
    agg, err = aggregate_issues(
        _mgr(),
        group_by=group_by,
        from_date=from_date,
        to_date=to_date,
        jql_extra=jql_extra,
        max_issues=max_issues,  # Limit Jira API results
        max_groups=max_groups,  # Limit chart groups
    )
    if err:
        return jsonify({"success": False, "error": err}), 400

    # Get the counts data (already processed by aggregate_issues)
    counts_data = agg.get("counts", [])
    
    # Data is already limited by the function, just extract for chart
    labels = [item["label"] for item in counts_data]
    values = [item["value"] for item in counts_data]

    # Heuristic chart type selection if not provided
    if not chart_type:
        if group_by == "created_date":
            chart_type = "line"
        elif len(labels) <= 6:
            chart_type = "doughnut"
        else:
            chart_type = "bar"

    palette = [
        "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4",
        "#84cc16", "#6366f1", "#d946ef", "#f87171", "#0ea5e9", "#64748b",
    ]
    colors = [palette[i % len(palette)] for i in range(len(values))]

    # Create title with appropriate suffix
    original_groups = agg.get("total_groups", len(counts_data))
    if max_groups and original_groups > max_groups:
        title_suffix = f" (Top {max_groups})"
    
    chart_spec = {
        "title": f"Distribusi Issue by {group_by}{title_suffix}",
        "type": chart_type,
        "labels": labels,
        "datasets": [
            {
                "label": "Jumlah",
                "data": values,
                "backgroundColor": colors,
                "borderColor": colors,
            }
        ],
        "meta": {
            "group_by": group_by,
            "from": agg.get("from"),
            "to": agg.get("to"),
            "source": "jira",
            "max_groups": max_groups,
            "max_issues": max_issues,
            "total_groups": agg.get("total_groups"),  # Original number of groups
            "showing_groups": len(counts_data),  # Number of groups being shown
            "filters": {
                "status": filters.get("status", []),
                "assignee": filters.get("assignee", []),
                "project": filters.get("project", []),
            },
        },
        "notes": f"Total {agg.get('total',0)} issues across {agg.get('total_groups', len(counts_data))} groups" + (f", showing top {max_groups}" if max_groups and agg.get('total_groups', len(counts_data)) > max_groups else "") + ".",
    }
    
    if "distincts" in agg:
        chart_spec["distincts"] = agg["distincts"]
    
    return jsonify({"success": True, "chart": chart_spec, "raw": agg})