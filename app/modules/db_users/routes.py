"""
VPS Panel — DB User Routes

Web and API routes for MySQL database user management.
Includes CRUD for db_users and permission grant/revoke.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import (
    admin_required_web, client_required_web,
    login_required_api, admin_required_api, log_activity,
)
from app.modules.db_users.schemas import (
    validate_create_db_user, validate_update_db_user_password, validate_grant_permission,
)
from app.modules.db_users import services as dbuser_svc
from app.modules.users.services import list_users, get_user_by_id

logger = logging.getLogger(__name__)

db_users_bp = Blueprint('db_users', __name__)


# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@db_users_bp.route('/admin/db-users', methods=['GET'])
@admin_required_web
def admin_db_users_page():
    """DB user management page."""
    db_users = dbuser_svc.get_all_db_users()
    users = list_users()
    from app.modules.database.services import get_all_databases
    databases = get_all_databases()
    return render_template('admin/db_users.html', db_users=db_users, users=users, databases=databases)


@db_users_bp.route('/admin/db-users/create', methods=['POST'])
@admin_required_web
@log_activity('create_db_user')
def admin_create_db_user():
    """Create a MySQL database user."""
    valid, error = validate_create_db_user(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('db_users.admin_db_users_page'))

    owner_user_id = request.form.get('user_id', type=int)
    db_username = request.form.get('db_username', '').strip()
    password = request.form.get('password', '')

    if not owner_user_id:
        flash('Please select an owner user.', 'danger')
        return redirect(url_for('db_users.admin_db_users_page'))

    ok, msg = dbuser_svc.create_db_user(owner_user_id, db_username, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('db_users.admin_db_users_page'))


@db_users_bp.route('/admin/db-users/<string:db_username>/delete', methods=['POST'])
@admin_required_web
@log_activity('delete_db_user')
def admin_delete_db_user(db_username):
    """Delete a MySQL database user."""
    ok, msg = dbuser_svc.delete_db_user(db_username)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('db_users.admin_db_users_page'))


@db_users_bp.route('/admin/db-users/<string:db_username>/password', methods=['POST'])
@admin_required_web
@log_activity('update_db_user_password')
def admin_update_db_user_password(db_username):
    """Update a MySQL database user's password."""
    valid, error = validate_update_db_user_password(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('db_users.admin_db_users_page'))

    password = request.form.get('password', '')
    ok, msg = dbuser_svc.update_db_user_password(db_username, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('db_users.admin_db_users_page'))


@db_users_bp.route('/admin/db-users/grant', methods=['POST'])
@admin_required_web
@log_activity('grant_db_access')
def admin_grant_db_access():
    """Grant a DB user access to a database."""
    valid, error = validate_grant_permission(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('db_users.admin_db_users_page'))

    db_username = request.form.get('db_username', '').strip()
    db_name = request.form.get('db_name', '').strip()

    ok, msg = dbuser_svc.grant_db_access(db_username, db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('db_users.admin_db_users_page'))


@db_users_bp.route('/admin/db-users/revoke', methods=['POST'])
@admin_required_web
@log_activity('revoke_db_access')
def admin_revoke_db_access():
    """Revoke a DB user's access to a database."""
    db_username = request.form.get('db_username', '').strip()
    db_name = request.form.get('db_name', '').strip()

    if not db_username or not db_name:
        flash('DB username and database name are required.', 'danger')
        return redirect(url_for('db_users.admin_db_users_page'))

    ok, msg = dbuser_svc.revoke_db_access(db_username, db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('db_users.admin_db_users_page'))


# ════════════════════════════════════════
# CLIENT WEB ROUTES
# ════════════════════════════════════════

@db_users_bp.route('/client/db-users/create', methods=['POST'])
@client_required_web
@log_activity('client_create_db_user')
def client_create_db_user():
    """Client creates their own DB user."""
    valid, error = validate_create_db_user(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('users.client_dashboard'))

    user_id = session['user_id']
    user = get_user_by_id(user_id)
    if not user:
        flash('Session error. Please log in again.', 'danger')
        return redirect(url_for('auth.login_page'))

    db_username = request.form.get('db_username', '').strip()
    password = request.form.get('password', '')

    # Enforce username prefix for client isolation
    prefix = f"{user.username}_"
    if not db_username.startswith(prefix):
        db_username = prefix + db_username

    ok, msg = dbuser_svc.create_db_user(user_id, db_username, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@db_users_bp.route('/client/db-users/<string:db_username>/delete', methods=['POST'])
@client_required_web
@log_activity('client_delete_db_user')
def client_delete_db_user(db_username):
    """Client deletes their own DB user."""
    record = dbuser_svc.get_db_user_by_username(db_username)
    if not record or record.owner_user_id != session['user_id']:
        flash('DB user not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    ok, msg = dbuser_svc.delete_db_user(db_username)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@db_users_bp.route('/client/db-users/<string:db_username>/password', methods=['POST'])
@client_required_web
@log_activity('client_update_db_user_password')
def client_update_db_user_password(db_username):
    """Client updates their own DB user's password."""
    record = dbuser_svc.get_db_user_by_username(db_username)
    if not record or record.owner_user_id != session['user_id']:
        flash('DB user not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    valid, error = validate_update_db_user_password(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('users.client_dashboard'))

    password = request.form.get('password', '')
    ok, msg = dbuser_svc.update_db_user_password(db_username, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@db_users_bp.route('/client/db-users/grant', methods=['POST'])
@client_required_web
@log_activity('client_grant_db_access')
def client_grant_db_access():
    """Client grants their DB user access to their database."""
    valid, error = validate_grant_permission(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('users.client_dashboard'))

    db_username = request.form.get('db_username', '').strip()
    db_name = request.form.get('db_name', '').strip()

    # Verify ownership of both resources
    db_user_record = dbuser_svc.get_db_user_by_username(db_username)
    if not db_user_record or db_user_record.owner_user_id != session['user_id']:
        flash('DB user not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    from app.modules.database.services import get_database_by_name
    db_record = get_database_by_name(db_name)
    if not db_record or db_record.user_id != session['user_id']:
        flash('Database not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    ok, msg = dbuser_svc.grant_db_access(db_username, db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@db_users_bp.route('/client/db-users/revoke', methods=['POST'])
@client_required_web
@log_activity('client_revoke_db_access')
def client_revoke_db_access():
    """Client revokes their DB user's access to their database."""
    db_username = request.form.get('db_username', '').strip()
    db_name = request.form.get('db_name', '').strip()

    # Verify ownership
    db_user_record = dbuser_svc.get_db_user_by_username(db_username)
    if not db_user_record or db_user_record.owner_user_id != session['user_id']:
        flash('DB user not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    ok, msg = dbuser_svc.revoke_db_access(db_username, db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


# ════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════

@db_users_bp.route('/api/db-user/create', methods=['POST'])
@admin_required_api
def api_create_db_user():
    """API: Create a MySQL database user."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_create_db_user(data)
    if not valid:
        return jsonify({"error": error}), 400

    owner_user_id = data.get('user_id') or data.get('owner_user_id')
    if not owner_user_id:
        return jsonify({"error": "user_id is required"}), 400

    ok, msg = dbuser_svc.create_db_user(
        owner_user_id, data['db_username'].strip(), data['password']
    )
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400


@db_users_bp.route('/api/db-user/update', methods=['PUT'])
@admin_required_api
def api_update_db_user():
    """API: Update a DB user's password."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_update_db_user_password(data)
    if not valid:
        return jsonify({"error": error}), 400

    ok, msg = dbuser_svc.update_db_user_password(
        data['db_username'].strip(), data['password']
    )
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@db_users_bp.route('/api/db-user/delete', methods=['DELETE'])
@admin_required_api
def api_delete_db_user():
    """API: Delete a DB user."""
    data = request.get_json(silent=True) or {}
    db_username = (data.get('db_username') or '').strip()
    if not db_username:
        return jsonify({"error": "db_username is required"}), 400

    ok, msg = dbuser_svc.delete_db_user(db_username)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@db_users_bp.route('/api/db-user/list', methods=['GET'])
@login_required_api
def api_list_db_users():
    """API: List DB users."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get('role') == 'admin':
        db_users = dbuser_svc.get_all_db_users()
    else:
        user_id = int(claims.get('sub', 0))
        db_users = dbuser_svc.get_db_users_for_owner(user_id)
    return jsonify({"db_users": [u.to_dict() for u in db_users]}), 200


@db_users_bp.route('/api/db-user/grant', methods=['POST'])
@admin_required_api
def api_grant_db_access():
    """API: Grant DB user access to a database."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_grant_permission(data)
    if not valid:
        return jsonify({"error": error}), 400

    ok, msg = dbuser_svc.grant_db_access(
        data['db_username'].strip(), data['db_name'].strip()
    )
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400


@db_users_bp.route('/api/db-user/revoke', methods=['DELETE'])
@admin_required_api
def api_revoke_db_access():
    """API: Revoke DB user access to a database."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_grant_permission(data)
    if not valid:
        return jsonify({"error": error}), 400

    ok, msg = dbuser_svc.revoke_db_access(
        data['db_username'].strip(), data['db_name'].strip()
    )
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400
