import sqlite3
from datetime import datetime
from flask import current_app as app

DB_PATH = 'maya_tone.db'

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY, title TEXT, created_at TIMESTAMP,
            updated_at TIMESTAMP, user_id TEXT, pending_action TEXT
        )''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, chat_id TEXT, content TEXT, sender TEXT,
            timestamp TIMESTAMP, FOREIGN KEY (chat_id) REFERENCES chats (id)
        )''')
    conn.commit()
    conn.close()


def insert_message(chat_id, content, sender):
    conn = get_conn(); c = conn.cursor()
    from uuid import uuid4
    c.execute('INSERT INTO messages (id, chat_id, content, sender, timestamp) VALUES (?,?,?,?,?)',
              (str(uuid4()), chat_id, content, sender, datetime.now()))
    conn.commit(); conn.close()


def fetch_recent_messages(chat_id, limit):
    conn = get_conn(); conn.row_factory = sqlite3.Row; c = conn.cursor()
    c.execute('SELECT sender, content FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?', (chat_id, limit))
    rows = c.fetchall(); conn.close()
    messages = []
    for row in rows:
        role = 'user' if row['sender'] == 'user' else 'assistant'
        messages.append({'role': role, 'content': row['content']})
    messages.reverse()
    return messages


def set_pending_action(chat_id, action_json):
    conn = get_conn(); c = conn.cursor()
    c.execute('UPDATE chats SET pending_action = ? WHERE id = ?', (action_json, chat_id))
    conn.commit(); conn.close()


def get_pending_action(chat_id):
    conn = get_conn(); c = conn.cursor()
    c.execute('SELECT pending_action FROM chats WHERE id = ?', (chat_id,))
    row = c.fetchone(); conn.close()
    return row[0] if row else None


def clear_pending_action(chat_id):
    set_pending_action(chat_id, None)


def touch_chat(chat_id):
    conn = get_conn(); c = conn.cursor()
    c.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (datetime.now(), chat_id))
    conn.commit(); conn.close()
