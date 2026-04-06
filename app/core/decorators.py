"""
VPS Panel — Authentication & Authorization Decorators
"""
import functools
from flask import session, redirect, url_for, flash, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt


def login_required_web(f):
    """Decorator: require session-based login for web routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required_web(f):
    """Decorator: require admin session for web routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def client_required_web(f):
    """Decorator: require client session for web routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'client':
            flash('Client access required.', 'danger')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def login_required_api(f):
    """Decorator: require JWT for API routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required_api(f):
    """Decorator: require JWT with admin role for API routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') != 'admin':
                return jsonify({"error": "Admin access required"}), 403
        except Exception:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def log_activity(action: str):
    """Decorator: automatically log user actions to the activity log."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                from app.models.activity_log import ActivityLog
                from app.extensions import db

                user_id = session.get('user_id')
                if not user_id:
                    # Try JWT
                    try:
                        verify_jwt_in_request()
                        claims = get_jwt()
                        user_id = claims.get('sub')
                    except Exception:
                        pass

                log_entry = ActivityLog(
                    user_id=user_id,
                    action=action,
                    target_type=request.blueprint or 'unknown',
                    target_id=request.path,
                    ip_address=request.remote_addr or '0.0.0.0',
                    details=f"{request.method} {request.path}",
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception:
                pass  # Never let logging break the request

            return result
        return decorated
    return decorator
