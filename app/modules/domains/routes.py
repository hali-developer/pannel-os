"""
VPS Panel — Domain Routes

Web and API routes for domain management.
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import admin_required_web, client_required_web, login_required_api, admin_required_api, log_activity
from app.modules.domains.schemas import validate_add_domain
from app.modules.domains import services as domain_svc
from app.modules.users.services import list_users

logger = logging.getLogger(__name__)

domains_bp = Blueprint('domains', __name__)


# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@domains_bp.route('/admin/domains', methods=['GET'])
@admin_required_web
def admin_domains_page():
    """Domain management page."""
    domains = domain_svc.get_all_domains()
    users = list_users()
    return render_template('admin/domains.html', domains=domains, users=users)


@domains_bp.route('/admin/domains/add', methods=['POST'])
@admin_required_web
@log_activity('add_domain')
def admin_add_domain():
    """Add a domain."""
    valid, error = validate_add_domain(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('domains.admin_domains_page'))

    user_id = request.form.get('user_id', type=int)
    domain_name = request.form.get('domain_name', '').strip().lower()

    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('domains.admin_domains_page'))

    ok, msg = domain_svc.add_domain(user_id, domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('domains.admin_domains_page'))


@domains_bp.route('/admin/domains/<string:domain_name>/remove', methods=['POST'])
@admin_required_web
@log_activity('remove_domain')
def admin_remove_domain(domain_name):
    """Remove a domain."""
    ok, msg = domain_svc.remove_domain(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('domains.admin_domains_page'))


@domains_bp.route('/admin/domains/<string:domain_name>/ssl/install', methods=['POST'])
@admin_required_web
@log_activity('install_ssl')
def admin_install_ssl(domain_name):
    """Install SSL certificate for a domain."""
    domain = domain_svc.get_domain_by_name(domain_name)
    if not domain or domain.user_id != session['user_id']:
        flash('Domain not found or access denied.', 'danger')
        return redirect(url_for('domains.client_domains_page'))
    ok, msg = domain_svc.install_ssl(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('domains.admin_domains_page'))


@domains_bp.route('/admin/domains/<string:domain_name>/ssl/revoke', methods=['POST'])
@admin_required_web
@log_activity('revoke_ssl')
def admin_revoke_ssl(domain_name):
    """Revoke SSL certificate for a domain."""
    ok, msg = domain_svc.revoke_ssl(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('domains.admin_domains_page'))


@domains_bp.route('/client/domains', methods=['GET'])
@client_required_web
def client_domains_page():
    """Client domain management page."""
    user_id = session['user_id']
    domains = domain_svc.get_domains_for_user(user_id)
    from app.modules.users.services import get_user_by_id
    user = get_user_by_id(user_id)
    return render_template('client/domains.html', domains=domains, user=user)


# ════════════════════════════════════════
# CLIENT ACTION ROUTES
# ════════════════════════════════════════

@domains_bp.route('/client/domains/add', methods=['POST'])
@client_required_web
@log_activity('client_add_domain')
def client_add_domain():
    """Client adds their own domain."""
    valid, error = validate_add_domain(request.form)
    if not valid:
        flash(error, 'danger')
        return redirect(url_for('domains.client_domains_page'))

    user_id = session['user_id']
    from app.modules.users.services import get_user_by_id
    user = get_user_by_id(user_id)
    if not user:
        flash('Session error. Please log in again.', 'danger')
        return redirect(url_for('auth.login_page'))

    domain_name = request.form.get('domain_name', '').strip().lower()

    ok, msg = domain_svc.add_domain(user_id, domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@domains_bp.route('/client/domains/<string:domain_name>/remove', methods=['POST'])
@client_required_web
@log_activity('client_remove_domain')
def client_remove_domain(domain_name):
    """Client removes their own domain."""
    domain = domain_svc.get_domain_by_name(domain_name)
    if not domain or domain.user_id != session['user_id']:
        flash('Domain not found or access denied.', 'danger')
        return redirect(url_for('domains.client_domains_page'))

    ok, msg = domain_svc.remove_domain(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@domains_bp.route('/client/domains/<string:domain_name>/ssl/install', methods=['POST'])
@client_required_web
@log_activity('client_install_ssl')
def client_install_ssl(domain_name):
    """Client installs SSL for their own domain."""
    domain = domain_svc.get_domain_by_name(domain_name)
    if not domain or domain.user_id != session['user_id']:
        flash('Domain not found or access denied.', 'danger')
        return redirect(url_for('domains.client_domains_page'))
    
    ok, msg = domain_svc.install_ssl(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))


@domains_bp.route('/client/domains/<string:domain_name>/ssl/revoke', methods=['POST'])
@client_required_web
@log_activity('client_revoke_ssl')
def client_revoke_ssl(domain_name):
    """Client revokes SSL for their own domain."""
    domain = domain_svc.get_domain_by_name(domain_name)
    if not domain or domain.user_id != session['user_id']:
        flash('Domain not found or access denied.', 'danger')
        return redirect(url_for('users.client_dashboard'))

    ok, msg = domain_svc.revoke_ssl(domain_name)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('users.client_dashboard'))



# ════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════

@domains_bp.route('/api/domain/add', methods=['POST'])
@admin_required_api
def api_add_domain():
    """API: Add a domain."""
    data = request.get_json(silent=True) or {}
    valid, error = validate_add_domain(data)
    if not valid:
        return jsonify({"error": error}), 400

    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    ok, msg = domain_svc.add_domain(user_id, data['domain_name'].strip().lower())
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400


@domains_bp.route('/api/domain/remove', methods=['DELETE'])
@admin_required_api
def api_remove_domain():
    """API: Remove a domain."""
    data = request.get_json(silent=True) or {}
    domain_name = (data.get('domain_name') or '').strip().lower()
    if not domain_name:
        return jsonify({"error": "domain_name is required"}), 400

    ok, msg = domain_svc.remove_domain(domain_name)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@domains_bp.route('/api/domain/list', methods=['GET'])
@login_required_api
def api_list_domains():
    """API: List domains."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get('role') == 'admin':
        domains = domain_svc.get_all_domains()
    else:
        user_id = int(claims.get('sub', 0))
        domains = domain_svc.get_domains_for_user(user_id)
    return jsonify({"domains": [d.to_dict() for d in domains]}), 200


@domains_bp.route('/api/domain/<string:domain_name>/ssl/install', methods=['POST'])
@admin_required_api
def api_install_ssl(domain_name):
    """API: Install SSL certificate for a domain."""
    ok, msg = domain_svc.install_ssl(domain_name)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400


@domains_bp.route('/api/domain/<string:domain_name>/ssl/revoke', methods=['POST'])
@admin_required_api
def api_revoke_ssl(domain_name):
    """API: Revoke SSL certificate for a domain."""
    ok, msg = domain_svc.revoke_ssl(domain_name)
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400

