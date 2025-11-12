from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv

from config.settings import get_settings
from models import get_user_by_id, init_db

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env"
    if env_path.exists():
        # Use override=True to ensure .env values take precedence
        # This is critical for production where systemd might set some env vars
        load_dotenv(env_path, override=True)
    else:
        # Try loading from current directory as fallback
        load_dotenv(override=True)

    _ENV_LOADED = True


login_manager = LoginManager()
login_manager.login_view = "core.login"
# Use "basic" instead of "strong" to avoid session invalidation behind load balancers
login_manager.session_protection = "basic"


@login_manager.user_loader
def load_user(user_id: str) -> Optional[object]:
    try:
        return get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None


def create_app() -> Flask:
    _ensure_env_loaded()
    
    # CRITICAL: Reset database connection to ensure we pick up correct DATABASE_URL
    # This is especially important for gunicorn workers that might have cached connections
    from models import reset_engine
    reset_engine()
    
    settings = get_settings()

    # Set template and static folders to project root directories
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    
    # Configure session cookies for HTTPS
    app.config["SESSION_COOKIE_SECURE"] = True  # Only send cookies over HTTPS
    app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection
    app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 31  # 31 days

    login_manager.init_app(app)
    init_db()

    # CRITICAL: Reset database connection before every request to ensure we use PostgreSQL
    # This prevents gunicorn workers from using cached SQLite connections
    # This applies to ALL users and ALL requests universally
    @app.before_request
    def reset_db_connection():
        """Reset database connection before each request to ensure correct database is used."""
        # Ensure environment is loaded first
        _ensure_env_loaded()
        # Then reset the connection
        from models import reset_engine
        reset_engine()
        # Verify we're using PostgreSQL
        from models import get_connection, _backend
        conn = get_connection()
        # Check connection type directly if _backend is None (it should be set, but check as fallback)
        is_postgres = "psycopg" in str(type(conn))
        if _backend != "postgres" and not is_postgres:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"CRITICAL: Database backend is {_backend}, expected postgres! Connection type: {type(conn)}")

    from .routes import bp as core_bp

    app.register_blueprint(core_bp)

    return app

