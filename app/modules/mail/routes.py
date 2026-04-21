"""
VPS Panel — Mail Module Routing
"""
import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from app.core.decorators import admin_required_web, client_required_web, log_activity, admin_required_api
from app.modules.mail import services as mail_svc
from app.modules.domains.services import get_all_domains, get_domains_for_user
from app.modules.users.services import list_users

logger = logging.getLogger(__name__)

mail_bp = Blueprint('mail', __name__)

# ════════════════════════════════════════
# ADMIN WEB ROUTES
# ════════════════════════════════════════

@mail_bp.route('/admin/mail', methods=['GET'])
@admin_required_web
def admin_mail_page():
    """Admin mail management page."""
    mailboxes = mail_svc.list_all_email_accounts()
    domains = get_all_domains()
    users = list_users()
    return render_template('admin/mail.html', mailboxes=mailboxes, domains=domains, users=users)

@mail_bp.route('/admin/mail/add', methods=['POST'])
@admin_required_web
@log_activity('add_mailbox')
def admin_add_mailbox():
    """Admin adds a mailbox for a user."""
    user_id = request.form.get('user_id', type=int)
    domain_id = request.form.get('domain_id', type=int)
    email_user = request.form.get('email_user', '').strip()
    password = request.form.get('password', '')

    if not all([user_id, domain_id, email_user, password]):
        flash("All fields are required.", "danger")
        return redirect(url_for('mail.admin_mail_page'))

    ok, msg = mail_svc.add_email_account(user_id, domain_id, email_user, password)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('mail.admin_mail_page'))

@mail_bp.route('/admin/mail/<int:account_id>/delete', methods=['POST'])
@admin_required_web
@log_activity('delete_mailbox')
def admin_delete_mailbox(account_id):
    """Admin deletes a mailbox."""
    ok, msg = mail_svc.delete_email_account(account_id, session['user_id'])
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('mail.admin_mail_page'))


# ════════════════════════════════════════
# CLIENT WEB ROUTES
# ════════════════════════════════════════

@mail_bp.route('/client/mail', methods=['GET'])
@client_required_web
def client_mail_page():
    """Client mail management page."""
    user_id = session['user_id']
    mailboxes = mail_svc.list_email_accounts(user_id)
    domains = get_domains_for_user(user_id)
    return render_template('client/mail.html', mailboxes=mailboxes, domains=domains)

@mail_bp.route('/client/mail/add', methods=['POST'])
@client_required_web
@log_activity('client_add_mailbox')
def client_add_mailbox():
    """Client adds their own mailbox."""
    user_id = session['user_id']
    domain_id = request.form.get('domain_id', type=int)
    email_user = request.form.get('email_user', '').strip()
    password = request.form.get('password', '')

    if not all([domain_id, email_user, password]):
        flash("All fields are required.", "danger")
        return redirect(url_for('mail.client_mail_page'))

    ok, msg = mail_svc.add_email_account(user_id, domain_id, email_user, password)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('mail.client_mail_page'))

@mail_bp.route('/client/mail/<int:account_id>/delete', methods=['POST'])
@client_required_web
@log_activity('client_delete_mailbox')
def client_delete_mailbox(account_id):
    """Client deletes their own mailbox."""
    ok, msg = mail_svc.delete_email_account(account_id, session['user_id'])
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('mail.client_mail_page'))
