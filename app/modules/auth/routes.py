"""
VPS Panel — Auth Routes

Handles both web (session) and API (JWT) authentication.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.modules.auth.schemas import validate_login
from app.modules.auth.services import authenticate, create_tokens
from app.models.activity_log import ActivityLog
from app.extensions import db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


# ════════════════════════════════════════
# WEB ROUTES (Session-based)
# ════════════════════════════════════════

@auth_bp.route('/')
def index():
    """Root route — redirect based on session."""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('users.admin_dashboard'))
        return redirect(url_for('users.client_dashboard'))
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/login', methods=['GET'])
def login_page():
    """Render the login page."""
    if 'user_id' in session:
        return redirect(url_for('auth.index'))
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
def login_submit():
    """Handle login form submission."""
    valid, error = validate_login(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('auth.login_page'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    user = authenticate(username, password)
    if not user:
        flash('Invalid username or password.', 'danger')
        return redirect(url_for('auth.login_page'))

    # Set session
    session.permanent = True
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role

    # Log activity
    try:
        log = ActivityLog(
            user_id=user.id,
            action='login',
            target_type='auth',
            target_id=str(user.id),
            ip_address=request.remote_addr,
            details=f"User '{username}' logged in.",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass

    logger.info(f"Web login: {username} ({user.role})")

    if user.role == 'admin':
        return redirect(url_for('users.admin_dashboard'))
    return redirect(url_for('users.client_dashboard'))


@auth_bp.route('/logout')
def logout():
    """Clear session and redirect to login."""
    username = session.get('username', 'unknown')
    user_id = session.get('user_id')

    # Log activity
    try:
        if user_id:
            log = ActivityLog(
                user_id=user_id,
                action='logout',
                target_type='auth',
                target_id=str(user_id),
                ip_address=request.remote_addr,
                details=f"User '{username}' logged out.",
            )
            db.session.add(log)
            db.session.commit()
    except Exception:
        pass

    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login_page'))


# ════════════════════════════════════════
# API ROUTES (JWT-based)
# ════════════════════════════════════════

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    """API login — returns JWT tokens."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_login(data)
    if not valid:
        return jsonify({"error": error}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = authenticate(username, password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    tokens = create_tokens(user)

    # Log activity
    try:
        log = ActivityLog(
            user_id=user.id,
            action='api_login',
            target_type='auth',
            target_id=str(user.id),
            ip_address=request.remote_addr,
            details=f"API login for '{username}'.",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass

    return jsonify(tokens), 200
