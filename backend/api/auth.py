# backend/api/auth.py
from flask import Blueprint, request, jsonify, session
from ..config import JIRA_BASE_URL

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    """Simple login gate - stores credentials in session."""
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username dan password harus diisi'}), 400
    
    # Just store in session - no validation
    session['jira_username'] = username
    session['jira_password'] = password
    session['logged_in'] = True
    
    return jsonify({
        'success': True, 
        'message': 'Login berhasil',
        'username': username
    })

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