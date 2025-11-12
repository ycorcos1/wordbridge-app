from __future__ import annotations

import os
from typing import Optional

from flask import Flask
from flask_login import LoginManager

from config.settings import get_settings
from models import get_user_by_id, init_db

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

    from .routes import bp as core_bp

    app.register_blueprint(core_bp)

    return app

