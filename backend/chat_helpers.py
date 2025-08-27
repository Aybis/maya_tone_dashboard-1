import json

COLOR_PALETTE = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444"]

def build_chart_markdown(counts: list, group_by: str, chart_type: str, *, title_prefix: str = "Agg by", chart_title: str = None, notes: str = "Gunakan filter") -> str:
    """Return markdown response with chart code fence + table + insight.

    counts: list of {label, value}
    chart_type: resolved externally (avoid circular import)
    If chart_title provided it overrides title_prefix.
    """
    labels = [c["label"] for c in counts][:40]
    values = [c["value"] for c in counts][:40]
    total = sum(values) or 1
    title = chart_title or f"{title_prefix} {group_by}"
    chart = {
        "title": title,
        "type": chart_type,
        "labels": labels,
        "datasets": [
            {
                "label": "Jumlah",
                "data": values,
                "backgroundColor": COLOR_PALETTE * (len(values) // len(COLOR_PALETTE) + 1),
            }
        ],
        "meta": {"group_by": group_by, "counts": counts},
        "notes": notes,
    }
    header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
    rows = "\n".join(
        [
            f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |"
            for c in counts[:100]
        ]
    )
    top3 = ", ".join(
        [
            f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)"
            for c in counts[:3]
        ]
    )
    insight = (
        f"Insight: {top3}. Total {sum(values) or 0} issue." if counts else "Insight: Tidak ada data."
    )
    return f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"


def build_export_markdown(table_content: str, download_link: str = None, filename: str = None) -> str:
    """Embed download metadata in bracket tags if provided."""
    if download_link and filename:
        export_data = {"download_link": download_link, "filename": filename}
        return f"{table_content}\n\n[EXPORT_DATA]{json.dumps(export_data)}[/EXPORT_DATA]"
    return table_content or "No data available"
