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
        "type": "bar" | "doughnut" | "line" | "pie"?   # optional explicit chart type override
      }

    Response JSON (success):
      { success: true, chart: { title, type, labels, datasets:[...], meta:{...} , notes, distincts? }, raw: <original aggregation> }

    Logic:
    - Builds optional JQL filter clause from provided filters.
    - Delegates aggregation to jira_utils.aggregate_issues.
    - Heuristically selects chart type if not provided.
    - Returns frontend-friendly spec including color palette.
    """
    data = request.json or {}
    group_by = data.get("group_by", "status")
    from_date = data.get("from") or None
    to_date = data.get("to") or None
    filters = data.get("filters", {}) or {}
    chart_type = data.get("type")

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

    agg, err = aggregate_issues(
        _mgr(),
        group_by=group_by,
        from_date=from_date,
        to_date=to_date,
        jql_extra=jql_extra,
    )
    if err:
        return jsonify({"success": False, "error": err}), 400

    labels = [item["label"] for item in agg.get("counts", [])]
    values = [item["value"] for item in agg.get("counts", [])]

    # Heuristic chart type if not provided
    if not chart_type:
        if group_by == "created_date":
            chart_type = "line"
        elif len(labels) <= 6:
            chart_type = "doughnut"
        else:
            chart_type = "bar"

    palette = [
        "#3b82f6",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#06b6d4",
        "#84cc16",
        "#6366f1",
        "#d946ef",
        "#f87171",
        "#0ea5e9",
        "#64748b",
    ]
    colors = [palette[i % len(palette)] for i in range(len(values))]

    chart_spec = {
        "title": f"Distribusi Issue by {group_by}",
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
            "filters": {
                "status": filters.get("status", []),
                "assignee": filters.get("assignee", []),
                "project": filters.get("project", []),
            },
        },
        "notes": f"Total {agg.get('total',0)} issue.",
    }
    if "distincts" in agg:
        chart_spec["distincts"] = agg["distincts"]
    return jsonify({"success": True, "chart": chart_spec, "raw": agg})
