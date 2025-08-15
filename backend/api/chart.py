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
        "max_results": 5?  # NEW: limit number of groups in chart
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
    max_results = data.get("max_results")  # NEW: get max_results from request

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

    # Get the original counts data
    counts_data = agg.get("counts", [])
    
    # NEW: Apply max_results limit to the aggregated data
    limited_data = counts_data
    others_count = 0
    
    if max_results and isinstance(max_results, int) and max_results > 0 and len(counts_data) > max_results:
        if group_by == "created_date":
            # For date grouping, keep chronological order and limit
            limited_data = counts_data[:max_results]
        else:
            # For other groupings, take top N by value (data is already sorted by value desc)
            limited_data = counts_data[:max_results]
            # Calculate "Others" category for remaining items
            others_items = counts_data[max_results:]
            others_count = sum(item["value"] for item in others_items)
            if others_count > 0:
                limited_data.append({"label": "Others", "value": others_count})

    labels = [item["label"] for item in limited_data]
    values = [item["value"] for item in limited_data]

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

    # Create title with appropriate suffix
    title_suffix = ""
    if max_results and len(counts_data) > max_results:
        title_suffix = f" (Top {max_results})"
    
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
            "max_results": max_results,
            "total_groups": len(counts_data),  # NEW: show original number of groups
            "showing_groups": len(limited_data),  # NEW: show limited number of groups
            "filters": {
                "status": filters.get("status", []),
                "assignee": filters.get("assignee", []),
                "project": filters.get("project", []),
            },
        },
        "notes": f"Total {agg.get('total',0)} issues across {len(counts_data)} groups" + (f", showing top {max_results}" if max_results and len(counts_data) > max_results else "") + ".",
    }
    if "distincts" in agg:
        chart_spec["distincts"] = agg["distincts"]
    
    return jsonify({"success": True, "chart": chart_spec, "raw": agg})