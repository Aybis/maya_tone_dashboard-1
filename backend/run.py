"""Application entrypoint for running the SocketIO server.

Usage (dev):
  python -m backend.run
  # or legacy
  python backend/run.py

This wraps create_app() and exposes SocketIO.run for unified server startup.
"""
import os
from . import create_app
from .extensions import socketio

app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG','False').lower() in ('1','true','yes')
    socketio.run(app, host='0.0.0.0', port=4000, debug=debug_mode)
