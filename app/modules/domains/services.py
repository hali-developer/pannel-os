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
    document_root = os.path.join(web_root, user.username, 'public_html')

    # Deploy Apache config
    ok, msg = ApacheService.deploy_domain(domain_name, document_root)
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
        ApacheService.undeploy_domain(domain_name)
        return False, f"Database error: {str(e)}"


def remove_domain(domain_name: str) -> tuple[bool, str]:
    """Remove a domain from both Apache and the database."""
    domain = Domain.query.filter_by(domain_name=domain_name).first()
    if not domain:
        return False, f"Domain '{domain_name}' not found."

    # Remove from Apache
    ok, msg = ApacheService.undeploy_domain(domain_name)
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
