# backend/utils/session_jira.py
from flask import session
from ..config import JIRA_BASE_URL

def get_session_credentials():
    """Get Jira credentials from session instead of env."""
    if not session.get('logged_in'):
        return None, None, None
    
    return (
        JIRA_BASE_URL,
        session.get('jira_username'),
        session.get('jira_password')
    )

def require_auth():
    """Check if user is authenticated."""
    return session.get('logged_in', False)