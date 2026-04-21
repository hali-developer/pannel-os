"""
VPS Panel — Mail Module Services

Business logic for managing mailbox accounts.
"""
import logging
from flask import current_app
from app.extensions import db
from app.models.email_account import EmailAccount
from app.models.domain import Domain
from app.models.user import User

logger = logging.getLogger(__name__)


def add_email_account(user_id: int, domain_id: int, email_user: str, password: str) -> tuple[bool, str]:
    """
    Create a new mailbox for a domain.
    """
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    domain = Domain.query.get(domain_id)
    if not domain or domain.user_id != user_id:
        return False, "Domain not found or unauthorized."

    email_user = email_user.lower().strip()
    email_address = f"{email_user}@{domain.domain_name}"

    # Check for duplicate
    existing = EmailAccount.query.filter_by(email_address=email_address).first()
    if existing:
        return False, f"Email address '{email_address}' already exists."

    # Use Bcrypt for mail server compatibility (usually handled by panel logic)
    from flask_bcrypt import Bcrypt
    bcrypt = Bcrypt()
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    # Register in DB
    account = EmailAccount(
        user_id=user_id,
        domain_id=domain_id,
        email_user=email_user,
        email_address=email_address,
        password_hash=password_hash,
        is_active=True
    )

    try:
        db.session.add(account)
        db.session.commit()
        logger.info(f"Email account created: {email_address} (user: {user.username})")
        return True, f"Mailbox '{email_address}' successfully created."
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating mailbox: {e}")
        return False, f"Database error: {str(e)}"


def delete_email_account(account_id: int, user_id: int) -> tuple[bool, str]:
    """Delete a mailbox."""
    account = EmailAccount.query.get(account_id)
    if not account:
        return False, "Mailbox not found."
    
    # Auth check: Client can only delete their own; Admin can delete any
    from app.models.user import User
    user = User.query.get(user_id)
    if user.role != 'admin' and account.user_id != user_id:
        return False, "Unauthorized."

    email_address = account.email_address
    try:
        db.session.delete(account)
        db.session.commit()
        logger.info(f"Email account deleted: {email_address}")
        return True, f"Mailbox '{email_address}' deleted."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def list_email_accounts(user_id: int) -> list[EmailAccount]:
    """Get all mailboxes for a specific user."""
    return EmailAccount.query.filter_by(user_id=user_id).all()


def list_all_email_accounts() -> list[EmailAccount]:
    """Get all mailboxes on the system (Admin only)."""
    return EmailAccount.query.all()


def change_email_password(account_id: int, user_id: int, new_password: str) -> tuple[bool, str]:
    """Update mailbox password."""
    account = EmailAccount.query.get(account_id)
    if not account:
        return False, "Mailbox not found."

    from app.models.user import User
    user = User.query.get(user_id)
    if user.role != 'admin' and account.user_id != user_id:
        return False, "Unauthorized."

    # Use Bcrypt for mail server compatibility
    from flask_bcrypt import Bcrypt
    bcrypt = Bcrypt()
    account.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')

    try:
        db.session.commit()
        return True, f"Password for {account.email_address} updated."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"
