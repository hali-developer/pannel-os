"""
VPS Panel — DB User Module Services

Business logic for PostgreSQL database user management.
Orchestrates between panel DB records and PostgreSQL user provisioning.

Architecture:
  - DbUser: a PostgreSQL user created for a panel client
  - DbUserPermission: maps which DbUser can access which ClientDatabase
  - PostgreSQL GRANT/REVOKE ensures permissions are correct.
"""
import logging
from cryptography.fernet import Fernet
from flask import current_app
from app.extensions import db
from app.models.db_user import DbUser
from app.models.db_user_permission import DbUserPermission
from app.models.database import ClientDatabase
from app.models.user import User
from app.services.postgresql_service import PostgreSQLService
from app.services.mysql_service import MySQLService
from app.core.pgadmin_sync import sync_user_to_pgadmin

logger = logging.getLogger(__name__)


def _get_fernet():
    """Get Fernet cipher for encrypting DB passwords."""
    key = current_app.config.get('DB_PASSWORD_ENCRYPTION_KEY')
    if not key:
        # Fallback: derive from SECRET_KEY (not ideal but functional)
        import base64
        import hashlib
        secret = current_app.config['SECRET_KEY']
        derived = hashlib.sha256(secret.encode()).digest()
        key = base64.urlsafe_b64encode(derived)
    else:
        key = key.encode() if isinstance(key, str) else key
    return Fernet(key)


def _encrypt_password(password: str) -> str:
    """Encrypt a password for storage."""
    f = _get_fernet()
    return f.encrypt(password.encode()).decode()


def _decrypt_password(encrypted: str) -> str:
    """Decrypt a stored password."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


# ════════════════════════════════════════
# DB USER CRUD
# ════════════════════════════════════════

def create_db_user(owner_user_id: int, db_username: str, password: str, db_type: str = 'postgres') -> tuple[bool, str]:
    """
    Create a database user with a unique prefixed name.
    """
    from app.core.utils import generate_prefixed_name
    
    # Apply unique prefix
    db_username = generate_prefixed_name(db_username)
    
    owner = User.query.get(owner_user_id)
    if not owner:
        return False, "Owner user not found."

    existing = DbUser.query.filter_by(db_username=db_username).first()
    if existing:
        return False, f"DB username '{db_username}' already exists."

    # Create on selected engine
    if db_type == 'mysql':
        ok, msg = MySQLService.create_user(db_username, password)
    else:
        ok, msg = PostgreSQLService.create_user(db_username, password)
        if ok:
            sync_user_to_pgadmin(db_username, password)
            
    if not ok:
        return False, f"{db_type.capitalize()} user creation failed: {msg}"

    # Record in panel DB
    try:
        encrypted_pwd = _encrypt_password(password)
    except Exception as e:
        PostgreSQLService.drop_user(db_username)
        return False, f"Password encryption failed: {str(e)}"

    record = DbUser(
        db_username=db_username,
        db_type=db_type,
        db_password_encrypted=encrypted_pwd,
        owner_user_id=owner_user_id,
        db_host='localhost',
    )
    try:
        db.session.add(record)
        db.session.commit()
        logger.info(f"DB user created: {db_username} for {owner.username}")
        return True, f"DB user '{db_username}' created."
    except Exception as e:
        db.session.rollback()
        if db_type == 'mysql':
            MySQLService.drop_user(db_username)
        else:
            PostgreSQLService.drop_user(db_username)
        return False, f"Database error: {str(e)}"


def delete_db_user(db_username: str) -> tuple[bool, str]:
    """Delete a DB user from both PostgreSQL and panel DB."""
    record = DbUser.query.filter_by(db_username=db_username).first()
    if not record:
        return False, f"DB user '{db_username}' not found."

    # Drop from engine
    if record.db_type == 'mysql':
        ok, msg = MySQLService.drop_user(db_username) 
    else:
        PostgreSQLService.revoke_all_user_privileges(db_username)
        ok, msg = PostgreSQLService.drop_user(db_username)

    if not ok:
        logger.warning(f"{record.db_type.capitalize()} drop user warning for {db_username}: {msg}")

    # Remove from panel DB (cascades to permissions)
    try:
        db.session.delete(record)
        db.session.commit()
        logger.info(f"DB user deleted: {db_username}")
        return True, f"DB user '{db_username}' deleted."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def update_db_user_password(db_username: str, new_password: str) -> tuple[bool, str]:
    """Update a DB user's password in both PostgreSQL and panel DB."""
    record = DbUser.query.filter_by(db_username=db_username).first()
    if not record:
        return False, f"DB user '{db_username}' not found."

    # Update on engine
    if record.db_type == 'mysql':
        ok, msg = MySQLService.update_user_password(db_username, new_password)
    else:
        ok, msg = PostgreSQLService.update_user_password(db_username, new_password)
        if ok:
            sync_user_to_pgadmin(db_username, new_password)
            
    if not ok:
        return False, f"{record.db_type.capitalize()} password update failed: {msg}"

    # Update encrypted password in panel DB
    try:
        record.db_password_encrypted = _encrypt_password(new_password)
        db.session.commit()
        logger.info(f"DB user password updated: {db_username}")
        return True, f"Password updated for '{db_username}'."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


# ════════════════════════════════════════
# PERMISSION MANAGEMENT
# ════════════════════════════════════════

def grant_db_access(db_username: str, db_name: str) -> tuple[bool, str]:
    """
    Grant a DB user access to a specific database:
      1. Validate both exist
      2. Check for duplicate permission
      3. GRANT on PostgreSQL
      4. Record permission
    """
    db_user_record = DbUser.query.filter_by(db_username=db_username).first()
    if not db_user_record:
        return False, f"DB user '{db_username}' not found."

    db_record = ClientDatabase.query.filter_by(db_name=db_name).first()
    if not db_record:
        return False, f"Database '{db_name}' not found."

    # Check for existing permission
    existing = DbUserPermission.query.filter_by(
        db_user_id=db_user_record.id,
        db_id=db_record.id,
    ).first()
    if existing:
        return False, f"'{db_username}' already has access to '{db_name}'."

    # ENFORCE ENGINE ISOLATION
    if db_user_record.db_type != db_record.db_type:
        return False, f"Engine mismatch: Cannot grant {db_user_record.db_type} user access to {db_record.db_type} database."

    # Grant on engine
    if db_record.db_type == 'mysql':
        ok, msg = MySQLService.grant_privileges(db_name, db_username)
    else:
        ok, msg = PostgreSQLService.grant_privileges(db_name, db_username)
        
    if not ok:
        return False, f"{db_record.db_type.capitalize()} GRANT failed: {msg}"

    # Record permission
    perm = DbUserPermission(
        db_user_id=db_user_record.id,
        db_id=db_record.id,
    )
    try:
        db.session.add(perm)
        db.session.commit()
        logger.info(f"Granted {db_username} access to {db_name}")
        return True, f"'{db_username}' granted access to '{db_name}'."
    except Exception as e:
        db.session.rollback()
        PostgreSQLService.revoke_privileges(db_name, db_username)
        return False, f"Database error: {str(e)}"


def revoke_db_access(db_username: str, db_name: str) -> tuple[bool, str]:
    """Revoke a DB user's access to a specific database."""
    db_user_record = DbUser.query.filter_by(db_username=db_username).first()
    if not db_user_record:
        return False, f"DB user '{db_username}' not found."

    db_record = ClientDatabase.query.filter_by(db_name=db_name).first()
    if not db_record:
        return False, f"Database '{db_name}' not found."

    perm = DbUserPermission.query.filter_by(
        db_user_id=db_user_record.id,
        db_id=db_record.id,
    ).first()
    if not perm:
        return False, f"'{db_username}' does not have access to '{db_name}'."

    # Revoke on engine
    if db_record.db_type == 'mysql':
        ok, msg = MySQLService.revoke_privileges(db_name, db_username)
    else:
        ok, msg = PostgreSQLService.revoke_privileges(db_name, db_username)
        
    if not ok:
        logger.warning(f"{db_record.db_type.capitalize()} REVOKE warning: {msg}")

    # Remove permission record
    try:
        db.session.delete(perm)
        db.session.commit()
        logger.info(f"Revoked {db_username} access from {db_name}")
        return True, f"'{db_username}' access to '{db_name}' revoked."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


# ════════════════════════════════════════
# QUERIES
# ════════════════════════════════════════

def get_db_users_for_owner(owner_user_id: int) -> list[DbUser]:
    """Get all DB users belonging to a panel user."""
    return DbUser.query.filter_by(owner_user_id=owner_user_id).order_by(DbUser.created_at.desc()).all()


def get_all_db_users() -> list[DbUser]:
    """Get all DB users (admin view)."""
    return DbUser.query.order_by(DbUser.created_at.desc()).all()


def get_db_user_by_username(db_username: str) -> DbUser:
    """Get a DB user record by username."""
    return DbUser.query.filter_by(db_username=db_username).first()


def get_permissions_for_db_user(db_user_id: int) -> list[DbUserPermission]:
    """Get all permissions for a DB user."""
    return DbUserPermission.query.filter_by(db_user_id=db_user_id).all()


def get_permissions_for_database(db_id: int) -> list[DbUserPermission]:
    """Get all permissions for a database."""
    return DbUserPermission.query.filter_by(db_id=db_id).all()
