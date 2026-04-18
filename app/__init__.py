"""
VPS Panel — Flask Application Factory
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from .extensions import db, jwt, migrate
from .config import config_map


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    )
    app.config.from_object(config_map.get(config_name, config_map['development']))

    # ── Initialize Extensions ──
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # ── Register Blueprints ──
    _register_blueprints(app)

    # ── Inject Template Globals ──
    _inject_template_globals(app)

    # ── Setup Logging ──
    _setup_logging(app)

    # ── Create DB Tables ──
    with app.app_context():
        from . import models  # noqa: F401 — import models so SQLAlchemy sees them
        db.create_all()
        _ensure_admin(app)

    # ── Register Error Handlers ──
    _register_error_handlers(app)

    return app


def _inject_template_globals(app):
    """Inject global variables available in every Jinja2 template."""
    @app.context_processor
    def globals():
        return {
            'base_url': app.config.get('BASE_URL', 'http://localhost'),
            'phppgadmin_url': app.config.get('PHPPGADMIN_URL', app.config.get('BASE_URL', 'http://localhost') + '/phppgadmin'),
            'panel_name': app.config.get('PANEL_NAME', 'VPS Panel'),
            'panel_version': app.config.get('PANEL_VERSION', '3.0.0'),
        }


def _register_blueprints(app):
    """Register all module blueprints."""
    from .modules.auth.routes import auth_bp
    from .modules.users.routes import users_bp
    from .modules.ftp.routes import ftp_bp
    from .modules.database.routes import database_bp
    from .modules.db_users.routes import db_users_bp
    from .modules.domains.routes import domains_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(database_bp)
    app.register_blueprint(db_users_bp)
    app.register_blueprint(ftp_bp)
    app.register_blueprint(domains_bp)


def _setup_logging(app):
    """Configure structured logging and prevent reentrancy errors."""
    log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_file = app.config.get('LOG_FILE')
    is_production = os.environ.get('FLASK_ENV') == 'production'

    # Base formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    # 1. Console / Stream Logging
    # In development, we want explicit console logging.
    # In production, Gunicorn captures stdout/stderr, so adding a redundant 
    # StreamHandler can cause "reentrant call" errors in Python 3.12.
    if not is_production or app.config.get('DEBUG'):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)
    else:
        # In production/Gunicorn, ensure the root logger level is synced 
        # so logs propagate to Gunicorn's captured stderr.
        logging.getLogger().setLevel(log_level)

    # 2. Dedicated File handler (if path is writable)
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(log_file, maxBytes=10_485_760, backupCount=5)
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
        except (PermissionError, OSError):
            app.logger.warning(f"Cannot write to log file {log_file}")

    app.logger.setLevel(log_level)


def _ensure_admin(app):
    """Create default admin user if none exists."""
    from .models.user import User
    from werkzeug.security import generate_password_hash

    if User.query.filter_by(role='admin').first() is None:
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            role='admin',
            home_directory=os.path.join(app.config.get('WEB_ROOT', '/var/www'), 'admin'),
        )
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Default admin account created (username: admin, password: admin).")


def _register_error_handlers(app):
    """Global error handlers."""
    from flask import jsonify, render_template, request

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found"}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Forbidden"}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal server error"}), 500
        return render_template('errors/500.html'), 500
