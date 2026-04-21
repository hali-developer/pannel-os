"""
VPS Panel — Domains Module Services

Business logic for domain management.
Orchestrates between MySQL panel records and Apache configuration.
"""
import os
import logging
from flask import current_app
from app.extensions import db
from app.models.domain import Domain
from app.models.user import User
from app.services.apache_service import ApacheService

logger = logging.getLogger(__name__)


def add_domain(user_id: int, domain_name: str) -> tuple[bool, str]:
    """
    Add a domain to a user:
      1. Validate user exists
      2. Check for duplicate domain
      3. Generate & deploy Apache config
      4. Record in panel DB
    """
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    domain_name = domain_name.lower().strip()

    existing = Domain.query.filter_by(domain_name=domain_name).first()
    if existing:
        return False, f"Domain '{domain_name}' is already registered."

    web_root = current_app.config.get('WEB_ROOT', '/var/www')
    
    if user.role == "admin":
        base_path = web_root
    else:
        base_path = os.path.join(web_root, user.username)

    document_root = os.path.join(base_path, domain_name, 'public_html')

    # Deploy Apache config
    ok, msg = ApacheService.deploy_domain(domain_name, base_path)
    if not ok:
        return False, f"Apache deployment failed: {msg}"

    # Record in panel DB
    domain = Domain(
        user_id=user_id,
        domain_name=domain_name,
        document_root=document_root,
        is_active=True,
    )
    try:
        db.session.add(domain)
        db.session.commit()
        logger.info(f"Domain added: {domain_name} -> {document_root} (user: {user.username})")
        return True, f"Domain '{domain_name}' added and Apache configured."
    except Exception as e:
        db.session.rollback()
        ApacheService.undeploy_domain(domain_name, document_root)
        return False, f"Database error: {str(e)}"


def remove_domain(domain_name: str) -> tuple[bool, str]:
    """Remove a domain from both Apache and the database."""
    domain = Domain.query.filter_by(domain_name=domain_name).first()
    if not domain:
        return False, f"Domain '{domain_name}' not found."
    base_path = domain.document_root.replace(f"/public_html", "")
    # Remove from Apache
    ok, msg = ApacheService.undeploy_domain(domain_name, base_path)
    if not ok:
        logger.warning(f"Apache undeploy warning for {domain_name}: {msg}")

    # Remove from panel DB
    try:
        db.session.delete(domain)
        db.session.commit()
        logger.info(f"Domain removed: {domain_name}")
        return True, f"Domain '{domain_name}' removed."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def get_domains_for_user(user_id: int) -> list[Domain]:
    """Get all domains belonging to a user."""
    return Domain.query.filter_by(user_id=user_id, is_active=True).order_by(Domain.created_at.desc()).all()


def get_all_domains() -> list[Domain]:
    """Get all domains (admin view)."""
    return Domain.query.order_by(Domain.created_at.desc()).all()


def get_domain_by_name(domain_name: str) -> Domain:
    """Get a domain record by name."""
    return Domain.query.filter_by(domain_name=domain_name).first()


def install_ssl(domain_name: str) -> tuple[bool, str]:
    """
    Install a Let's Encrypt SSL certificate for the given domain:
      1. Verify domain exists in panel DB
      2. Run Certbot via ApacheService
      3. Mark ssl_enabled=True in database
    """
    domain = Domain.query.filter_by(domain_name=domain_name).first()
    if not domain:
        return False, f"Domain '{domain_name}' not found."

    if domain.ssl_enabled:
        return False, f"SSL is already enabled for '{domain_name}'."

    web_dir = domain.document_root.replace(f"/public_html", "")
    admin_email = current_app.config.get('SSL_ADMIN_EMAIL', f'{domain.user.email or "info@example.com"}')
    ok, msg = ApacheService.install_ssl(domain_name, web_dir, admin_email)
    if not ok:
        return False, msg

    try:
        domain.ssl_enabled = True
        db.session.commit()
        logger.info(f"SSL enabled for domain: {domain_name}")
        return True, f"SSL certificate installed for '{domain_name}'. HTTPS is now active."
    except Exception as e:
        db.session.rollback()
        return False, f"SSL installed on server but DB update failed: {str(e)}"


def revoke_ssl(domain_name: str) -> tuple[bool, str]:
    """
    Remove the Let's Encrypt SSL certificate for the given domain:
      1. Verify domain exists in panel DB
      2. Delete cert via Certbot
      3. Mark ssl_enabled=False in database
    """
    domain = Domain.query.filter_by(domain_name=domain_name).first()
    if not domain:
        return False, f"Domain '{domain_name}' not found."

    if not domain.ssl_enabled:
        return False, f"SSL is not enabled for '{domain_name}'."

    ok, msg = ApacheService.revoke_ssl(domain_name)
    if not ok:
        return False, msg

    try:
        domain.ssl_enabled = False
        db.session.commit()
        logger.info(f"SSL removed for domain: {domain_name}")
        return True, f"SSL certificate removed for '{domain_name}'."
    except Exception as e:
        db.session.rollback()
        return False, f"SSL removed on server but DB update failed: {str(e)}"

