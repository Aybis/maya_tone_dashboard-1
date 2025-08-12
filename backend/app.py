from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
import re
from typing import List, Dict, Any, Optional
from collections import Counter
import sqlite3
from uuid import uuid4
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging
from logging.handlers import RotatingFileHandler

# Import OpenAI
try:
    from openai import OpenAI
    OPENAI_VERSION = "v1"
except ImportError:
    try:
        import openai
        OPENAI_VERSION = "legacy"
    except ImportError:
        logging.error("OpenAI library tidak terinstall")
        OPENAI_VERSION = None

# Import Jira library for CRUD operations
try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    logging.error("Jira library tidak terinstall (pip install jira)")
    JIRA = None
    JIRAError = None


# Load environment variables
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY environment variable must be set and non-empty for secure session management.")
app.secret_key = secret_key
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


# --- Configuration ---
JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

# --- System Prompts ---
BASE_SYSTEM_PROMPT = f"""Anda adalah asisten AI bernama Maya. Anda hanya boleh menjawab pertanyaan dan MENGEKSEKUSI PERINTAH yang berkaitan dengan Jira Data Center (proyek, issue, tiket) dan native Jira worklog. Jika pengguna bertanya di luar topik ini, tolak dengan sopan.

**INFORMASI WAKTU SAAT INI:**
- Tanggal hari ini: {datetime.now().strftime('%Y-%m-%d')}
- Waktu saat ini: {datetime.now().strftime('%H:%M:%S')}
- Bulan ini: {datetime.now().strftime('%B %Y')}
- Bulan lalu: {(datetime.now().replace(day=1) - timedelta(days=1)).strftime('%B %Y')}

**ATURAN UTAMA ANDA:**
1.  **Fokus Ganda**: Fungsi UTAMA Anda adalah untuk (1) menjawab pertanyaan dan (2) MENGEKSEKUSI PERINTAH (seperti membuat, update, atau hapus issue/worklog) yang berkaitan dengan **Jira Data Center** menggunakan alat yang tersedia.
2.  **Tolak Pertanyaan di Luar Topik**: Jika pengguna bertanya tentang hal lain (misalnya, pengetahuan umum, cuaca, berita, atau topik lain di luar Jira), Anda HARUS menolak dengan sopan. Katakan sesuatu seperti: "Maaf, saya adalah Maya, asisten khusus untuk Jira Data Center. Saya tidak bisa menjawab pertanyaan di luar topik tersebut."
3.  **Gunakan Alat**: Selalu prioritaskan penggunaan alat (`tools`) yang tersedia untuk mendapatkan data yang akurat sebelum menjawab atau mengeksekusi perintah.
4.  **Bahasa**: Selalu jawab dalam Bahasa Indonesia / inggris yang baik dan benar.
5.  **PENTING**: Ini adalah Jira Data Center, bukan Jira Cloud. Sistem menggunakan username, bukan accountId. Worklog menggunakan native Jira API.
6.  **Issue Types**: Dukung semua issue types seperti Epic, Story, Task, Sub-task, Bug, Improvement, dll.
7.  **Custom Fields**: Sistem mendukung acceptance criteria di customfield_10561.
8.  **Memory**: Anda memiliki memori percakapan dan dapat mengingat konteks dari pesan sebelumnya dalam sesi ini.
9.  **Alur Update/Delete Worklog**: Jika pengguna ingin mengubah atau menghapus worklog, Anda harus terlebih dahulu menanyakan detail worklog tersebut (seperti issue key dan tanggal). Kemudian, gunakan tool `get_worklogs` untuk menemukan worklog yang dimaksud. Tampilkan hasilnya kepada pengguna untuk konfirmasi. Setelah pengguna memilih worklog yang benar (dan Anda mendapatkan `worklog_id`), baru panggil tool `update_worklog` atau `delete_worklog`.
10. **WAKTU REAL-TIME**: Selalu gunakan waktu dan tanggal yang akurat sesuai informasi di atas. Jangan menggunakan tanggal lama seperti Oktober 2023.

**ATURAN PEMFORMATAN:**
- Saat menampilkan daftar (seperti daftar issue atau worklog), gunakan format yang jelas dan mudah dibaca.
- Gunakan **nomor urut** untuk setiap item dalam daftar.
- Gunakan **indentasi** dan **tebal (bold)** untuk menyorot informasi penting seperti ID, Tanggal, atau Status.
- Contoh format untuk daftar worklog:
  
  📋 **Daftar Worklog untuk Issue GEMINI-6221:**
  
  1️⃣ **Worklog ID**: `1971654`
     • **Issue**: GEMINI-6221 - Solving bug AI
     • **Tanggal**: 2024-12-15
     • **Durasi**: 2 jam
     • **Deskripsi**: solving bug AI
     • **Author**: John Doe
     
  2️⃣ **Worklog ID**: `1968309`  
     • **Issue**: GEMINI-6221 - Solving bug AI
     • **Tanggal**: 2024-12-14
     • **Durasi**: 1 jam
     • **Deskripsi**: AI Development
     • **Author**: John Doe

- Format untuk daftar issue:
  
  🎫 **Daftar Issue:**
  
  1️⃣ **[PROJ-123]** - Bug di login system
     • **Status**: In Progress
     • **Assignee**: Jane Smith
     • **Priority**: High
     • **Created**: 2024-12-10
     
  2️⃣ **[PROJ-124]** - Feature request dashboard
     • **Status**: To Do  
     • **Assignee**: Unassigned
     • **Priority**: Medium
     • **Created**: 2024-12-12
"""

# --- Database Initialization ---
def init_db():
    """Initialize SQLite database for chat storage and add pending_action column if not exists."""
    conn = sqlite3.connect('maya_tone.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY, title TEXT, created_at TIMESTAMP,
            updated_at TIMESTAMP, user_id TEXT
        )''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, chat_id TEXT, content TEXT, sender TEXT,
            timestamp TIMESTAMP, FOREIGN KEY (chat_id) REFERENCES chats (id)
        )''')

    # Add pending_action column to chats table if it doesn't exist for confirmation flow
    c.execute("PRAGMA table_info(chats)")
    columns = [row[1] for row in c.fetchall()]
    if 'pending_action' not in columns:
        c.execute('ALTER TABLE chats ADD COLUMN pending_action TEXT')
        app.logger.info("Kolom 'pending_action' ditambahkan ke tabel chats.")

    conn.commit()
    conn.close()

# --- JiraManager for Dashboard (Read-Only) ---
class JiraManager:
    """This class handles read-only operations for the dashboard."""
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth

    def get_current_user(self) -> Dict[str, Any]:
        try:
            response = self.session.get(f"{self.base_url}/rest/api/2/myself")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Error getting current user: {e}")
            return {}

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                'jql': jql, 'maxResults': max_results,
                'fields': 'key,summary,status,assignee,reporter,created,updated,priority,issuetype,description'
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('issues', [])
        except Exception as e:
            app.logger.error(f"Error searching issues with JQL '{jql}': {e}")
            return []

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        try:
            # Get tickets for the current user and team
            current_user = self.get_current_user()
            username = current_user.get('name', '')
            
            if not username:
                print("Warning: No username found, using fallback queries")
                username = 'currentUser()'
            
            # Various JQL queries for dashboard stats (with safer fallbacks)
            queries = {
                'my_open': f'assignee = "{username}" AND status != "Done" AND status != "Closed"' if username != 'currentUser()' else 'assignee = currentUser() AND status != "Done" AND status != "Closed"',
                'my_total': f'assignee = "{username}"' if username != 'currentUser()' else 'assignee = currentUser()',
                'reported_by_me': f'reporter = "{username}"' if username != 'currentUser()' else 'reporter = currentUser()',
                'recent_activity': 'updated >= -7d',
                'high_priority': 'priority in ("High", "Highest")',
                'all_open': 'status not in ("Done", "Closed", "Resolved")',
                'created_this_month': 'created >= -30d',  # Fallback to last 30 days instead of startOfMonth()
                'resolved_this_month': 'status changed to ("Done", "Closed", "Resolved") DURING (-30d, now())'
            }
            
            stats = {}
            detailed_data = {}
            
            for key, jql in queries.items():
                try:
                    issues = self.search_issues(jql, 100)
                    stats[key] = len(issues)
                    detailed_data[key] = issues
                except Exception as e:
                    print(f"Error executing query {key}: {e}")
                    stats[key] = 0
                    detailed_data[key] = []
            
            status_counts = Counter()
            priority_counts = Counter()
            assignee_counts = Counter()
            type_counts = Counter()
            
            try:
                all_issues = self.search_issues('updated >= -30d', 200)
            except Exception as e:
                print(f"Error getting issues for analytics: {e}")
                all_issues = []
            
            for issue in all_issues:
                try:
                    fields = issue.get('fields', {})
                    if not fields: continue
                    
                    status_obj = fields.get('status')
                    status = status_obj.get('name', 'Unknown') if status_obj and isinstance(status_obj, dict) else 'Unknown'
                    status_counts[status] += 1
                    
                    priority_obj = fields.get('priority')
                    priority = priority_obj.get('name', 'Medium') if priority_obj and isinstance(priority_obj, dict) else 'Medium'
                    priority_counts[priority] += 1
                    
                    assignee_obj = fields.get('assignee')
                    assignee_name = assignee_obj.get('displayName', 'Unassigned') if assignee_obj and isinstance(assignee_obj, dict) else 'Unassigned'
                    assignee_counts[assignee_name] += 1
                    
                    issue_type_obj = fields.get('issuetype')
                    issue_type = issue_type_obj.get('name', 'Unknown') if issue_type_obj and isinstance(issue_type_obj, dict) else 'Unknown'
                    type_counts[issue_type] += 1
                    
                except Exception as e:
                    print(f"Error processing issue {issue.get('key', 'unknown')}: {e}")
                    continue
            
            try:
                prev_month_issues = self.search_issues('created >= -60d AND created <= -30d', 100)
                prev_month_count = len(prev_month_issues)
            except Exception as e:
                print(f"Error getting previous period issues: {e}")
                prev_month_count = 0
            
            current_month_count = stats.get('created_this_month', 0)
            if prev_month_count > 0:
                growth_rate = ((current_month_count - prev_month_count) / prev_month_count) * 100
            else:
                growth_rate = 100 if current_month_count > 0 else 0
            
            return {
                'summary': {
                    'my_open_tickets': stats.get('my_open', 0),
                    'my_total_tickets': stats.get('my_total', 0),
                    'reported_by_me': stats.get('reported_by_me', 0),
                    'recent_activity': stats.get('recent_activity', 0),
                    'high_priority': stats.get('high_priority', 0),
                    'all_open_tickets': stats.get('all_open', 0),
                    'created_this_month': stats.get('created_this_month', 0),
                    'resolved_this_month': stats.get('resolved_this_month', 0)
                },
                'distributions': {
                    'status': dict(status_counts.most_common()),
                    'priority': dict(priority_counts.most_common()),
                    'assignees': dict(assignee_counts.most_common(10)),
                    'types': dict(type_counts.most_common())
                },
                'trends': {
                    'created_this_month': current_month_count,
                    'created_last_month': prev_month_count,
                    'growth_rate': round(growth_rate, 1)
                },
                'recent_tickets': self._format_tickets(detailed_data.get('recent_activity', [])[:10])
            }
            
        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_stats()
    
    def _format_tickets(self, issues: List[Dict]) -> List[Dict]:
        """Format tickets for display"""
        tickets = []
        for issue in issues:
            fields = issue['fields']
            ticket = {
                'key': issue['key'],
                'summary': fields.get('summary', 'No summary'),
                'status': fields.get('status', {}).get('name', 'Unknown'),
                'assignee': fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned',
                'priority': fields.get('priority', {}).get('name', 'Medium') if fields.get('priority') else 'Medium',
                'updated': fields.get('updated', '')[:10] if fields.get('updated') else 'Unknown',
                'url': f"{self.base_url}/browse/{issue['key']}"
            }
            tickets.append(ticket)
        return tickets
    
    def _get_default_stats(self) -> Dict[str, Any]:
        """Return default stats if API fails"""
        return {
            'summary': {'my_open_tickets': 0, 'my_total_tickets': 0, 'reported_by_me': 0, 'recent_activity': 0, 'high_priority': 0, 'all_open_tickets': 0, 'created_this_month': 0, 'resolved_this_month': 0},
            'distributions': {'status': {}, 'priority': {}, 'assignees': {}, 'types': {}},
            'trends': {'created_this_month': 0, 'created_last_month': 0, 'growth_rate': 0},
            'recent_tickets': []
        }

# --- New Helper Functions for Advanced Chat (CRUD & Tooling) ---

def init_openai_client(api_key):
    if not api_key or not OPENAI_VERSION: return None
    try:
        return OpenAI(api_key=api_key) if OPENAI_VERSION == "v1" else openai
    except Exception as e:
        app.logger.error(f"Gagal menginisialisasi client OpenAI: {e}")
        return None

def init_jira_client_crud(jira_url, jira_username, jira_password):
    if not JIRA or not all([jira_url, jira_username, jira_password]): return None
    try:
        return JIRA(server=jira_url, basic_auth=(jira_username, jira_password))
    except Exception as e:
        app.logger.error(f"Error menginisialisasi client CRUD Jira: {e}")
        return None

def execute_jql_search(jql_query, max_results=50):
    """Wrapper to use the dashboard's JiraManager for searching."""
    try:
        issues_data = jira_manager.search_issues(jql_query, max_results)
        return issues_data, None
    except Exception as e:
        return None, str(e)

def get_all_projects(jira_client):
    if not jira_client: return None, "Jira client tidak terinisialisasi."
    try:
        projects = jira_client.projects()
        return [{"key": p.key, "name": p.name} for p in projects], None
    except Exception as e:
        return None, f"Error saat mengambil proyek: {e}"

def get_issue_types(jira_client, project_key=None):
    if not jira_client: return None, "Jira client tidak terinisialisasi."
    try:
        issue_types = jira_client.project(project_key).issueTypes if project_key else jira_client.issue_types()
        return [{"id": t.id, "name": t.name} for t in issue_types], None
    except Exception as e:
        return None, f"Error saat mengambil issue types: {e}"

def get_worklogs_from_jira(jira_client, username, from_date, to_date):
    if not all([jira_client, username, from_date, to_date]):
        return None, "Parameter tidak lengkap."
    try:
        jql = f'worklogAuthor = "{username}" AND worklogDate >= "{from_date}" AND worklogDate <= "{to_date}"'
        issues = jira_client.search_issues(jql, expand="changelog", fields="worklog,key,summary")
        worklogs = []
        for issue in issues:
            for worklog in jira_client.worklogs(issue.key):
                if worklog.author.name == username:
                    worklogs.append({
                        "issueKey": issue.key, "issueSummary": issue.fields.summary,
                        "timeSpent": worklog.timeSpent, "started": worklog.started,
                        "comment": worklog.comment, "id": worklog.id,
                    })
        return worklogs, None
    except Exception as e:
        return None, f"Error mengambil worklog: {e}"

def create_jira_worklog(jira_client, issue_key, time_spent_hours, description, date=None):
    """Create a new worklog in Jira Data Center.
    FIXED: This function now ALWAYS uses the current timestamp to avoid AI hallucination issues.
    The 'date' parameter is ignored to prevent incorrect dates.
    """
    if not jira_client: 
        return None, "Jira client tidak terinisialisasi."
    
    try:
        # FIXED: Always use the current real-time date and time.
        # This overrides any incorrect date (like October 2023) sent by the AI model.
        worklog_date = datetime.now()
        
        # Create the worklog
        worklog = jira_client.add_worklog(
            issue=issue_key,
            timeSpentSeconds=int(float(time_spent_hours) * 3600),
            comment=description,
            started=worklog_date
        )
        
        return {
            "id": worklog.id,
            "issueKey": issue_key,
            "timeSpent": worklog.timeSpent,
            "comment": worklog.comment,
            "started": worklog.started,
            "author": worklog.author.displayName if hasattr(worklog.author, 'displayName') else worklog.author.name
        }, None
        
    except Exception as e:
        return None, f"Gagal membuat worklog: {e}"

def update_jira_worklog(jira_client, issue_key, worklog_id, time_spent_hours=None, description=None):
    """Update an existing worklog in Jira Data Center"""
    if not jira_client: 
        return None, "Jira client tidak terinisialisasi."
    
    try:
        update_data = {}
        if time_spent_hours is not None:
            update_data['timeSpentSeconds'] = int(float(time_spent_hours) * 3600)
        if description is not None:
            update_data['comment'] = description
        
        if not update_data:
            return None, "Tidak ada data untuk diupdate."
        
        worklog = jira_client.worklog(issue_key, worklog_id)
        worklog.update(**update_data)
        
        return {
            "id": worklog.id, "issueKey": issue_key, "timeSpent": worklog.timeSpent,
            "comment": worklog.comment, "started": worklog.started,
            "author": worklog.author.displayName if hasattr(worklog.author, 'displayName') else worklog.author.name
        }, None
        
    except Exception as e:
        return None, f"Gagal update worklog: {e}"

def delete_jira_worklog(jira_client, issue_key, worklog_id):
    """Delete an existing worklog from Jira Data Center"""
    if not jira_client: 
        return False, "Jira client tidak terinisialisasi."
    
    try:
        worklog = jira_client.worklog(issue_key, worklog_id)
        worklog.delete()
        return True, None
        
    except Exception as e:
        return False, f"Gagal hapus worklog: {e}"

def create_jira_issue_api(jira_client, details):
    """Create a new Jira issue"""
    if not jira_client: 
        return None, "Jira client tidak terinisialisasi."
    
    try:
        if not details.get("summary") or not details.get("project_key"):
            return None, "Summary dan Project key diperlukan untuk membuat issue."
        
        issue_data = {
            "project": {"key": details["project_key"]},
            "summary": details["summary"],
            "issuetype": {"name": details.get("issuetype_name", "Task")}
        }
        if details.get("description"): issue_data["description"] = details["description"]
        if details.get("acceptance_criteria"): issue_data["customfield_10561"] = details["acceptance_criteria"]
        if details.get("priority_name"): issue_data["priority"] = {"name": details["priority_name"]}
        if details.get("assignee_name"): issue_data["assignee"] = {"name": details["assignee_name"]}
        if details.get("duedate"):
            try:
                datetime.strptime(details["duedate"], "%Y-%m-%d")
                issue_data["duedate"] = details["duedate"]
            except ValueError:
                return None, f"Format duedate tidak valid: '{details['duedate']}'."

        issue = jira_client.create_issue(fields=issue_data)
        
        return {
            "key": issue.key, "summary": issue.fields.summary, "status": issue.fields.status.name,
            "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
            "created": issue.fields.created, "url": f"{JIRA_BASE_URL}/browse/{issue.key}"
        }, None
        
    except Exception as e:
        return None, f"Gagal membuat issue: {e}"

def update_jira_issue_api(jira_client, issue_key, updates):
    if not jira_client: return None, "Jira client tidak terinisialisasi."
    try:
        issue = jira_client.issue(issue_key)
        issue.update(fields=updates)
        return issue, None
    except Exception as e:
        return None, f"Gagal update issue: {e}"

def delete_jira_issue_api(jira_client, issue_key):
    if not jira_client: return False, "Jira client tidak terinisialisasi."
    try:
        jira_client.issue(issue_key).delete()
        return True, None
    except Exception as e:
        return False, f"Gagal hapus issue: {e}"

def check_confirmation_intent(user_message, openai_client):
    """Analyzes user response for confirmation, cancellation, or other intents."""
    system_prompt = """
    Analisis respons pengguna untuk konfirmasi. Balas HANYA dengan JSON: {"intent": "confirm" | "cancel" | "other"}.
    - "confirm": ya, lanjutkan, betul, ok, gas, yakin, lanjut, benar, silahkan, iya, oke.
    - "cancel": jangan, batal, tidak, stop, gajadi, cancel, enggak.
    - "other": lainnya (jika tidak cocok dengan confirm atau cancel).
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=0.0, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        # Fallback for safety
        lower_message = user_message.lower()
        if any(word in lower_message for word in ["ya", "lanjut", "yakin", "ok", "betul", "gas", "iya", "oke"]):
            return {"intent": "confirm"}
        if any(word in lower_message for word in ["tidak", "batal", "jangan", "stop", "cancel", "enggak"]):
            return {"intent": "cancel"}
        return {"intent": "other"}

# --- Global Managers ---
jira_manager = None # For dashboard

def initialize_managers():
    """Initialize Jira manager for dashboard."""
    global jira_manager
    if not all([JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD]):
        raise ValueError("Variabel lingkungan Jira belum diatur.")
    jira_manager = JiraManager(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)

# --- Dashboard & Core API Routes ---
@app.route('/api/dashboard-stats')
def get_dashboard_stats_route():
    if jira_manager is None: return jsonify({'error': 'Jira manager not initialized'}), 500
    return jsonify(jira_manager.get_dashboard_stats())

# --- New Advanced AI Chat Routes ---

@app.route('/api/chat/new', methods=['POST'])
def create_new_chat():
    conn = sqlite3.connect('maya_tone.db')
    c = conn.cursor()
    chat_id = str(uuid4())
    # Generate a friendlier random title (two words + time)
    WORDS = [
        'Orion','Lumen','Echo','Nova','Aster','Nimbus','Quartz','Atlas','Zenith','Pulse',
        'Vertex','Cipher','Delta','Nimbus','Photon','Pulse','Vortex','Comet','Helix','Matrix'
    ]
    import random
    title = f"{random.choice(WORDS)} {random.choice(WORDS)} {datetime.now().strftime('%H:%M')}"  # e.g. "Orion Helix 14:22"
    c.execute('INSERT INTO chats (id, title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)',
              (chat_id, title, datetime.now(), datetime.now(), 'user'))
    conn.commit()
    conn.close()
    return jsonify({'chat_id': chat_id, 'title': title})

@app.route('/api/chat/history')
def get_chat_history():
    conn = sqlite3.connect('maya_tone.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, title FROM chats ORDER BY updated_at DESC')
    chats = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(chats)

@app.route('/api/chat/<chat_id>')
def get_chat_messages(chat_id):
    conn = sqlite3.connect('maya_tone.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT content, sender FROM messages WHERE chat_id = ? ORDER BY timestamp ASC', (chat_id,))
    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(messages)

# --- Confirmation Flow Helper Functions ---
def _generate_confirmation_prompt(function_name: str, args: Dict) -> str:
    """Generates a human-readable confirmation message for a destructive action."""
    if function_name == "create_worklog":
        return (f"Anda akan mencatat worklog **{args.get('time_spent_hours', 'N/A')} jam** pada issue **{args.get('issue_key', 'N/A')}** "
                f"dengan deskripsi '{args.get('description', 'N/A')}'.\n\nApakah Anda yakin ingin melanjutkan?")
    elif function_name == "update_worklog":
        updates = []
        if 'time_spent_hours' in args and args['time_spent_hours'] is not None:
            updates.append(f"waktu menjadi **{args['time_spent_hours']} jam**")
        if 'description' in args and args['description'] is not None:
            updates.append(f"deskripsi menjadi '{args['description']}'")
        return (f"Anda akan mengupdate worklog **ID {args.get('worklog_id', 'N/A')}** pada issue **{args.get('issue_key', 'N/A')}** dengan mengubah "
                f"{' dan '.join(updates)}.\n\nApakah Anda yakin?")
    elif function_name == "delete_worklog":
        return (f"Anda akan **menghapus** worklog **ID {args.get('worklog_id', 'N/A')}** dari issue **{args.get('issue_key', 'N/A')}**."
                f"\n\nAksi ini tidak dapat diurungkan. Apakah Anda yakin?")
    elif function_name == "manage_issue":
        action = args.get("action")
        details = args.get("details", {})
        if action == "create":
            return (f"Anda akan membuat **{details.get('issuetype_name', 'Issue')}** baru di proyek **{details.get('project_key', 'N/A')}** "
                    f"dengan judul '{details.get('summary', 'N/A')}'.\n\nApakah Anda yakin?")
        elif action == "update":
            return f"Anda akan mengupdate issue **{details.get('issue_key', 'N/A')}**.\n\nApakah Anda yakin ingin melanjutkan?"
        elif action == "delete":
            return (f"Anda akan **menghapus permanen** issue **{details.get('issue_key', 'N/A')}**."
                    f"\n\nAksi ini tidak dapat diurungkan. Apakah Anda yakin?")
    return "Apakah Anda yakin ingin melanjutkan dengan aksi ini?"

def _execute_tool_function(function_name: str, function_args: Dict, jira_crud_client):
    """Dispatcher to execute the correct tool function based on its name."""
    tool_result_data, tool_error = None, None

    if function_name == "manage_issue":
        action = function_args.get("action")
        details = function_args.get("details", {})
        if action == "create":
            tool_result_data, tool_error = create_jira_issue_api(jira_crud_client, details)
        elif action == "update":
            issue_key = details.pop("issue_key", None)
            tool_result_data, tool_error = update_jira_issue_api(jira_crud_client, issue_key, details)
        elif action == "delete":
            tool_result_data, tool_error = delete_jira_issue_api(jira_crud_client, details.get("issue_key"))
    elif function_name == "get_issues":
        tool_result_data, tool_error = execute_jql_search(**function_args)
    elif function_name == "get_projects":
        tool_result_data, tool_error = get_all_projects(jira_crud_client)
    elif function_name == "get_issue_types":
        tool_result_data, tool_error = get_issue_types(jira_crud_client, **function_args)
    elif function_name == "get_worklogs":
        function_args['username'] = JIRA_USERNAME
        tool_result_data, tool_error = get_worklogs_from_jira(jira_crud_client, **function_args)
    elif function_name == "create_worklog":
        tool_result_data, tool_error = create_jira_worklog(jira_crud_client, **function_args)
    elif function_name == "update_worklog":
        tool_result_data, tool_error = update_jira_worklog(jira_crud_client, **function_args)
    elif function_name == "delete_worklog":
        tool_result_data, tool_error = delete_jira_worklog(jira_crud_client, **function_args)
    else:
        tool_error = f"Fungsi '{function_name}' tidak ditemukan."
        
    return tool_result_data, tool_error

# --- Main Chat Endpoint (FIXED) ---
@app.route('/api/chat/<chat_id>/ask', methods=['POST'])
def api_ask_chat(chat_id):
    data = request.json
    user_message = data.get("message")
    if not user_message:
        return jsonify({"success": False, "answer": "Pesan tidak boleh kosong."})

    openai_client = init_openai_client(OPENAI_API_KEY)
    if not openai_client:
        return jsonify({"success": False, "answer": "Gagal inisialisasi OpenAI client."})

    conn = sqlite3.connect('maya_tone.db')
    c = conn.cursor()
    c.execute('INSERT INTO messages (id, chat_id, content, sender, timestamp) VALUES (?, ?, ?, ?, ?)',
              (str(uuid4()), chat_id, user_message, 'user', datetime.now()))
    conn.commit()

    def send_response(answer_text, close_conn=True):
        c.execute('INSERT INTO messages (id, chat_id, content, sender, timestamp) VALUES (?, ?, ?, ?, ?)',
                  (str(uuid4()), chat_id, answer_text, 'assistant', datetime.now()))
        c.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (datetime.now(), chat_id))
        conn.commit()
        if close_conn:
            conn.close()
        socketio.emit('new_message', {'chat_id': chat_id, 'content': answer_text, 'sender': 'assistant'}, room=chat_id)
        return jsonify({"success": True, "answer": answer_text})

    try:
        # --- Confirmation Flow Logic ---
        c.execute('SELECT pending_action FROM chats WHERE id = ?', (chat_id,))
        pending_result = c.fetchone()
        pending_action_json = pending_result[0] if pending_result else None

        if pending_action_json:
            pending_action = json.loads(pending_action_json)
            intent_result = check_confirmation_intent(user_message, openai_client)
            intent = intent_result.get("intent")

            # Clear the pending action from DB immediately, regardless of intent
            c.execute('UPDATE chats SET pending_action = NULL WHERE id = ?', (chat_id,))
            conn.commit()

            if intent == "confirm":
                jira_crud_client = init_jira_client_crud(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)
                tool_result_data, tool_error = _execute_tool_function(
                    pending_action['name'], pending_action['args'], jira_crud_client
                )
                if tool_error:
                    return send_response(f"❌ Terjadi kesalahan saat eksekusi: {tool_error}")

                # FIXED: Create proper message structure for summarizer
                c.execute('SELECT sender, content FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?', (chat_id, MAX_CONTEXT_MESSAGES))
                history = []
                for row in c.fetchall():
                    role = "user" if row[0] == "user" else "assistant"
                    history.append({"role": role, "content": row[1]})
                history.reverse()

                # Build proper messages for OpenAI API
                summarizer_messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}] + history
                
                # Add confirmation message and tool result properly
                summarizer_messages.append({
                    "role": "assistant", 
                    "content": f"✅ Aksi '{pending_action['name']}' berhasil dieksekusi. Hasil: {json.dumps(tool_result_data, ensure_ascii=False)}"
                })
                
                second_response = openai_client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=summarizer_messages,
                    temperature=0.1
                )
                final_answer = second_response.choices[0].message.content
                return send_response(final_answer)

            elif intent == "cancel":
                return send_response("❌ Baik, aksi telah dibatalkan.")
            # if intent is "other", fall through to normal processing for the new message

        # --- Main Tool-Calling Logic (No Pending Action) ---
        c.execute('SELECT sender, content FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?', (chat_id, MAX_CONTEXT_MESSAGES))
        history = []
        for row in c.fetchall():
            role = "user" if row[0] == "user" else "assistant"
            history.append({"role": role, "content": row[1]})
        history.reverse()

        api_call_history = [{"role": "system", "content": BASE_SYSTEM_PROMPT}] + history
        
        # FIXED: Updated tools with better descriptions and current date context
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
        last_month_end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
        
        tools = [
            {
                "type": "function", 
                "function": {
                    "name": "get_issues", 
                    "description": f"Cari issue di Jira Data Center menggunakan JQL. Gunakan tanggal real-time: hari ini = {current_date}, bulan ini mulai = {current_month_start}.", 
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "jql_query": {
                                "type": "string", 
                                "description": f"Query JQL yang valid. Contoh untuk bulan ini: 'created >= \"{current_month_start}\"' atau 'updated >= \"{current_date}\"'"
                            }
                        }, 
                        "required": ["jql_query"]
                    }
                }
            },
            {"type": "function", "function": {"name": "get_projects", "description": "Dapatkan daftar semua projek yang tersedia di Jira.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "get_issue_types", "description": "Dapatkan daftar semua issue types yang tersedia.", "parameters": {"type": "object", "properties": {"project_key": {"type": "string", "description": "Project key (opsional)"}}}}},
            {
                "type": "function", 
                "function": {
                    "name": "get_worklogs", 
                    "description": f"Ambil data worklog untuk pengguna saat ini dalam rentang tanggal. Gunakan tanggal real-time: hari ini = {current_date}, bulan ini = {current_month_start} sampai {current_date}, bulan lalu = {last_month_start} sampai {last_month_end}.", 
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "from_date": {"type": "string", "description": f"Tanggal mulai YYYY-MM-DD. Contoh: bulan ini = {current_month_start}, bulan lalu = {last_month_start}"}, 
                            "to_date": {"type": "string", "description": f"Tanggal selesai YYYY-MM-DD. Contoh: hari ini = {current_date}, bulan lalu = {last_month_end}"}
                        }, 
                        "required": ["from_date", "to_date"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "create_worklog", 
                    "description": f"Membuat worklog baru pada issue tertentu. PENTING: Worklog akan dibuat dengan timestamp saat ini ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) untuk mencegah kesalahan tanggal.", 
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "issue_key": {"type": "string", "description": "Kode issue (contoh: PROJ-123)"}, 
                            "time_spent_hours": {"type": "number", "description": "Jumlah jam yang dihabiskan"}, 
                            "description": {"type": "string", "description": "Deskripsi pekerjaan yang dilakukan"}, 
                            "date": {"type": "string", "description": "DIABAIKAN - sistem akan menggunakan tanggal saat ini secara otomatis"}
                        }, 
                        "required": ["issue_key", "time_spent_hours", "description"]
                    }
                }
            },
            {"type": "function", "function": {"name": "update_worklog", "description": "Memperbarui worklog yang sudah ada.", "parameters": {"type": "object", "properties": {"issue_key": {"type": "string"}, "worklog_id": {"type": "string"}, "time_spent_hours": {"type": "number"}, "description": {"type": "string"}}, "required": ["issue_key", "worklog_id"]}}},
            {"type": "function", "function": {"name": "delete_worklog", "description": "Menghapus worklog yang sudah ada.", "parameters": {"type": "object", "properties": {"issue_key": {"type": "string"}, "worklog_id": {"type": "string"}}, "required": ["issue_key", "worklog_id"]}}},
            {"type": "function", "function": {"name": "manage_issue", "description": "Membuat, memperbarui, atau menghapus issue di Jira.", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["create", "update", "delete"]}, "details": {"type": "object", "description": "Detail yang diperlukan untuk aksi."}}, "required": ["action", "details"]}}}
        ]

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=api_call_history, 
            tools=tools, 
            tool_choice="auto",
            temperature=0.1
        )
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if not tool_calls:
            return send_response(response_message.content)

        tool_call = tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        DESTRUCTIVE_FUNCTIONS = {"create_worklog", "update_worklog", "delete_worklog", "manage_issue"}

        if function_name in DESTRUCTIVE_FUNCTIONS:
            action_to_confirm = {"name": function_name, "args": function_args}
            c.execute('UPDATE chats SET pending_action = ? WHERE id = ?', (json.dumps(action_to_confirm), chat_id))
            conn.commit()
            confirmation_prompt = _generate_confirmation_prompt(function_name, function_args)
            return send_response(confirmation_prompt, close_conn=False)
        else:
            jira_crud_client = init_jira_client_crud(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)
            tool_result_data, tool_error = _execute_tool_function(function_name, function_args, jira_crud_client)

            if tool_error: 
                return send_response(f"❌ Error: {tool_error}")

            # Custom markdown formatting for certain functions (bypass second OpenAI summarization)
            def format_issues_markdown(issues):
                if not issues:
                    return "### 📋 Daftar Issue\nTidak ada issue ditemukan."
                from collections import Counter
                status_counter = Counter()
                priority_counter = Counter()
                assignee_counter = Counter()
                oldest = None
                newest = None
                oldest_key = newest_key = None
                lines = [f"## 📋 Daftar Issue (Total: {len(issues)})\n"]
                for idx, issue in enumerate(issues, start=1):
                    fields = issue.get('fields', {})
                    key = issue.get('key','?')
                    summary = fields.get('summary','(no summary)')
                    status = (fields.get('status') or {}).get('name','Unknown')
                    assignee = (fields.get('assignee') or {}).get('displayName','Unassigned')
                    priority = (fields.get('priority') or {}).get('name','Medium')
                    created = fields.get('created','')[:10]
                    updated = fields.get('updated','')[:10]
                    lines.append(f"{idx}. **[{key}]** - {summary}\n   • Status: {status}\n   • Assignee: {assignee}\n   • Priority: {priority}\n   • Created: {created}\n   • Updated: {updated}\n")
                    status_counter[status]+=1
                    priority_counter[priority]+=1
                    assignee_counter[assignee]+=1
                    # track oldest/newest by created/updated
                    try:
                        from datetime import datetime as _dt
                        created_dt = _dt.strptime(created, '%Y-%m-%d') if created else None
                        updated_dt = _dt.strptime(updated, '%Y-%m-%d') if updated else None
                        if created_dt and (oldest is None or created_dt < oldest):
                            oldest = created_dt; oldest_key = key
                        if updated_dt and (newest is None or updated_dt > newest):
                            newest = updated_dt; newest_key = key
                    except Exception:
                        pass
                def fmt_counter(counter):
                    return ', '.join(f"{k}: {v}" for k,v in counter.most_common()) or '-'
                lines.append("### 🧮 Ringkasan")
                lines.append(f"- Total issues: **{len(issues)}**")
                lines.append(f"- Distinct assignees: **{len(assignee_counter)}**")
                lines.append(f"- Status breakdown: {fmt_counter(status_counter)}")
                lines.append(f"- Priority breakdown: {fmt_counter(priority_counter)}")
                if oldest:
                    lines.append(f"- Oldest created: {oldest.date()} ({oldest_key})")
                if newest:
                    lines.append(f"- Most recently updated: {newest.date()} ({newest_key})")
                top_status = status_counter.most_common(1)[0][0] if status_counter else None
                high_priorities = sum(v for k,v in priority_counter.items() if k.lower().startswith('p0') or k.lower() in ('high','highest'))
                lines.append("\n### 💡 Insight")
                if top_status:
                    lines.append(f"- Status paling umum: **{top_status}** menunjukkan area fokus saat ini.")
                lines.append(f"- Jumlah issue prioritas tinggi (P0/High): **{high_priorities}**")
                if newest and oldest:
                    age_days = (newest - oldest).days
                    lines.append(f"- Rentang umur issue (oldest to newest update): **{age_days} hari**")
                lines.append("\n> Penjelasan: Daftar di atas tersusun terurut dan ringkasan memberikan distribusi untuk membantu prioritisasi.")
                return "\n".join(lines)

            def format_worklogs_markdown(worklogs):
                if not worklogs:
                    return "### ⏱️ Worklog\nTidak ada worklog ditemukan."
                total_hours = 0.0
                by_issue = {}
                lines = [f"## ⏱️ Worklog (Total entri: {len(worklogs)})\n"]
                for idx, w in enumerate(worklogs, start=1):
                    issue_key = w.get('issueKey') or w.get('issue_key')
                    summary = w.get('issueSummary') or w.get('summary','')
                    hours = 0.0
                    # timeSpent maybe '2h' or '1h 30m'
                    ts = w.get('timeSpent') or w.get('time_spent') or ''
                    import re
                    h_match = re.search(r'(\d+(?:\.\d+)?)h', ts)
                    m_match = re.search(r'(\d+)m', ts)
                    if h_match: hours += float(h_match.group(1))
                    if m_match: hours += float(m_match.group(1))/60.0
                    total_hours += hours
                    by_issue[issue_key] = by_issue.get(issue_key, 0)+hours
                    started = w.get('started','')[:10]
                    lines.append(f"{idx}. **[{issue_key}]** {summary}\n   • Date: {started}\n   • Duration: {hours:.2f}h\n   • Comment: {w.get('comment','-')}\n")
                lines.append("### 🧮 Ringkasan")
                lines.append(f"- Total jam: **{total_hours:.2f}h**")
                lines.append(f"- Issue terbanyak: {max(by_issue, key=by_issue.get)} ({max(by_issue.values()):.2f}h)" if by_issue else "- Issue terbanyak: -")
                lines.append(f"- Rata-rata per worklog: {(total_hours/len(worklogs)):.2f}h")
                lines.append("\n### 💡 Insight\n- Distribusi jam membantu identifikasi fokus kerja. Periksa apakah jam seimbang antar issue prioritas.")
                return "\n".join(lines)

            if function_name == 'get_issues':
                try:
                    markdown = format_issues_markdown(tool_result_data or [])
                    return send_response(markdown)
                except Exception as e:
                    app.logger.error(f"Formatting issues markdown failed: {e}")
            if function_name == 'get_worklogs':
                try:
                    markdown = format_worklogs_markdown(tool_result_data or [])
                    return send_response(markdown)
                except Exception as e:
                    app.logger.error(f"Formatting worklogs markdown failed: {e}")

            # FIXED: Proper message structure for OpenAI API
            summarizer_messages = api_call_history + [
                {
                    "role": "assistant",
                    "content": None,  # Required for tool calls
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function", 
                            "function": {
                                "name": function_name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                    ]
                },
                {
                    "tool_call_id": tool_call.id, 
                    "role": "tool", 
                    "name": function_name, 
                    "content": json.dumps(tool_result_data, ensure_ascii=False)
                }
            ]
            
            second_response = openai_client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=summarizer_messages,
                temperature=0.1
            )
            final_answer = second_response.choices[0].message.content
            return send_response(final_answer)

    except Exception as e:
        app.logger.error(f"Error di /api/chat/{chat_id}/ask: {e}", exc_info=True)
        # Clean up pending action on error
        try:
            c.execute('UPDATE chats SET pending_action = NULL WHERE id = ?', (chat_id,))
            conn.commit()
        except:
            pass
        return send_response(f"❌ Terjadi error di server: {str(e)}")
    finally:
        if conn:
            conn.close()


# --- WebSocket Events ---
@socketio.on('join_chat')
def on_join_chat(data):
    chat_id = data.get('chat_id')
    if chat_id:
        join_room(chat_id)
        emit('status', {'msg': f'Joined chat {chat_id}'})

@socketio.on('leave_chat')
def on_leave_chat(data):
    chat_id = data.get('chat_id')
    if chat_id:
        leave_room(chat_id)
        emit('status', {'msg': f'Left chat {chat_id}'})

# --- Additional Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'current_date': datetime.now().strftime('%Y-%m-%d'),
        'current_time': datetime.now().strftime('%H:%M:%S'),
        'services': {
            'jira': jira_manager is not None, 
            'openai': OPENAI_API_KEY is not None
        }
    })

@app.route('/api/chat/<chat_id>/delete', methods=['DELETE'])
def delete_chat(chat_id):
    try:
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        c.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting chat {chat_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/<chat_id>/title', methods=['PUT'])
def update_chat_title(chat_id):
    try:
        data = request.json
        new_title = data.get('title', '').strip()
        if not new_title:
            return jsonify({'success': False, 'error': 'Title cannot be empty'}), 400
        
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('UPDATE chats SET title = ?, updated_at = ? WHERE id = ?', 
                  (new_title, datetime.now(), chat_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error updating chat title {chat_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# --- Main Execution ---
if __name__ == '__main__':
    if not app.debug:
        file_handler = RotatingFileHandler("app.log", maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
    
    try:
        init_db()
        initialize_managers()
        app.logger.info("✅ Maya-Tone backend initialized successfully!")
        print("🚀 Starting Maya-Tone Backend Server...")
        print(f"📊 Dashboard API: http://localhost:4000/api/dashboard-stats")
        print(f"💬 Chat API: http://localhost:4000/api/chat/")
        print(f"❤️  Health Check: http://localhost:4000/api/health")
        print(f"📅 Current Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
        socketio.run(app, host='0.0.0.0', port=4000, debug=debug_mode)
        
    except Exception as e:
        app.logger.error(f"❌ Failed to initialize application: {e}", exc_info=True)
        print(f"❌ Error starting application: {e}")
        exit(1)