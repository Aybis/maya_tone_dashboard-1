"""Thin legacy entrypoint. Prefer: `python -m backend.run`.
Includes fallback so `python backend/app.py` also works (adjusts sys.path for direct script execution).
See run.py for the canonical entrypoint used in deployment / dev tasks.
"""
import os
try:  # Normal package-relative imports when run as module
    from . import create_app
    from .extensions import socketio
except ImportError:  # Fallback when executed directly (no parent package)
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    # Now import via absolute package name
    from backend import create_app  # type: ignore
    from backend.extensions import socketio  # type: ignore

app = create_app()

@app.route('/')
def root():
    return {"message": "Backend running. Modular API under /api/*"}

@app.errorhandler(404)
def not_found(e):
    return {"error": "not found"}, 404

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG','False').lower() in ('1','true','yes')
    socketio.run(app, host='0.0.0.0', port=4000, debug=debug_mode)
## All legacy routes removed; blueprints provide functionality.