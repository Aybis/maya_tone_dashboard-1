from flask_socketio import SocketIO
from flask_cors import CORS

# Global extension instances (imported in app factory and entrypoints)
# SocketIO: real-time events / future interactive features.
# CORS: allow frontend dev server calls without manual headers.
socketio = SocketIO(cors_allowed_origins="*")

def init_extensions(app):
    """Bind global extension objects to the Flask app instance."""
    CORS(app)
    socketio.init_app(app)
