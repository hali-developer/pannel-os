"""
VPS Panel — User Services

Business logic for user CRUD operations.
"""
import os
import logging
from werkzeug.security import generate_password_hash
from flask import current_app
from app.extensions import db
from app.models.user import User

logger = logging.getLogger(__name__)


def create_user(username: str, password: str, role: str = 'client', email: str = None) -> tuple[bool, str, User]:
    """
    Create a new panel user.
    Sets up home directory path (actual dir creation happens via FTP module on Linux).
    """
    # Check for duplicates
    existing = User.query.filter_by(username=username).first()
    if existing:
        return False, f"Username '{username}' already exists.", None

    web_root = current_app.config.get('WEB_ROOT', '/var/www')
    home_dir = os.path.join(web_root, username)

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        email=email,
        role=role,
        home_directory=home_dir,
        is_active=True,
    )

    try:
        db.session.add(user)
        db.session.commit()
        logger.info(f"User created: {username} (role={role})")
        return True, f"User '{username}' created successfully.", user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create user {username}: {e}")
        return False, f"Database error: {str(e)}", None


def get_user_by_id(user_id: int) -> User:
    """Get a user by ID."""
    return User.query.get(user_id)


def get_user_by_username(username: str) -> User:
    """Get a user by username."""
    return User.query.filter_by(username=username).first()


def list_users(include_inactive: bool = False) -> list[User]:
    """List all users."""
    query = User.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(User.created_at.desc()).all()


def update_user(user_id: int, **kwargs) -> tuple[bool, str]:
    """Update user fields."""
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    if 'password' in kwargs and kwargs['password']:
        user.password_hash = generate_password_hash(kwargs['password'])
    if 'email' in kwargs:
        user.email = kwargs['email']
    if 'is_active' in kwargs:
        user.is_active = kwargs['is_active']
    if 'role' in kwargs and kwargs['role'] in ('admin', 'client'):
        user.role = kwargs['role']

    try:
        db.session.commit()
        logger.info(f"User updated: {user.username}")
        return True, "User updated successfully."
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def deactivate_user(user_id: int) -> tuple[bool, str]:
    """Soft-delete a user by deactivating them."""
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."
    if user.role == 'admin':
        # Don't deactivate the last admin
        admin_count = User.query.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            return False, "Cannot deactivate the last admin account."

    user.is_active = False
    try:
        db.session.commit()
        logger.info(f"User deactivated: {user.username}")
        return True, f"User '{user.username}' deactivated."
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def delete_user(user_id: int) -> tuple[bool, str]:
    """Permanently delete a user and cascade to related records."""
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            return False, "Cannot delete the last admin account."

    username = user.username
    try:
        db.session.delete(user)
        db.session.commit()
        logger.info(f"User deleted: {username}")
        return True, f"User '{username}' deleted."
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def get_dashboard_stats() -> dict:
    """Get summary statistics for the admin dashboard."""
    from app.models.domain import Domain
    from app.models.ftp_account import FTPAccount
    from app.models.database import ClientDatabase

    return {
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_clients': User.query.filter_by(role='client', is_active=True).count(),
        'total_admins': User.query.filter_by(role='admin', is_active=True).count(),
        'total_domains': Domain.query.filter_by(is_active=True).count(),
        'total_ftp_accounts': FTPAccount.query.filter_by(is_active=True).count(),
        'total_databases': ClientDatabase.query.count(),
    }
