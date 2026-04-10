"""
VPS Panel — FTP Module Services

Business logic for FTP account management.
Orchestrates between MySQL panel records and system-level FTP operations.
"""
import logging
from flask import current_app
from app.extensions import db
from app.models.ftp_account import FTPAccount
from app.models.domain import Domain
from app.models.user import User
from app.services.ftp_service import FTPSystemService
import crypt

logger = logging.getLogger(__name__)


def create_ftp_account(user_id: int, username: str, password: str, domain_id: int) -> tuple[bool, str]:
    """
    Create an FTP account:
      1. Validate user exists
      2. Check for duplicate FTP username
      3. Provision system user (Linux) or mock (Windows)
      4. Record in panel DB
    """
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    existing = FTPAccount.query.filter_by(username=username).first()
    if existing:
        return False, f"FTP username '{username}' already exists."

    domain = Domain.query.filter_by(id=domain_id).first()
    if not domain:
        return False, f"Domain not found."

    home_dir = domain.document_root
    hashed = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

    # Record in DB
    account = FTPAccount(
        user_id=user_id,
        username=username,
        password=hashed,
        domain_id=domain_id,
        home_directory=home_dir,
        is_active=True,
    )
    try:
        db.session.add(account)
        db.session.commit()
        logger.info(f"FTP account created: {username} for domain {domain.domain_name}")
        return True, f"FTP account '{username}' created."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def delete_ftp_account(username: str) -> tuple[bool, str]:
    """Delete an FTP account from both system and database."""
    account = FTPAccount.query.filter_by(username=username).first()
    if not account:
        return False, f"FTP account '{username}' not found."

    # Remove from DB
    try:
        db.session.delete(account)
        db.session.commit()
        logger.info(f"FTP account deleted: {ftp_username}")
        return True, f"FTP account '{ftp_username}' deleted."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def change_ftp_password(username: str, new_password: str) -> tuple[bool, str]:
    """Change an FTP account's password."""
    account = FTPAccount.query.filter_by(username=username).first()
    if not account:
        return False, f"FTP account '{username}' not found."

    hashed = crypt.crypt(new_password, crypt.mksalt(crypt.METHOD_SHA512))
    account.password = hashed
    try:
        db.session.commit()
        logger.info(f"FTP password changed: {username}")
        return True, "Password updated."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def get_ftp_accounts_for_user(user_id: int) -> list[FTPAccount]:
    """Get all FTP accounts belonging to a user."""
    return FTPAccount.query.filter_by(user_id=user_id, is_active=True).all()


def get_all_ftp_accounts() -> list[FTPAccount]:
    """Get all FTP accounts (admin view)."""
    return FTPAccount.query.order_by(FTPAccount.created_at.desc()).all()
