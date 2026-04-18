"""
VPS Panel — User Services

Business logic for user CRUD operations.
Each panel user maps to a Linux system user for FTPS + file ownership.
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
    For 'client' role:
      - Creates a Linux system user (for FTPS + file ownership)
      - Sets up home directory at /var/www/{username}/public_html
      - Configures vsftpd for this user
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
        system_username=username if role == 'client' else None,
        is_active=True,
    )

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create user {username}: {e}")
        return False, f"Database error: {str(e)}", None

    # Automatically provision system resources for new client users
    if role == 'client':
        from app.services.ftp_service import FTPSystemService
        ok, msg = FTPSystemService.provision_ftp_user(username, password, home_dir)
        if not ok:
            logger.warning(f"System user provisioning failure for {username}: {msg}")
            # We don't fail the whole web account creation, but we log the error 
            # so it can be fixed manually or retried later.

    logger.info(f"User created with auto-provisioning: {username} (role={role})")
    return True, f"User '{username}' created successfully.", user


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
        # Also update system user password if they are a client
        if user.role == 'client' and user.system_username:
            from app.services.ftp_service import FTPSystemService
            FTPSystemService.set_password(user.system_username, kwargs['password'])

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
    """
    Permanently delete a user and cascade to related records.
    Cleans up:
      - Linux system user
      - PostgreSQL databases owned by this user
      - PostgreSQL DB users owned by this user
      - FTP accounts
      - Domains (Apache configs)
    """
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin', is_active=True).count()
        if admin_count <= 1:
            return False, "Cannot delete the last admin account."

    username = user.username

    # Cleanup: deprovision all databases
    from app.models.database import ClientDatabase
    from app.services.postgresql_service import PostgreSQLService
    client_dbs = ClientDatabase.query.filter_by(user_id=user_id).all()
    for cdb in client_dbs:
        PostgreSQLService.deprovision_database(cdb.db_name, cdb.db_user)

    # Cleanup: deprovision all DB users
    from app.models.db_user import DbUser
    db_users = DbUser.query.filter_by(owner_user_id=user_id).all()
    for dbu in db_users:
        PostgreSQLService.revoke_all_user_privileges(dbu.db_username)
        PostgreSQLService.drop_user(dbu.db_username)

    # Cleanup: deprovision domains (Apache configs)
    from app.models.domain import Domain
    from app.services.apache_service import ApacheService
    domains = Domain.query.filter_by(user_id=user_id).all()
    for dom in domains:
        ApacheService.undeploy_domain(dom.domain_name)

    # Cleanup: deprovision FTP / system user
    if user.role == 'client' and user.system_username:
        from app.services.ftp_service import FTPSystemService
        FTPSystemService.deprovision_ftp_user(user.system_username)

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
    from app.models.db_user import DbUser

    return {
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_clients': User.query.filter_by(role='client', is_active=True).count(),
        'total_admins': User.query.filter_by(role='admin', is_active=True).count(),
        'total_domains': Domain.query.filter_by(is_active=True).count(),
        'total_ftp_accounts': FTPAccount.query.filter_by(is_active=True).count(),
        'total_databases': ClientDatabase.query.count(),
        'total_db_users': DbUser.query.count(),
    }
