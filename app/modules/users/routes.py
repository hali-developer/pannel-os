"""
VPS Panel — User Routes

Admin user management and dashboard views for both admin and client.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import admin_required_web, client_required_web, login_required_api, admin_required_api, log_activity
from app.modules.users.schemas import validate_create_user
from app.modules.users import services as user_svc
from app.models.activity_log import ActivityLog
from app.extensions import db

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__)


# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@users_bp.route('/admin/dashboard')
@admin_required_web
def admin_dashboard():
    """Admin overview dashboard with stats."""
    stats = user_svc.get_dashboard_stats()
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)


@users_bp.route('/admin/users', methods=['GET'])
@admin_required_web
def admin_users_page():
    """Admin user management page."""
    users = user_svc.list_users(include_inactive=True)
    return render_template('admin/users.html', users=users)


@users_bp.route('/admin/users/create', methods=['POST'])
@admin_required_web
@log_activity('create_user')
def admin_create_user():
    """Create a new user from admin panel."""
    valid, error = validate_create_user(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('users.admin_users_page'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'client')
    email = request.form.get('email', '').strip() or None

    ok, msg, user = user_svc.create_user(username, password, role, email)
    if ok:
        flash(f"User '{username}' created successfully.", 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('users.admin_users_page'))


@users_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required_web
@log_activity('toggle_user')
def admin_toggle_user(user_id):
    """Activate/deactivate a user."""
    user = user_svc.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('users.admin_users_page'))

    if user.is_active:
        ok, msg = user_svc.deactivate_user(user_id)
    else:
        ok, msg = user_svc.update_user(user_id, is_active=True)

    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.admin_users_page'))


@users_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required_web
@log_activity('delete_user')
def admin_delete_user(user_id):
    """Permanently delete a user."""
    ok, msg = user_svc.delete_user(user_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.admin_users_page'))


@users_bp.route('/admin/users/<int:user_id>/password', methods=['POST'])
@admin_required_web
@log_activity('change_user_password')
def admin_change_password(user_id):
    """Change a user's password."""
    new_password = request.form.get('password', '')
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('users.admin_users_page'))

    ok, msg = user_svc.update_user(user_id, password=new_password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.admin_users_page'))


@users_bp.route('/admin/activity')
@admin_required_web
def admin_activity_log():
    """View activity log."""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    logs = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/activity_log.html', logs=logs)


# ════════════════════════════════════════
# CLIENT WEB ROUTES
# ════════════════════════════════════════

@users_bp.route('/dashboard')
@client_required_web
def client_dashboard():
    """Client self-service dashboard."""
    user = user_svc.get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('auth.login_page'))

    from app.models.domain import Domain
    from app.models.ftp_account import FTPAccount
    from app.models.database import ClientDatabase

    domains = Domain.query.filter_by(user_id=user.id, is_active=True).all()
    ftp_accounts = FTPAccount.query.filter_by(user_id=user.id, is_active=True).all()
    databases = ClientDatabase.query.filter_by(user_id=user.id).all()

    return render_template('client/dashboard.html',
                           user=user,
                           domains=domains,
                           ftp_accounts=ftp_accounts,
                           databases=databases)


# ════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════

@users_bp.route('/api/users/create', methods=['POST'])
@admin_required_api
def api_create_user():
    """API: Create a new user."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_create_user(data)
    if not valid:
        return jsonify({"error": error}), 400

    ok, msg, user = user_svc.create_user(
        data['username'].strip(),
        data['password'],
        data.get('role', 'client'),
        data.get('email'),
    )
    if ok:
        return jsonify({"message": msg, "user": user.to_dict()}), 201
    return jsonify({"error": msg}), 400


@users_bp.route('/api/users', methods=['GET'])
@admin_required_api
def api_list_users():
    """API: List all users."""
    users = user_svc.list_users(include_inactive=True)
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
@login_required_api
def api_get_user(user_id):
    """API: Get user details."""
    user = user_svc.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200


@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required_api
def api_delete_user(user_id):
    """API: Delete a user."""
    ok, msg = user_svc.delete_user(user_id)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400
