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
)
from ..services.openai_service import get_client, check_confirmation_intent
from ..services.tool_dispatcher import execute as execute_tool
from ..extensions import socketio  # For real-time emission of assistant replies

chat_bp = Blueprint("chat", __name__)


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
                        "max_results": {
                            "type": "integer",
                            "description": "Batasi jumlah grup dalam chart (contoh: 5 untuk top 5). Sisanya akan digabung ke 'Others'",
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
                "description": "Create / update / delete issue. Gunakan action=create|update|delete. Untuk create/update sertakan fields di details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "update", "delete"],
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
                                "priority_name": {"type": "string"},
                                "assignee_name": {"type": "string"},
                                "duedate": {"type": "string"},
                                "issuetype_name": {"type": "string"},
                            },
                        },
                    },
                    "required": ["action"],
                },
            },
        },
    ]


@chat_bp.route("/api/chat/new", methods=["POST"])
def new_chat():
    conn = sqlite3.connect("maya_tone.db")
    c = conn.cursor()
    from uuid import uuid4
    import random

    chat_id = str(uuid4())
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
    c.execute(
        "INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)",
        (chat_id, title, datetime.now(), datetime.now(), "user"),
    )
    conn.commit()
    conn.close()
    return jsonify({"chat_id": chat_id, "title": title})


@chat_bp.route("/api/chat/history")
def history():
    conn = sqlite3.connect("maya_tone.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats ORDER BY updated_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


@chat_bp.route("/api/chat/<chat_id>")
def messages(chat_id):
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
    conn = sqlite3.connect("maya_tone.db")
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@chat_bp.route("/api/chat/<chat_id>/title", methods=["PUT"])
def rename_chat(chat_id):
    data = request.json or {}
    title = (data.get("title", "") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "Empty title"}), 400
    conn = sqlite3.connect("maya_tone.db")
    c = conn.cursor()
    c.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now(), chat_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@chat_bp.route("/api/chat/<chat_id>/ask", methods=["POST"])
def ask(chat_id):
    payload = request.json or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."})

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
            chart = {
                "title": "Distribusi Issue (Fallback)",
                "type": "bar",
                "labels": labels,
                "datasets": [
                    {
                        "label": "Jumlah",
                        "data": values,
                        "backgroundColor": ["#3b82f6"] * len(values),
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
        chart = {
            "title": f"Agg by {data_res['group_by']}",
            "type": "bar",
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
    payload = request.json or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."}), 400

    # Get user from session and generate dynamic prompt
    jira_username = session.get("jira_username")
    if not jira_username:
        socketio.emit(
            "assistant_error",
            {"chat_id": chat_id, "error": "Sesi tidak valid."},
            room=chat_id,
        )
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
                chart = {
                    "title": f"Agg by {data_res['group_by']}",
                    "type": "bar",
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
                chart = {
                    "title": f"Agg by {data_res['group_by']}",
                    "type": "bar",
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
