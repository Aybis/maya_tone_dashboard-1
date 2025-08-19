from flask import Blueprint, request, jsonify, session
import json, sqlite3
from datetime import datetime, timedelta
from ..prompts import get_base_system_prompt
from ..config import (
    MAX_CONTEXT_MESSAGES,
    AZURE_OPENAI_DEPLOYMENT_NAME
    # AZURE_OPENAI_API_KEY,  # Commented out - used for regular OpenAI fallback logic
)
from ..db import (
    insert_message,
    fetch_recent_messages,
    get_pending_action,
    set_pending_action,
    clear_pending_action,
    touch_chat,
    get_user_chats,
    create_user_chat,
    verify_chat_ownership,
    delete_user_chat,
    update_chat_title,
)
from ..services.openai_service import get_client, check_confirmation_intent
from ..services.tool_dispatcher import execute as execute_tool
from ..extensions import socketio  # For real-time emission of assistant replies

chat_bp = Blueprint("chat", __name__)


def get_current_user():
    """Get current authenticated user from session"""
    if not session.get("logged_in"):
        return None
    return session.get("jira_username")


def require_auth():
    """Check if user is authenticated, return user_id or error response"""
    user_id = get_current_user()
    if not user_id:
        return None, (
            jsonify({"success": False, "error": "Authentication required"}),
            401,
        )
    return user_id, None


def detect_chart_type(user_message: str, group_by: str = None, data_counts: list = None) -> str:
    """
    Detect the appropriate chart type based on user message and data characteristics.
    
    Args:
        user_message: The user's message requesting a chart
        group_by: The field being grouped by (status, priority, etc.)
        data_counts: List of count data to analyze
    
    Returns:
        Chart type string: "pie", "doughnut", "bar", "bar-horizontal", or "line"
    """
    message_lower = user_message.lower()
    
    # Explicit chart type requests
    if any(word in message_lower for word in ["pie chart", "pie", "circular"]):
        return "pie"
    if any(word in message_lower for word in ["doughnut", "donut", "ring"]):
        return "doughnut"
    if any(word in message_lower for word in ["line chart", "line", "trend", "over time"]):
        return "line"
    if any(word in message_lower for word in ["horizontal bar", "horizontal"]):
        return "bar-horizontal"
    if any(word in message_lower for word in ["bar chart", "bar", "column"]):
        return "bar"
    
    # Smart defaults based on data characteristics
    if group_by == "created_date" or "time" in message_lower or "trend" in message_lower:
        return "line"
    
    # For categorical data with few items, pie/doughnut works well
    if data_counts and len(data_counts) <= 6:
        # If user mentions distribution, proportion, or percentage, prefer pie
        if any(word in message_lower for word in ["distribution", "proportion", "percentage", "share", "breakdown"]):
            return "pie"
    
    # For many categories or when comparing values, bar is better
    if data_counts and len(data_counts) > 10:
        return "bar"
    
    # Default fallback
    return "bar"


def get_model_name():
    """Return the Azure OpenAI deployment name."""
    return AZURE_OPENAI_DEPLOYMENT_NAME
    # return AZURE_OPENAI_DEPLOYMENT_NAME if AZURE_OPENAI_API_KEY else "gpt-4o-mini"  # Commented out - regular OpenAI fallback


# ---- Tool schema builder ---------------------------------------------------
def build_tools(current_date: str, month_start: str):
    """Return OpenAI tools schema list reused across endpoints."""
    return [
        {
            "type": "function",
            "function": {
                "name": "aggregate_issues",
                "description": "Agregasi issue untuk chart (kembalikan distribusi counts).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "enum": [
                                "status",
                                "priority",
                                "assignee",
                                "type",
                                "created_date",
                            ],
                        },
                        "from_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD mulai (opsional)",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD akhir (opsional)",
                        },
                        "max_groups": {
                            "type": "integer",
                            "description": "Batasi jumlah grup dalam chart (contoh: 5 untuk top 5 assignees). Sisanya akan digabung ke 'Others'",
                        },
                        "max_issues": {
                            "type": "integer", 
                            "description": "Batasi jumlah issue yang diambil dari Jira API (default 500, tingkatkan jika perlu data lebih lengkap)",
                        },
                        "jql_extra": {
                            "type": "string",
                            "description": "Tambahan filter JQL",
                        },
                    },
                    "required": ["group_by"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_issues",
                "description": f"Cari issue via JQL gunakan tanggal real-time: today={current_date} month_start={month_start}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jql_query": {
                            "type": "string",
                            "description": "Kueri JQL lengkap",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Batas hasil (default 50)",
                        },
                    },
                    "required": ["jql_query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_projects",
                "description": "Daftar semua project Jira (key + name).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_issue_types",
                "description": "Daftar issue types; jika project_key diberikan hanya dari project tsb.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_key": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_worklogs",
                "description": "Ambil worklog user saat ini dalam rentang tanggal (inklusi).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["from_date", "to_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_worklog",
                "description": "Buat worklog pada issue tertentu.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "time_spent_hours": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": ["issue_key", "time_spent_hours"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_worklog",
                "description": "Update worklog (waktu atau deskripsi).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "worklog_id": {"type": "string"},
                        "time_spent_hours": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": ["issue_key", "worklog_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_worklog",
                "description": "Hapus worklog tertentu.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "worklog_id": {"type": "string"},
                    },
                    "required": ["issue_key", "worklog_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "manage_issue",
                "description": "Create / update issue. Gunakan action=create|update. Untuk create/update sertakan fields di details. Tidak ada delete issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "update"], #delete disabled
                        },
                        "details": {
                            "type": "object",
                            "description": "Field issue. For update/delete sertakan issue_key.",
                            "properties": {
                                "issue_key": {"type": "string"},
                                "project_key": {"type": "string"},
                                "summary": {"type": "string"},
                                "description": {"type": "string"},
                                "acceptance_criteria": {"type": "string"},
                                "priority_name": {"type": "string", "default": "P2"},
                                "assignee_name": {"type": "string"},
                                "duedate": {"type": "string"},
                                "issuetype_name": {"type": "string", "defaulr": "Bug"},
                            },
                        },
                    },
                    "required": ["action"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_users",
                "description": "Search for users by name (fuzzy search). Use this when user mentions a name for assignment but you need to find the exact user. If project is provided, searches for assignable users in that project, otherwise searches all users.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "partial_name": {
                            "type": "string",
                            "description": "Partial name or username to search for"
                        },
                        "project": {
                            "type": "string",
                            "description": "Optional project name to check user assignability in that specific project"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 10)"
                        }
                    },
                    "required": ["partial_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "export_worklog_data",
                "description": "Export worklog data in table format for a date range. Triggered when user asks to 'export data from X to Y' or similar phrasing with start and end dates. Produces a worklog export table with specific layout and grouping by calendar day.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format (inclusive)"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format (inclusive)"
                        }
                    },
                    "required": ["start_date", "end_date"]
                }
            }
        },
    ]


@chat_bp.route("/api/chat/new", methods=["POST"])
def new_chat():
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    import random
    WORDS = [
        "Orion",
        "Lumen",
        "Echo",
        "Nova",
        "Aster",
        "Nimbus",
        "Quartz",
        "Atlas",
        "Zenith",
        "Pulse",
        "Vertex",
        "Cipher",
        "Delta",
        "Photon",
        "Vortex",
        "Comet",
        "Helix",
        "Matrix",
    ]
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"
    chat_id = create_user_chat(user_id, title)
    return jsonify({"chat_id": chat_id, "title": title})


@chat_bp.route("/api/chat/history")
def history():
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    chats = get_user_chats(user_id)
    return jsonify(chats)


@chat_bp.route("/api/chat/<chat_id>")
def messages(chat_id):
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    # Verify chat ownership
    if not verify_chat_ownership(chat_id, user_id):
        return jsonify({"success": False, "error": "Chat not found or access denied"}), 404
    
    conn = sqlite3.connect("maya_tone.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT content, sender FROM messages WHERE chat_id = ? ORDER BY timestamp ASC",
        (chat_id,),
    )
    msgs = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(msgs)


@chat_bp.route("/api/chat/<chat_id>/delete", methods=["DELETE"])
def delete_chat(chat_id):
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    success = delete_user_chat(chat_id, user_id)
    if not success:
        return jsonify({"success": False, "error": "Chat not found or access denied"}), 404
    
    return jsonify({"success": True})


@chat_bp.route("/api/chat/<chat_id>/title", methods=["PUT"])
def rename_chat(chat_id):
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    data = request.json or {}
    title = (data.get("title", "") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "Empty title"}), 400
    
    success = update_chat_title(chat_id, user_id, title)
    if not success:
        return jsonify({"success": False, "error": "Chat not found or access denied"}), 404
    
    return jsonify({"success": True})


@chat_bp.route("/api/chat/<chat_id>/ask", methods=["POST"])
def ask(chat_id):
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    # Verify chat ownership
    if not verify_chat_ownership(chat_id, user_id):
        return jsonify({"success": False, "answer": "Chat not found or access denied"}), 404
    
    payload = request.json or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."})

    # Get user from session and generate dynamic prompt
    jira_username = user_id
    system_prompt = get_base_system_prompt(jira_username)

    client = get_client()
    if not client:
        return jsonify({"success": False, "answer": "OpenAI tidak tersedia."})

    insert_message(chat_id, user_message, "user")

    def send(answer):
        insert_message(chat_id, answer, "assistant")
        touch_chat(chat_id)
        try:
            socketio.emit(
                "new_message",
                {"chat_id": chat_id, "sender": "assistant", "content": answer},
                room=chat_id,
            )
        except Exception:
            pass
        return jsonify({"success": True, "answer": answer})

    # 1. Confirmation flow check
    pending = get_pending_action(chat_id)
    if pending:
        intent = check_confirmation_intent(user_message, client).get("intent")
        clear_pending_action(chat_id)
        if intent == "cancel":
            return send("❌ Baik, aksi dibatalkan.")
        if intent == "confirm":
            action = json.loads(pending)
            name = action["name"]
            args = action["args"]
            data_res, err = execute_tool(name, args)
            if err:
                return send(f"❌ Error eksekusi: {err}")
            history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
            messages_ = (
                [{"role": "system", "content": system_prompt}]
                + history_msgs
                + [
                    {
                        "role": "assistant",
                        "content": f"✅ Aksi '{name}' sukses: {json.dumps(data_res, ensure_ascii=False)}",
                    }
                ]
            )
            second = client.chat.completions.create(
                model=get_model_name(), messages=messages_, temperature=0.1
            )
            return send(second.choices[0].message.content)

    # 2. Normal flow: build context
    history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    messages_ = [{"role": "system", "content": system_prompt}] + history_msgs
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    tools = build_tools(current_date, month_start)
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=messages_,
        tools=tools,
        tool_choice="auto",
        temperature=0.1,
    )
    rmsg = response.choices[0].message

    # 3. No tool call case
    if not getattr(rmsg, "tool_calls", None):
        if any(
            k in user_message.lower()
            for k in ["chart", "grafik", "diagram", "visual", "pie", "bar", "line"]
        ):
            data_res, err = execute_tool("aggregate_issues", {"group_by": "status"})
            counts = (data_res or {}).get("counts", []) if not err else []
            labels = [c["label"] for c in counts][:40]
            values = [c["value"] for c in counts][:40]
            total = sum(values) or 1
            chart_type = detect_chart_type(user_message, "status", counts)
            chart = {
                "title": "Distribusi Issue (Fallback)",
                "type": chart_type,
                "labels": labels,
                "datasets": [
                    {
                        "label": "Jumlah",
                        "data": values,
                        "backgroundColor": ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444"] * (len(values) // 5 + 1),
                    }
                ],
                "meta": {"group_by": "status", "filters": {}, "counts": counts},
                "notes": "Fallback",
            }
            header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
            rows = "\n".join(
                [
                    f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |"
                    for c in counts[:50]
                ]
            )
            top3 = ", ".join(
                [
                    f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)"
                    for c in counts[:3]
                ]
            )
            insight = f"Insight: Top {min(3,len(counts))}: {top3}. Total {total} issue."
            return send(
                f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
            )
        return send(rmsg.content or "Tidak ada jawaban.")

    # 4. Handle tool call result
    call = rmsg.tool_calls[0]
    fname = call.function.name
    args = json.loads(call.function.arguments)
    data_res, err = execute_tool(fname, args)
    if err:
        return send(f"❌ Error: {err}")

    if fname == "aggregate_issues":
        labels = [c["label"] for c in data_res["counts"]][:40]
        values = [c["value"] for c in data_res["counts"]][:40]
        total = sum(values) or 1
        chart_type = detect_chart_type(user_message, data_res["group_by"], data_res["counts"])
        chart = {
            "title": f"Agg by {data_res['group_by']}",
            "type": chart_type,
            "labels": labels,
            "datasets": [
                {
                    "label": "Jumlah",
                    "data": values,
                    "backgroundColor": [
                        "#3b82f6",
                        "#06b6d4",
                        "#8b5cf6",
                        "#f59e0b",
                        "#ef4444",
                    ]
                    * (len(values) // 5 + 1),
                }
            ],
            "meta": {"group_by": data_res["group_by"], "counts": data_res["counts"]},
            "notes": "Gunakan filter",
        }
        header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
        rows = "\n".join(
            [
                f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |"
                for c in data_res["counts"][:100]
            ]
        )
        top3 = ", ".join(
            [
                f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)"
                for c in data_res["counts"][:3]
            ]
        )
        insight = (
            f"Insight: {top3}. Total {data_res['total']} issue."
            if data_res["counts"]
            else "Insight: Tidak ada data."
        )
        return send(
            f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
        )

    if fname == "export_worklog_data":
        # Return the table directly without additional processing
        table_content = data_res.get("table", "No data available")
        return send(table_content)

    tool_call_id = call.id
    summarizer_messages = messages_ + [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {"name": fname, "arguments": call.function.arguments},
                }
            ],
        },
        {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "name": fname,
            "content": json.dumps(data_res, ensure_ascii=False),
        },
    ]
    second = client.chat.completions.create(
        model=get_model_name(), messages=summarizer_messages, temperature=0.1
    )
    return send(second.choices[0].message.content)


@chat_bp.route("/api/chat/<chat_id>/ask_stream", methods=["POST"])
def ask_stream(chat_id):
    user_id, error_response = require_auth()
    if error_response:
        return error_response
    
    # Verify chat ownership
    if not verify_chat_ownership(chat_id, user_id):
        return jsonify({"success": False, "answer": "Chat not found or access denied"}), 404
    
    payload = request.json or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."}), 400

    # Get user from session and generate dynamic prompt
    jira_username = user_id
    system_prompt = get_base_system_prompt(jira_username)

    client = get_client()
    if not client:
        return jsonify({"success": False, "answer": "OpenAI tidak tersedia."}), 500

    insert_message(chat_id, user_message, "user")

    history_msgs = fetch_recent_messages(chat_id, MAX_CONTEXT_MESSAGES)
    messages_ = [{"role": "system", "content": system_prompt}] + history_msgs
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    tools = build_tools(current_date, month_start)

    try:
        preview = client.chat.completions.create(
            model=get_model_name(),
            messages=messages_ + [{"role": "user", "content": user_message}],
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        rmsg = preview.choices[0].message

        if getattr(rmsg, "tool_calls", None):
            socketio.emit("assistant_start", {"chat_id": chat_id}, room=chat_id)
            call = rmsg.tool_calls[0]
            fname = call.function.name
            args = json.loads(call.function.arguments)
            data_res, err = execute_tool(fname, args)
            if err:
                answer = f"❌ Error: {err}"
                insert_message(chat_id, answer, "assistant")
                touch_chat(chat_id)
                socketio.emit(
                    "assistant_end",
                    {"chat_id": chat_id, "content": answer},
                    room=chat_id,
                )
                return jsonify({"success": True, "streamed": True})

            if fname == "aggregate_issues":
                labels = [c["label"] for c in data_res["counts"]][:40]
                values = [c["value"] for c in data_res["counts"]][:40]
                total = sum(values) or 1
                chart_type = detect_chart_type(user_message, data_res["group_by"], data_res["counts"])
                chart = {
                    "title": f"Agg by {data_res['group_by']}",
                    "type": chart_type,
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "Jumlah",
                            "data": values,
                            "backgroundColor": [
                                "#3b82f6",
                                "#06b6d4",
                                "#8b5cf6",
                                "#f59e0b",
                                "#ef4444",
                            ]
                            * (len(values) // 5 + 1),
                        }
                    ],
                    "meta": {
                        "group_by": data_res["group_by"],
                        "counts": data_res["counts"],
                    },
                    "notes": "Gunakan filter",
                }
                header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
                rows = "\n".join(
                    [
                        f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |"
                        for c in data_res["counts"][:100]
                    ]
                )
                top3 = ", ".join(
                    [
                        f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)"
                        for c in data_res["counts"][:3]
                    ]
                )
                insight = (
                    f"Insight: {top3}. Total {data_res['total']} issue."
                    if data_res["counts"]
                    else "Insight: Tidak ada data."
                )
                answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
                insert_message(chat_id, answer, "assistant")
                touch_chat(chat_id)
                socketio.emit(
                    "assistant_end",
                    {"chat_id": chat_id, "content": answer},
                    room=chat_id,
                )
                return jsonify({"success": True, "streamed": True})

            if fname == "export_worklog_data":
                # Return the table directly without additional processing
                table_content = data_res.get("table", "No data available")
                insert_message(chat_id, table_content, "assistant")
                touch_chat(chat_id)
                socketio.emit(
                    "assistant_end",
                    {"chat_id": chat_id, "content": table_content},
                    room=chat_id,
                )
                return jsonify({"success": True, "streamed": True})

            tool_call_id = call.id
            summary_payload = data_res
            try:
                if isinstance(data_res, list) and len(data_res) > 60:
                    summary_payload = {
                        "items_preview": data_res[:60],
                        "total_items": len(data_res),
                    }
                elif isinstance(data_res, dict):
                    for k, v in list(data_res.items()):
                        if isinstance(v, list) and len(v) > 60:
                            data_res[k] = {
                                "items_preview": v[:60],
                                "total_items": len(v),
                            }
                            summary_payload = data_res
            except Exception:
                pass

            summarizer_messages = messages_ + [
                {"role": "user", "content": user_message},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": fname,
                                "arguments": call.function.arguments,
                            },
                        }
                    ],
                },
                {
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": fname,
                    "content": json.dumps(summary_payload, ensure_ascii=False),
                },
            ]
            try:
                stream2 = client.chat.completions.create(
                    model=get_model_name(),
                    messages=summarizer_messages,
                    temperature=0.2,
                    stream=True,
                )
                full = []
                for chunk in stream2:
                    try:
                        delta = chunk.choices[0].delta.content
                    except Exception:
                        delta = None
                    if not delta:
                        continue
                    full.append(delta)
                    socketio.emit(
                        "assistant_delta",
                        {"chat_id": chat_id, "delta": delta},
                        room=chat_id,
                    )
                answer = "".join(full) or "(kosong)"
            except Exception as e:
                answer = f"❌ Error summarising: {e}"

            insert_message(chat_id, answer, "assistant")
            touch_chat(chat_id)
            socketio.emit(
                "assistant_end", {"chat_id": chat_id, "content": answer}, room=chat_id
            )
            return jsonify({"success": True, "streamed": True})

        socketio.emit("assistant_start", {"chat_id": chat_id}, room=chat_id)
        full = []
        stream = client.chat.completions.create(
            model=get_model_name(),
            messages=messages_ + [{"role": "user", "content": user_message}],
            temperature=0.2,
            stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if not delta:
                continue
            full.append(delta)
            socketio.emit(
                "assistant_delta", {"chat_id": chat_id, "delta": delta}, room=chat_id
            )
        answer = "".join(full) or "(kosong)"
        insert_message(chat_id, answer, "assistant")
        touch_chat(chat_id)
        socketio.emit(
            "assistant_end", {"chat_id": chat_id, "content": answer}, room=chat_id
        )
        return jsonify({"success": True, "streamed": True})
    except Exception as e:
        socketio.emit(
            "assistant_error", {"chat_id": chat_id, "error": str(e)}, room=chat_id
        )
        return jsonify({"success": False, "answer": f"Error streaming: {e}"}), 500


@chat_bp.route("/api/chat/ask_new", methods=["POST"])
def ask_new():
    payload = request.json or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."}), 400

    # Get user from session and generate dynamic prompt
    jira_username = session.get("jira_username")
    if not jira_username:
        return (
            jsonify(
                {
                    "success": False,
                    "answer": "Sesi Anda telah berakhir. Silakan login kembali.",
                }
            ),
            401,
        )
    system_prompt = get_base_system_prompt(jira_username)

    client = get_client()
    if not client:
        return jsonify({"success": False, "answer": "OpenAI tidak tersedia."}), 500

    import sqlite3, random
    from uuid import uuid4

    conn = sqlite3.connect("maya_tone.db")
    c = conn.cursor()
    WORDS = [
        "Orion",
        "Lumen",
        "Echo",
        "Nova",
        "Aster",
        "Nimbus",
        "Quartz",
        "Atlas",
        "Zenith",
        "Pulse",
        "Vertex",
        "Cipher",
        "Delta",
        "Photon",
        "Vortex",
        "Comet",
        "Helix",
        "Matrix",
    ]
    chat_id = str(uuid4())
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"
    c.execute(
        "INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?,?,?,?,?)",
        (chat_id, title, datetime.now(), datetime.now(), "user"),
    )
    conn.commit()
    conn.close()

    insert_message(chat_id, user_message, "user")
    try:
        socketio.emit(
            "new_message",
            {"chat_id": chat_id, "sender": "user", "content": user_message},
            room=chat_id,
        )
    except Exception:
        pass

    messages_ = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    tools = build_tools(current_date, month_start)

    try:
        response = client.chat.completions.create(
            model=get_model_name(),
            messages=messages_,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
    except Exception as e:
        return jsonify({"success": False, "answer": f"LLM error: {e}"}), 500

    rmsg = response.choices[0].message
    answer = None

    if getattr(rmsg, "tool_calls", None):
        call = rmsg.tool_calls[0]
        fname = call.function.name
        import json as _json

        try:
            args = _json.loads(call.function.arguments)
        except Exception:
            args = {}
        data_res, err = execute_tool(fname, args)
        if err:
            answer = f"❌ Error: {err}"
        else:
            if fname == "aggregate_issues":
                labels = [c["label"] for c in data_res["counts"]][:40]
                values = [c["value"] for c in data_res["counts"]][:40]
                total = sum(values) or 1
                chart_type = detect_chart_type(user_message, data_res["group_by"], data_res["counts"])
                chart = {
                    "title": f"Agg by {data_res['group_by']}",
                    "type": chart_type,
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "Jumlah",
                            "data": values,
                            "backgroundColor": [
                                "#3b82f6",
                                "#06b6d4",
                                "#8b5cf6",
                                "#f59e0b",
                                "#ef4444",
                            ]
                            * (len(values) // 5 + 1),
                        }
                    ],
                    "meta": {
                        "group_by": data_res["group_by"],
                        "counts": data_res["counts"],
                    },
                    "notes": "Gunakan filter",
                }
                header = "| Label | Jumlah | % |\n| --- | ---: | ---: |"
                rows = "\n".join(
                    [
                        f"| {c['label']} | {c['value']} | {round(c['value']*100/total,1)}% |"
                        for c in data_res["counts"][:100]
                    ]
                )
                top3 = ", ".join(
                    [
                        f"{c['label']} {c['value']} ({round(c['value']*100/total,1)}%)"
                        for c in data_res["counts"][:3]
                    ]
                )
                insight = (
                    f"Insight: {top3}. Total {data_res['total']} issue."
                    if data_res["counts"]
                    else "Insight: Tidak ada data."
                )
                answer = f"```chart\n{json.dumps(chart, ensure_ascii=False)}\n```\n\n{header}\n{rows}\n\n{insight}"
            else:
                tool_call_id = call.id
                summarizer_messages = messages_ + [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": fname,
                                    "arguments": call.function.arguments,
                                },
                            }
                        ],
                    },
                    {
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": fname,
                        "content": _json.dumps(data_res, ensure_ascii=False),
                    },
                ]
                second = client.chat.completions.create(
                    model=get_model_name(), messages=summarizer_messages, temperature=0.1
                )
                answer = second.choices[0].message.content
    else:
        answer = rmsg.content or "Tidak ada jawaban."

    insert_message(chat_id, answer, "assistant")
    touch_chat(chat_id)
    try:
        socketio.emit(
            "new_message",
            {"chat_id": chat_id, "sender": "assistant", "content": answer},
            room=chat_id,
        )
    except Exception:
        pass
    return jsonify(
        {"success": True, "answer": answer, "chat_id": chat_id, "title": title}
    )
