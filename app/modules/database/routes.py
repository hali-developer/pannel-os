"""
VPS Panel — Database Routes

Web and API routes for MySQL database management.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import admin_required_web, client_required_web, login_required_api, admin_required_api, log_activity
from app.modules.database.schemas import validate_create_db
from app.modules.database import services as db_svc
from app.modules.users.services import list_users, get_user_by_id

logger = logging.getLogger(__name__)

database_bp = Blueprint('database', __name__)


# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@database_bp.route('/admin/databases', methods=['GET'])
@admin_required_web
def admin_databases_page():
    """Database management page."""
    databases = db_svc.get_all_databases()
    users = list_users()
    return render_template('admin/databases.html', databases=databases, users=users)


@database_bp.route('/admin/databases/create', methods=['POST'])
@admin_required_web
@log_activity('create_database')
def admin_create_database():
    """Create a MySQL database for a user."""
    valid, error = validate_create_db(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('database.admin_databases_page'))

    user_id = request.form.get('user_id', type=int)
    db_name = request.form.get('db_name', '').strip()
    db_user = request.form.get('db_user', '').strip()
    password = request.form.get('password', '')

    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('database.admin_databases_page'))

    ok, msg = db_svc.create_database(user_id, db_name, db_user, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('database.admin_databases_page'))


@database_bp.route('/admin/databases/<string:db_name>/delete', methods=['POST'])
@admin_required_web
@log_activity('delete_database')
def admin_delete_database(db_name):
    """Delete a MySQL database."""
    ok, msg = db_svc.delete_database(db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('database.admin_databases_page'))


# ════════════════════════════════════════
# CLIENT WEB ROUTES
# ════════════════════════════════════════

@database_bp.route('/client/databases/create', methods=['POST'])
@client_required_web
@log_activity('client_create_database')
def client_create_database():
    """Client creates their own database."""
    valid, error = validate_create_db(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('users.client_dashboard'))

    user_id = session['user_id']
    user = get_user_by_id(user_id)
    if not user:
        flash('Session error. Please log in again.', 'danger')
        return redirect(url_for('auth.login_page'))

    db_name = request.form.get('db_name', '').strip()
    db_user = request.form.get('db_user', '').strip()
    password = request.form.get('password', '')

    # Enforce username prefix for client isolation
    prefix = f"{user.username}_"
    if not db_name.startswith(prefix):
        db_name = prefix + db_name
    if not db_user.startswith(prefix):
        db_user = prefix + db_user

    ok, msg = db_svc.create_database(user_id, db_name, db_user, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@database_bp.route('/client/databases/<string:db_name>/delete', methods=['POST'])
@client_required_web
@log_activity('client_delete_database')
def client_delete_database(db_name):
    """Client deletes their own database."""
    # Verify ownership
    record = db_svc.get_database_by_name(db_name)
    if not record or record.user_id != session['user_id']:
        flash('Database not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    ok, msg = db_svc.delete_database(db_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


# ════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════

@database_bp.route('/api/db/create', methods=['POST'])
@admin_required_api
def api_create_database():
    """API: Create a MySQL database."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_create_db(data)
    if not valid:
        return jsonify({"error": error}), 400

    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    ok, msg = db_svc.create_database(
        user_id,
        data['db_name'].strip(),
        data['db_user'].strip(),
        data['password'],
    )
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400


@database_bp.route('/api/db/list', methods=['GET'])
@login_required_api
def api_list_databases():
    """API: List databases."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get('role') == 'admin':
        databases = db_svc.get_all_databases()
    else:
        user_id = int(claims.get('sub', 0))
        databases = db_svc.get_databases_for_user(user_id)
    return jsonify({"databases": [d.to_dict() for d in databases]}), 200


@database_bp.route('/api/db/delete', methods=['DELETE'])
@admin_required_api
def api_delete_database():
    """API: Delete a database."""
    data = request.get_json(silent=True) or {}
    db_name = (data.get('db_name') or '').strip()
    if not db_name:
        return jsonify({"error": "db_name is required"}), 400

    ok, msg = db_svc.delete_database(db_name)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400
