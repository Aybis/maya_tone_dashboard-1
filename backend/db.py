import sqlite3
from datetime import datetime
from flask import current_app as app

DB_PATH = "maya_tone.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY, title TEXT, created_at TIMESTAMP,
            updated_at TIMESTAMP, user_id TEXT, pending_action TEXT
        )"""
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, chat_id TEXT, content TEXT, sender TEXT,
            timestamp TIMESTAMP, FOREIGN KEY (chat_id) REFERENCES chats (id)
        )"""
    )
    # Add index for better performance on user-specific queries
    c.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats (user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages (chat_id)")
    conn.commit()
    conn.close()


def insert_message(chat_id, content, sender):
    conn = get_conn()
    c = conn.cursor()
    from uuid import uuid4

    c.execute(
        "INSERT INTO messages (id, chat_id, content, sender, timestamp) VALUES (?,?,?,?,?)",
        (str(uuid4()), chat_id, content, sender, datetime.now()),
    )
    conn.commit()
    conn.close()


def fetch_recent_messages(chat_id, limit):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT sender, content FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    messages = []
    for row in rows:
        role = "user" if row["sender"] == "user" else "assistant"
        messages.append({"role": role, "content": row["content"]})
    messages.reverse()
    return messages


def set_pending_action(chat_id, action_json):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE chats SET pending_action = ? WHERE id = ?", (action_json, chat_id)
    )
    conn.commit()
    conn.close()


def get_pending_action(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT pending_action FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def clear_pending_action(chat_id):
    set_pending_action(chat_id, None)


def touch_chat(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (datetime.now(), chat_id))
    conn.commit()
    conn.close()


def get_user_chats(user_id):
    """Get all chats for a specific user"""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT id, title FROM chats WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def create_user_chat(user_id, title):
    """Create a new chat for a specific user"""
    conn = get_conn()
    c = conn.cursor()
    from uuid import uuid4
    
    chat_id = str(uuid4())
    c.execute(
        "INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)",
        (chat_id, title, datetime.now(), datetime.now(), user_id),
    )
    conn.commit()
    conn.close()
    return chat_id


def verify_chat_ownership(chat_id, user_id):
    """Verify that a chat belongs to a specific user"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == user_id


def delete_user_chat(chat_id, user_id):
    """Delete a chat only if it belongs to the user"""
    conn = get_conn()
    c = conn.cursor()
    # First verify ownership
    c.execute("SELECT user_id FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    if not row or row[0] != user_id:
        conn.close()
        return False
    
    # Delete messages and chat
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    conn.commit()
    conn.close()
    return True


def update_chat_title(chat_id, user_id, title):
    """Update chat title only if it belongs to the user"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, datetime.now(), chat_id, user_id),
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0
