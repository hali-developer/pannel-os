"""
VPS Panel — FTP Routes

Web and API routes for FTP account management.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import admin_required_web, login_required_api, admin_required_api, log_activity
from app.modules.ftp.schemas import validate_create_ftp, validate_change_password
from app.modules.ftp import services as ftp_svc
from app.modules.users.services import list_users
from app.modules.domains.services import get_all_domains

logger = logging.getLogger(__name__)

ftp_bp = Blueprint('ftp', __name__)


# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@ftp_bp.route('/admin/ftp', methods=['GET'])
@admin_required_web
def admin_ftp_page():
    """FTP management page."""
    accounts = ftp_svc.get_all_ftp_accounts()
    users = list_users()
    domains = get_all_domains()
    return render_template('admin/ftp.html', accounts=accounts, users=users, domains=domains)


@ftp_bp.route('/admin/ftp/create', methods=['POST'])
@admin_required_web
@log_activity('create_ftp')
def admin_create_ftp():
    """Create an FTP account."""
    valid, error = validate_create_ftp(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('ftp.admin_ftp_page'))

    user_id = request.form.get('user_id', type=int)
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    domain_id = request.form.get('domain_id', type=int)

    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('ftp.admin_ftp_page'))
    
    if not domain_id:
        flash('Please select a domain.', 'danger')
        return redirect(url_for('ftp.admin_ftp_page'))

    ok, msg = ftp_svc.create_ftp_account(user_id, username, password, domain_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('ftp.admin_ftp_page'))


@ftp_bp.route('/admin/ftp/<string:username>/delete', methods=['POST'])
@admin_required_web
@log_activity('delete_ftp')
def admin_delete_ftp(username):
    """Delete an FTP account."""
    ok, msg = ftp_svc.delete_ftp_account(username)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('ftp.admin_ftp_page'))


@ftp_bp.route('/admin/ftp/<string:username>/password', methods=['POST'])
@admin_required_web
@log_activity('change_ftp_password')
def admin_change_ftp_password(username):
    """Change FTP password."""
    valid, error = validate_change_password(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('ftp.admin_ftp_page'))

    password = request.form.get('password', '')
    ok, msg = ftp_svc.change_ftp_password(username, password)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('ftp.admin_ftp_page'))


# ════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════

@ftp_bp.route('/api/ftp/create', methods=['POST'])
@admin_required_api
def api_create_ftp():
    """API: Create FTP account."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_create_ftp(data)
    if not valid:
        return jsonify({"error": error}), 400

    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    ok, msg = ftp_svc.create_ftp_account(
        user_id, data['username'].strip(), data['password']
    )
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400


@ftp_bp.route('/api/ftp/password', methods=['PUT'])
@admin_required_api
def api_change_ftp_password():
    """API: Change FTP password."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username:
        return jsonify({"error": "username is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    ok, msg = ftp_svc.change_ftp_password(username, password)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@ftp_bp.route('/api/ftp/delete', methods=['DELETE'])
@admin_required_api
def api_delete_ftp():
    """API: Delete FTP account."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    if not username:
        return jsonify({"error": "username is required"}), 400

    ok, msg = ftp_svc.delete_ftp_account(username)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@ftp_bp.route('/api/ftp/list', methods=['GET'])
@login_required_api
def api_list_ftp():
    """API: List FTP accounts."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get('role') == 'admin':
        accounts = ftp_svc.get_all_ftp_accounts()
    else:
        user_id = int(claims.get('sub', 0))
        accounts = ftp_svc.get_ftp_accounts_for_user(user_id)
    return jsonify({"accounts": [a.to_dict() for a in accounts]}), 200
