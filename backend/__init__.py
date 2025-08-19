"""Backend package initialization.

Key concepts:
- create_app(): Flask application factory used by both run.py and app.py legacy entrypoint.
- Blueprints: chat (conversational AI + tool calling), dashboard (summary metrics), chart (direct aggregations without LLM).
- Extensions: SocketIO + CORS initialized via extensions.init_extensions.
- Database: Lightweight SQLite (maya_tone.db) initialised on startup.
"""

from flask import Flask, jsonify, request, session
from .config import SECRET_KEY
from .extensions import init_extensions, socketio
from .db import init_db
from .api.chat import chat_bp
from .api.dashboard import dashboard_bp
from .api.chart import chart_bp
from .api.auth import auth_bp
from .api.projects import projects_bp
import requests


def create_app():
    """Application factory.

    Responsibilities:
    1. Instantiate Flask app & configure secret key.
    2. Initialise extensions (CORS + SocketIO binding) so SocketIO shares the Flask app context.
    3. Initialise / migrate the SQLite DB (tables created if missing).
    4. Register API blueprints (each one owns its URL space under /api/*).
    5. Provide a lightweight /api/health route for readiness probes.

    Returns: Configured Flask application instance.
    """
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    init_extensions(app)
    init_db()
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chart_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)

    @app.before_request
    def require_auth():
        exempt_paths = ["/api/login", "/api/logout", "/api/health", "/api/check-auth"]
        if request.path in exempt_paths or request.path.startswith("/static"):
            return

        if request.path.startswith("/api/") and not session.get("logged_in"):
            return jsonify({"error": "Authentication required"}), 401

    @app.route("/api/health")
    def health():
        from datetime import datetime

        return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

    return app


# Socket.IO event handlers (placed after app creation so 'socketio' is bound)
@socketio.on("join_chat")
def handle_join_chat(data):
    """Client requests to join a chat room to receive real-time messages.

    Frontend emits: socket.emit('join_chat', { chat_id })
    We join a room named after chat_id so assistant replies can be room-targeted.
    """
    try:
        from flask import request as flask_request

        chat_id = (data or {}).get("chat_id")
        if not chat_id:
            return
        from flask_socketio import join_room

        join_room(chat_id)
    except Exception:
        # Best-effort; avoid crashing on bad payload
        pass
