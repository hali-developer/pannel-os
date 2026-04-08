"""
VPS Panel — FTP Module Services

Business logic for FTP account management.
Orchestrates between MySQL panel records and system-level FTP operations.
"""
import logging
from flask import current_app
from app.extensions import db
from app.models.ftp_account import FTPAccount
from app.models.user import User
from app.services.ftp_service import FTPSystemService

logger = logging.getLogger(__name__)


def create_ftp_account(user_id: int, ftp_username: str, password: str) -> tuple[bool, str]:
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

    existing = FTPAccount.query.filter_by(ftp_username=ftp_username).first()
    if existing:
        return False, f"FTP username '{ftp_username}' already exists."

    home_dir = user.home_directory or FTPSystemService.get_home_directory(user.username)

    # Provision on the system
    ok, msg = FTPSystemService.provision_ftp_user(ftp_username, password, home_dir)
    if not ok:
        return False, f"System provisioning failed: {msg}"

    # Record in DB
    account = FTPAccount(
        user_id=user_id,
        ftp_username=ftp_username,
        home_directory=home_dir,
        is_active=True,
    )
    try:
        db.session.add(account)
        db.session.commit()
        logger.info(f"FTP account created: {ftp_username} for user {user.username}")
        return True, f"FTP account '{ftp_username}' created."
    except Exception as e:
        db.session.rollback()
        # Rollback system user
        FTPSystemService.deprovision_ftp_user(ftp_username)
        return False, f"Database error: {str(e)}"


def delete_ftp_account(ftp_username: str) -> tuple[bool, str]:
    """Delete an FTP account from both system and database."""
    account = FTPAccount.query.filter_by(ftp_username=ftp_username).first()
    if not account:
        return False, f"FTP account '{ftp_username}' not found."

    # Remove from system
    ok, msg = FTPSystemService.deprovision_ftp_user(ftp_username)
    if not ok:
        logger.warning(f"System deprovision warning for {ftp_username}: {msg}")

    # Remove from DB
    try:
        db.session.delete(account)
        db.session.commit()
        logger.info(f"FTP account deleted: {ftp_username}")
        return True, f"FTP account '{ftp_username}' deleted."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def change_ftp_password(ftp_username: str, new_password: str) -> tuple[bool, str]:
    """Change an FTP account's password."""
    account = FTPAccount.query.filter_by(ftp_username=ftp_username).first()
    if not account:
        return False, f"FTP account '{ftp_username}' not found."

    ok, msg = FTPSystemService.set_password(ftp_username, new_password)
    if not ok:
        return False, f"Password change failed: {msg}"

    logger.info(f"FTP password changed: {ftp_username}")
    return True, "Password updated."


def get_ftp_accounts_for_user(user_id: int) -> list[FTPAccount]:
    """Get all FTP accounts belonging to a user."""
    return FTPAccount.query.filter_by(user_id=user_id, is_active=True).all()


def get_all_ftp_accounts() -> list[FTPAccount]:
    """Get all FTP accounts (admin view)."""
    return FTPAccount.query.order_by(FTPAccount.created_at.desc()).all()
