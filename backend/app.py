from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta
import openai
from dotenv import load_dotenv
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
import sqlite3
from uuid import uuid4 
from flask_socketio import SocketIO, emit, join_room, leave_room

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

socketio = SocketIO(app, cors_allowed_origins="*")

def init_db():
    """Initialize SQLite database for chat storage"""
    conn = sqlite3.connect('maya_tone.db')
    c = conn.cursor()
    
    # Create chats table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            user_id TEXT
        )
    ''')
    
    # Create messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT,
            content TEXT,
            sender TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    ''')
    
    conn.commit()
    conn.close()

class JiraManager:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def get_current_user(self) -> Dict[str, Any]:
        """Get current user information"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/2/myself")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting current user: {e}")
            return {}
    
    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for issues using JQL"""
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                'jql': jql,
                'maxResults': max_results,
                'fields': 'key,summary,status,assignee,reporter,created,updated,priority,issuetype,description'
            }
            
            print(f"Executing JQL: {jql}")
            response = self.session.get(url, params=params)
            
            if response.status_code == 401:
                print("Authentication failed - check credentials")
                return []
            elif response.status_code == 400:
                print(f"Bad JQL query: {jql}")
                print(f"Response: {response.text}")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            print(f"JQL query returned {len(issues)} issues")
            return issues
        except Exception as e:
            print(f"Error searching issues with JQL '{jql}': {e}")
            return []
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from Jira"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/2/user/search?username=.")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting users: {e}")
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
                'my_open': f'assignee = {username} AND status != "Done" AND status != "Closed"' if username != 'currentUser()' else 'assignee = currentUser() AND status != "Done" AND status != "Closed"',
                'my_total': f'assignee = {username}' if username != 'currentUser()' else 'assignee = currentUser()',
                'reported_by_me': f'reporter = {username}' if username != 'currentUser()' else 'reporter = currentUser()',
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
                    print(f"Executing query {key}: {jql}")
                    issues = self.search_issues(jql, 100)
                    stats[key] = len(issues)
                    detailed_data[key] = issues
                    print(f"Query {key} returned {len(issues)} results")
                except Exception as e:
                    print(f"Error executing query {key}: {e}")
                    stats[key] = 0
                    detailed_data[key] = []
            
            # Process status distribution with safer approach
            status_counts = Counter()
            priority_counts = Counter()
            assignee_counts = Counter()
            type_counts = Counter()
            
            # Get broader dataset for analytics - use simpler query
            try:
                all_issues = self.search_issues('updated >= -30d', 200)
                print(f"Retrieved {len(all_issues)} issues for analytics")
            except Exception as e:
                print(f"Error getting issues for analytics: {e}")
                all_issues = []
            
            for issue in all_issues:
                fields = issue['fields']
                
                # Status distribution
                status = fields.get('status', {}).get('name', 'Unknown')
                status_counts[status] += 1
                
                # Priority distribution
                priority = fields.get('priority', {}).get('name', 'Unknown')
                priority_counts[priority] += 1
                
                # Assignee distribution (top 10)
                assignee = fields.get('assignee')
                assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
                assignee_counts[assignee_name] += 1
                
                # Issue type distribution
                issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
                type_counts[issue_type] += 1
            
            # Calculate trends (compare with previous period) - use safer query
            try:
                prev_month_issues = self.search_issues('created >= -60d AND created <= -30d', 100)
                prev_month_count = len(prev_month_issues)
                print(f"Previous period issues: {prev_month_count}")
            except Exception as e:
                print(f"Error getting previous period issues: {e}")
                prev_month_count = 0
            
            return {
                'summary': {
                    'my_open_tickets': stats['my_open'],
                    'my_total_tickets': stats['my_total'],
                    'reported_by_me': stats['reported_by_me'],
                    'recent_activity': stats['recent_activity'],
                    'high_priority': stats['high_priority'],
                    'all_open_tickets': stats['all_open'],
                    'created_this_month': stats['created_this_month'],
                    'resolved_this_month': stats['resolved_this_month']
                },
                'distributions': {
                    'status': dict(status_counts.most_common()),
                    'priority': dict(priority_counts.most_common()),
                    'assignees': dict(assignee_counts.most_common(10)),
                    'types': dict(type_counts.most_common())
                },
                'trends': {
                    'created_this_month': stats.get('created_this_month', 0),
                    'created_last_month': prev_month_count,
                    'growth_rate': ((stats.get('created_this_month', 0) - prev_month_count) / max(prev_month_count, 1)) * 100
                },
                'recent_tickets': self._format_tickets(detailed_data.get('recent_activity', [])[:10])
            }
            
        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
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
            'summary': {
                'my_open_tickets': 0,
                'my_total_tickets': 0,
                'reported_by_me': 0,
                'recent_activity': 0,
                'high_priority': 0,
                'all_open_tickets': 0,
                'created_this_month': 0,
                'resolved_this_month': 0
            },
            'distributions': {
                'status': {},
                'priority': {},
                'assignees': {},
                'types': {}
            },
            'trends': {
                'created_this_month': 0,
                'created_last_month': 0,
                'growth_rate': 0
            },
            'recent_tickets': []
        }

class QueryProcessor:
    def __init__(self, openai_api_key: str):
        self.client = openai
        self.current_user = None
        self.all_users = []
        
    def set_jira_context(self, current_user: Dict, all_users: List[Dict]):
        """Set Jira context for better query processing"""
        self.current_user = current_user
        self.all_users = all_users
        
    def process_query(self, query: str, previous_context: Optional[str] = None) -> Dict[str, Any]:
        """Process natural language query and convert to JQL"""
        
        # Create user mapping for name resolution
        user_mapping = {}
        for user in self.all_users:
            display_name = user.get('displayName', '')
            username = user.get('name', '')
            if display_name:
                user_mapping[display_name.lower()] = username
            if username:
                user_mapping[username.lower()] = username

        system_prompt = f"""
You are a Jira JQL query generator. Convert natural language queries to JQL (Jira Query Language).

Current user: {self.current_user.get('displayName', 'Unknown')} ({self.current_user.get('name', 'Unknown')})
Current system datetime: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Available users (format: Display Name -> Username):
{chr(10).join([f"{user.get('displayName', 'Unknown')} -> {user.get('name', 'Unknown')}" for user in self.all_users[:20]])}

Context from previous query: {previous_context or 'None'}

CRITICAL JQL RULES:
1. NEVER use reserved words without quotes: "LIMIT", "ORDER", "BY", "AND", "OR", "NOT", "IN", "IS", "WAS", etc.
2. If a field name or value contains reserved words, wrap it in quotes: "My LIMIT Project"
3. Use proper JQL syntax - avoid SQL-like constructs
4. For limiting results, use Jira's built-in pagination, NOT "LIMIT" clause
5. Order by syntax: "ORDER BY created DESC" (not "ORDER BY created LIMIT 10")

Query Conversion Rules:
1. "me", "my", "I" refers to current user: {self.current_user.get('name', 'Unknown')}
2. When filtering by month/date, use created or updated dates appropriately
3. For user references like "Mr.A", "John", etc., match against display names and convert to usernames
4. If this is a follow-up query (like "show me the ones assigned by X"), modify the previous context
5. Common JQL fields: assignee, reporter, status, created, updated, priority, summary, description
6. Date formats: "2023-08-01" for specific dates, "-30d" for relative dates
7. For "assigned to me": assignee = currentUser()
8. For "assigned by someone": reporter = "username"
9. For text searches in summary/description: summary ~ "search term" or description ~ "search term"
10. Status values must match exact Jira status names (case-sensitive)

EXAMPLES OF CORRECT JQL:
- assignee = currentUser() AND status = "In Progress"
- project = "My PROJECT" AND created >= -7d ORDER BY created DESC
- reporter = "john.doe" AND priority = High
- summary ~ "bug" AND assignee in (currentUser(), "jane.smith")

EXAMPLES OF INCORRECT JQL TO AVOID:
- assignee = currentUser() LIMIT 10  (WRONG - LIMIT is reserved)
- SELECT * FROM issues WHERE...     (WRONG - this is SQL, not JQL)
- ORDER BY created LIMIT 5          (WRONG - use ORDER BY created DESC)

Return JSON with:
{{
    "jql": "the JQL query",
    "maxResult": "The amount of data to fetch IF explicitly said",
    "description": "human readable description of what will be shown",
    "context": "context for follow-up queries"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error processing query with OpenAI: {e}")
            # Fallback to basic query processing
            return self._fallback_query_processing(query)
    
    def _fallback_query_processing(self, query: str) -> Dict[str, Any]:
        """Fallback query processing if OpenAI fails"""
        query_lower = query.lower()
        
        # Basic patterns
        if "assigned to me" in query_lower or "my tickets" in query_lower:
            jql = "assignee = currentUser()"
            description = "Tickets assigned to you"
        elif "august" in query_lower:
            jql = "assignee = currentUser() AND created >= '2023-08-01' AND created <= '2023-08-31'"
            description = "Your tickets from August"
        else:
            jql = "assignee = currentUser()"
            description = "Your tickets"
        
        return {
            "jql": jql,
            "description": description,
            "context": f"Showing: {description}"
        }

# Initialize managers
jira_manager = None
query_processor = None

def initialize_managers():
    """Initialize Jira and Query managers"""
    global jira_manager, query_processor
    
    if not all([JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD, OPENAI_API_KEY]):
        raise ValueError("Missing required environment variables. Please check your .env file.")
    
    jira_manager = JiraManager(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)
    query_processor = QueryProcessor(OPENAI_API_KEY)
    
    # Set up context
    current_user = jira_manager.get_current_user()
    all_users = jira_manager.get_all_users()
    query_processor.set_jira_context(current_user, all_users)

# Routes
@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        if jira_manager is None:
            return jsonify({'error': 'Jira manager not initialized'}), 500
            
        print("Getting dashboard stats...")
        stats = jira_manager.get_dashboard_stats()
        print("Dashboard stats retrieved successfully")
        return jsonify(stats)
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'summary': {
                'my_open_tickets': 0,
                'my_total_tickets': 0,
                'reported_by_me': 0,
                'recent_activity': 0,
                'high_priority': 0,
                'all_open_tickets': 0,
                'created_this_month': 0,
                'resolved_this_month': 0
            },
            'distributions': {'status': {}, 'priority': {}, 'assignees': {}, 'types': {}},
            'trends': {'created_this_month': 0, 'created_last_month': 0, 'growth_rate': 0},
            'recent_tickets': []
        }), 200  # Return 200 with empty data instead of 500

@app.route('/api/query', methods=['POST'])
def process_query():
    """Process natural language query and return ticket results"""
    try:
        if jira_manager is None or query_processor is None:
            return jsonify({'error': 'Backend not initialized properly'}), 500

        data = request.json
        query = data.get('query', '')
        context = data.get('context')
        
        if not query:
            return jsonify({'error': 'No query provided'})
        
        # Process the query
        query_result = query_processor.process_query(query, context)
        jql = query_result['jql']
        
        # Handle maxResult properly - use default if not specified
        max_result = query_result.get('maxResult', 50)
        if isinstance(max_result, str) and max_result.isdigit():
            max_result = int(max_result)
        elif not isinstance(max_result, int):
            max_result = 50
        
        # Search for issues
        issues = jira_manager.search_issues(jql, max_results=max_result)
        
        # Format results
        tickets = jira_manager._format_tickets(issues)
        
        return jsonify({
            'tickets': tickets,
            'description': query_result['description'],
            'context': query_result['context'],
            'jql': jql,
            'total_results': len(tickets)
        })
        
    except Exception as e:
        print(f"Error in process_query: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test Jira connection
        current_user = jira_manager.get_current_user()
        if current_user:
            return jsonify({
                'status': 'healthy',
                'jira_connection': 'ok',
                'current_user': current_user.get('displayName', 'Unknown')
            })
        else:
            return jsonify({
                'status': 'unhealthy',
                'jira_connection': 'failed'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/api/user/profile')
def get_user_profile():
    """Get user profile information"""
    try:
        current_user = jira_manager.get_current_user()
        return jsonify({
            'name': current_user.get('displayName', 'Kaza Afghanistan'),
            'role': 'Software Engineer',
            'avatar': current_user.get('avatarUrls', {}).get('48x48', ''),
            'email': current_user.get('emailAddress', ''),
            'username': current_user.get('name', '')
        })
    except Exception as e:
        return jsonify({
            'name': 'Kaza Afghanistan',
            'role': 'Software Engineer',
            'avatar': '',
            'email': '',
            'username': ''
        })
    
@app.route('/api/chat/new', methods=['POST'])
def create_new_chat():
    """Create a new chat session"""
    try:
        chat_id = str(uuid4())
        title = f"Chat {datetime.now().strftime('%Y-%m-%d')}"
        
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO chats (id, title, created_at, updated_at, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, title, datetime.now(), datetime.now(), 'current_user'))
        conn.commit()
        conn.close()
        
        return jsonify({
            'chat_id': chat_id,
            'title': title,
            'created_at': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/chat/history')
def get_chat_history():
    """Get list of all chats"""
    try:
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('''
            SELECT id, title, created_at, updated_at 
            FROM chats 
            ORDER BY updated_at DESC
        ''')
        chats = [
            {
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'updated_at': row[3]
            }
            for row in c.fetchall()
        ]
        conn.close()
        
        return jsonify(chats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/chat/<chat_id>')
def get_chat_messages(chat_id):
    """Get messages for a specific chat"""
    try:
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('''
            SELECT content, sender, timestamp 
            FROM messages 
            WHERE chat_id = ?
            ORDER BY timestamp ASC
        ''', (chat_id,))
        messages = [
            {
                'content': row[0],
                'sender': row[1],
                'timestamp': row[2]
            }
            for row in c.fetchall()
        ]
        conn.close()
        
        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/<chat_id>/message', methods=['POST'])
def send_message(chat_id):
    """Send a message to a chat"""
    try:
        data = request.json
        message_content = data.get('message', '').strip()
        
        if not message_content:
            return jsonify({'error': 'Message content required'}), 400
        
        # Save user message
        message_id = str(uuid4())
        timestamp = datetime.now()
        
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO messages (id, chat_id, content, sender, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (message_id, chat_id, message_content, 'user', timestamp))
        
        # Check if this is a Jira query or general chat
        query_indicators = ['ticket', 'issue', 'assigned', 'jira', 'bug', 'show me', 'find', 'search']
        is_jira_query = any(indicator in message_content.lower() for indicator in query_indicators)
        
        if is_jira_query:
            # Process as Jira query
            query_result = query_processor.process_query(message_content)
            issues = jira_manager.search_issues(query_result['jql'], max_results=10)
            
            if issues:
                tickets_info = []
                for issue in issues[:5]:  # Show top 5
                    fields = issue['fields']
                    tickets_info.append(
                        f"• {issue['key']}: {fields.get('summary', 'No summary')[:50]}..."
                    )
                
                ai_response = f"I found {len(issues)} {query_result['description']}:\n\n" + \
                            "\n".join(tickets_info)
                if len(issues) > 5:
                    ai_response += f"\n\n... and {len(issues) - 5} more tickets."
            else:
                ai_response = f"No tickets found for your query: {query_result['description']}"
        else:
            # General chat response
            ai_response = "I'm here to help with your Jira tickets! Try asking me things like 'show my open tickets' or 'find bugs assigned to me'."
        
        # Save AI response
        ai_message_id = str(uuid4())
        ai_timestamp = datetime.now()
        c.execute('''
            INSERT INTO messages (id, chat_id, content, sender, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (ai_message_id, chat_id, ai_response, 'ai', ai_timestamp))
        
        # Update chat timestamp
        c.execute('''
            UPDATE chats SET updated_at = ? WHERE id = ?
        ''', (timestamp, chat_id))
        
        conn.commit()
        conn.close()
        
        # Emit real-time message if socket is connected
        socketio.emit('new_message', {
            'chat_id': chat_id,
            'user_message': {
                'content': message_content,
                'sender': 'user',
                'timestamp': timestamp.isoformat()
            },
            'ai_response': {
                'content': ai_response,
                'sender': 'ai',
                'timestamp': ai_timestamp.isoformat()
            }
        })
        
        return jsonify({
            'user_message': {
                'content': message_content,
                'sender': 'user',
                'timestamp': timestamp.isoformat()
            },
            'ai_response': {
                'content': ai_response,
                'sender': 'ai',
                'timestamp': ai_timestamp.isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/chat/<chat_id>/rename', methods=['PUT'])
def rename_chat(chat_id):
    """Rename a chat"""
    try:
        data = request.json
        new_title = data.get('title', '').strip()
        
        if not new_title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        c.execute('''
            UPDATE chats SET title = ?, updated_at = ?
            WHERE id = ?
        ''', (new_title, datetime.now(), chat_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'title': new_title})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Delete a chat and all its messages"""
    try:
        conn = sqlite3.connect('maya_tone.db')
        c = conn.cursor()
        
        # Delete messages first (foreign key constraint)
        c.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        
        # Delete chat
        c.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/canvas/data')
def get_canvas_data():
    """Get chart data for canvas with filtering"""
    try:
        filter_type = request.args.get('filter', 'monthly').lower()
        
        # Get actual data from Jira based on filter
        if filter_type == 'yearly':
            # Get data for past 3 years
            years_data = []
            current_year = datetime.now().year
            for year in range(current_year - 2, current_year + 1):
                year_issues = jira_manager.search_issues(
                    f'created >= "{year}-01-01" AND created <= "{year}-12-31"', 
                    max_results=1000
                )
                
                status_counts = {'todo': 0, 'progress': 0, 'review': 0, 'done': 0, 'bug': 0}
                for issue in year_issues:
                    status = issue['fields'].get('status', {}).get('name', '').lower()
                    issue_type = issue['fields'].get('issuetype', {}).get('name', '').lower()
                    
                    if 'bug' in issue_type:
                        status_counts['bug'] += 1
                    elif any(s in status for s in ['done', 'closed', 'resolved']):
                        status_counts['done'] += 1
                    elif any(s in status for s in ['review', 'testing']):
                        status_counts['review'] += 1
                    elif any(s in status for s in ['progress', 'development']):
                        status_counts['progress'] += 1
                    else:
                        status_counts['todo'] += 1
                
                years_data.append({
                    'name': str(year),
                    **status_counts
                })
            
            return jsonify(years_data)
        
        # For other filters, you can implement similar logic
        # For now, returning mock data as fallback
        elif filter_type == 'weekly':
            data = [
                {'name': 'Week 1', 'todo': 15, 'progress': 10, 'review': 8, 'done': 25, 'bug': 3},
                {'name': 'Week 2', 'todo': 18, 'progress': 12, 'review': 6, 'done': 30, 'bug': 2},
                {'name': 'Week 3', 'todo': 20, 'progress': 15, 'review': 10, 'done': 28, 'bug': 4},
                {'name': 'Week 4', 'todo': 22, 'progress': 18, 'review': 12, 'done': 35, 'bug': 1}
            ]
        elif filter_type == 'daily':
            data = [
                {'name': 'Mon', 'todo': 3, 'progress': 2, 'review': 1, 'done': 5, 'bug': 0},
                {'name': 'Tue', 'todo': 4, 'progress': 3, 'review': 2, 'done': 6, 'bug': 1},
                {'name': 'Wed', 'todo': 2, 'progress': 4, 'review': 3, 'done': 7, 'bug': 0},
                {'name': 'Thu', 'todo': 5, 'progress': 2, 'review': 1, 'done': 8, 'bug': 1},
                {'name': 'Fri', 'todo': 3, 'progress': 5, 'review': 4, 'done': 9, 'bug': 0}
            ]
        else:  # monthly - use actual Jira data
            monthly_data = []
            current_date = datetime.now()
            for i in range(12):
                month_date = current_date - timedelta(days=30 * i)
                month_name = month_date.strftime('%b')
                
                # Get issues for this month
                month_issues = jira_manager.search_issues(
                    f'created >= "{month_date.strftime("%Y-%m")}-01" AND created < "{(month_date + timedelta(days=32)).strftime("%Y-%m")}-01"',
                    max_results=500
                )
                
                status_counts = {'todo': 0, 'progress': 0, 'review': 0, 'done': 0, 'bug': 0}
                for issue in month_issues:
                    status = issue['fields'].get('status', {}).get('name', '').lower()
                    issue_type = issue['fields'].get('issuetype', {}).get('name', '').lower()
                    
                    if 'bug' in issue_type:
                        status_counts['bug'] += 1
                    elif any(s in status for s in ['done', 'closed', 'resolved']):
                        status_counts['done'] += 1
                    elif any(s in status for s in ['review', 'testing']):
                        status_counts['review'] += 1
                    elif any(s in status for s in ['progress', 'development']):
                        status_counts['progress'] += 1
                    else:
                        status_counts['todo'] += 1
                
                monthly_data.insert(0, {
                    'name': month_name,
                    **status_counts
                })
            
            data = monthly_data[:4]  # Return last 4 months
        
        return jsonify(data)
    except Exception as e:
        print(f"Error getting canvas data: {e}")
        # Return fallback data
        return jsonify([
            {'name': 'Jan', 'todo': 45, 'progress': 30, 'review': 20, 'done': 65, 'bug': 8},
            {'name': 'Feb', 'todo': 50, 'progress': 35, 'review': 25, 'done': 70, 'bug': 6},
            {'name': 'Mar', 'todo': 40, 'progress': 40, 'review': 30, 'done': 75, 'bug': 5},
            {'name': 'Apr', 'todo': 55, 'progress': 25, 'review': 15, 'done': 80, 'bug': 7}
        ])
    
@app.route('/api/ticket/<ticket_key>')
def get_ticket_details(ticket_key):
    """Get detailed information for a specific ticket"""
    try:
        issues = jira_manager.search_issues(f'key = "{ticket_key}"', max_results=1)
        
        if not issues:
            return jsonify({'error': 'Ticket not found'}), 404
        
        issue = issues[0]
        fields = issue['fields']
        
        ticket_details = {
            'key': issue['key'],
            'summary': fields.get('summary', 'No summary'),
            'description': fields.get('description', 'No description'),
            'status': fields.get('status', {}).get('name', 'Unknown'),
            'assignee': fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned',
            'reporter': fields.get('reporter', {}).get('displayName', 'Unknown') if fields.get('reporter') else 'Unknown',
            'priority': fields.get('priority', {}).get('name', 'Medium') if fields.get('priority') else 'Medium',
            'issue_type': fields.get('issuetype', {}).get('name', 'Unknown'),
            'created': fields.get('created', '')[:10] if fields.get('created') else 'Unknown',
            'updated': fields.get('updated', '')[:10] if fields.get('updated') else 'Unknown',
            'url': f"{jira_manager.base_url}/browse/{issue['key']}"
        }
        
        return jsonify(ticket_details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/stats/summary')
def get_stats_summary():
    """Get quick stats summary for widgets"""
    try:
        dashboard_stats = jira_manager.get_dashboard_stats()
        summary = dashboard_stats.get('summary', {})
        
        return jsonify({
            'open_tickets': summary.get('my_open_tickets', 0),
            'total_tickets': summary.get('my_total_tickets', 0),
            'high_priority': summary.get('high_priority', 0),
            'created_this_month': summary.get('created_this_month', 0),
            'resolved_this_month': summary.get('resolved_this_month', 0),
            'recent_activity': summary.get('recent_activity', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/tasks')
def get_tasks():
    """Get formatted task list for the dashboard table"""
    try:
        # Get recent tickets
        issues = jira_manager.search_issues('updated >= -30d', 50)
        tasks = []
        
        for issue in issues:
            fields = issue['fields']
            tasks.append({
                'id': issue['key'],
                'summary': fields.get('summary', 'No summary'),
                'status': fields.get('status', {}).get('name', 'Unknown'),
                'assignee': fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned',
                'due_date': fields.get('duedate', 'No due date'),
                'priority': fields.get('priority', {}).get('name', 'Medium') if fields.get('priority') else 'Medium',
                'url': f"{jira_manager.base_url}/browse/{issue['key']}"
            })
        
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/search/suggestions')
def get_search_suggestions():
    """Get search suggestions for autocomplete"""
    try:
        query = request.args.get('q', '').lower()
        
        suggestions = [
            "my open tickets",
            "tickets assigned to me",
            "high priority tickets",
            "bugs assigned to me",
            "tickets created this month",
            "resolved tickets",
            "tickets in progress",
            "overdue tickets"
        ]
        
        # Filter suggestions based on query
        if query:
            suggestions = [s for s in suggestions if query in s.lower()]
        
        return jsonify(suggestions[:5])  # Return top 5
    except Exception as e:
        return jsonify([])
    
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/test')
def test_connection():
    """Test endpoint to verify backend connection"""
    return jsonify({
        'status': 'success',
        'message': 'Backend is running',
        'timestamp': datetime.now().isoformat()
    })
    
# WebSocket Events for Real-time Chat
@socketio.on('join_chat')
def on_join_chat(data):
    """Join a chat room"""
    chat_id = data['chat_id']
    join_room(chat_id)
    emit('joined_chat', {'chat_id': chat_id})

@socketio.on('leave_chat')
def on_leave_chat(data):
    """Leave a chat room"""
    chat_id = data['chat_id']
    leave_room(chat_id)

@socketio.on('send_message')
def on_send_message(data):
    """Handle real-time message sending"""
    chat_id = data['chat_id']
    message = data['message']
    
    # Emit to all users in the chat room
    emit('new_message', {
        'content': message,
        'sender': 'user',
        'timestamp': datetime.now().isoformat()
    }, room=chat_id)

# Update your main initialization
if __name__ == '__main__':
    try:
        # Initialize database
        init_db()
        
        # Initialize managers
        initialize_managers()
        
        print("✅ Maya-Tone backend initialized successfully!")
        print("📊 Dashboard API: http://localhost:5000/api/dashboard-stats")
        print("💬 Chat API: http://localhost:5000/api/chat/history")
        print("🎨 Canvas API: http://localhost:5000/api/canvas/data")
        print("👤 Profile API: http://localhost:5000/api/user/profile")
        print("🔍 Test API: http://localhost:5000/api/test")
        
        # Use SocketIO to run the app for real-time features
        socketio.run(app, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"❌ Failed to initialize application: {e}")
        import traceback
        traceback.print_exc()