# backend/api/auth.py
from flask import Blueprint, request, jsonify, session
from ..config import JIRA_BASE_URL
from ..jira_utils import JiraManager
import requests
from requests.auth import HTTPBasicAuth

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    """Login with Jira credential validation."""
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400
    
    # Validate credentials against Jira
    try:
        # Test credentials by calling Jira's myself endpoint
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/2/myself",
            auth=HTTPBasicAuth(username, password),
            timeout=10
        )
        
        if response.status_code == 401:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        elif response.status_code != 200:
            return jsonify({'success': False, 'error': 'Unable to connect to Jira. Please try again later.'}), 500
        
        # If we get here, credentials are valid
        user_info = response.json()
        
        # Store in session
        session['jira_username'] = username
        session['jira_password'] = password
        session['logged_in'] = True
        session['jira_base_url'] = JIRA_BASE_URL
        
        return jsonify({
            'success': True, 
            'message': 'Login successful',
            'username': user_info.get('displayName', username)
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Connection timeout. Please try again.'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Unable to connect to Jira. Please check your network connection.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'An unexpected error occurred. Please try again.'}), 500

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """Clear session."""
    session.clear()
    return jsonify({'success': True, 'message': 'Logout berhasil'})

@auth_bp.route('/api/check-auth')
def check_auth():
    """Check if user is logged in."""
    if session.get('logged_in'):
        return jsonify({
            'authenticated': True,
            'username': session.get('jira_username')
        })
    return jsonify({'authenticated': False}), 401