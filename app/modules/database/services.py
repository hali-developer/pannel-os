"""
VPS Panel — Database Module Services

Business logic for client MySQL database management.
Orchestrates between MySQL panel records and MySQL provisioning.
"""
import logging
from app.extensions import db
from app.models.database import ClientDatabase
from app.models.db_user_permission import DbUserPermission
from app.models.user import User
from app.services.postgresql_service import PostgreSQLService
from app.services.mysql_service import MySQLService
from app.core.pgadmin_sync import sync_user_to_pgadmin

logger = logging.getLogger(__name__)


def create_database(user_id: int, db_name: str, db_user: str, password: str, db_type: str = 'postgres') -> tuple[bool, str]:
    """
    Create a client MySQL database with unique prefixed names.
    """
    from app.core.utils import generate_prefixed_name
    
    # Apply unique prefixes
    db_name = generate_prefixed_name(db_name)
    db_user = generate_prefixed_name(db_user)
    
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    # Check for existing
    existing = ClientDatabase.query.filter_by(db_name=db_name).first()
    if existing:
        return False, f"Database '{db_name}' already exists."

    # Provision on selected engine
    if db_type == 'mysql':
        ok, msg = MySQLService.provision_database(db_name, db_user, password)
    else:
        ok, msg = PostgreSQLService.provision_database(db_name, db_user, password)
        # Sync to pgAdmin
        if ok:
            sync_user_to_pgadmin(db_user, password)
            
    if not ok:
        return False, f"{db_type.capitalize()} provisioning failed: {msg}"

    # Record in panel DB
    record = ClientDatabase(
        user_id=user_id,
        db_name=db_name,
        db_type=db_type,
        db_user=db_user,
        db_host='localhost',
    )
    try:
        db.session.add(record)
        db.session.commit()
        logger.info(f"Database created: {db_name} (user: {db_user}) for {user.username}")
        return True, f"Database '{db_name}' created with user '{db_user}'."
    except Exception as e:
        db.session.rollback()
        # Rollback provisioning
        if db_type == 'mysql':
            MySQLService.deprovision_database(db_name, db_user)
        else:
            PostgreSQLService.deprovision_database(db_name, db_user)
        return False, f"Database error: {str(e)}"


def delete_database(db_name: str) -> tuple[bool, str]:
    """Delete a client MySQL database from both MySQL and panel DB."""
    record = ClientDatabase.query.filter_by(db_name=db_name).first()
    if not record:
        return False, f"Database '{db_name}' not found in panel."

    db_user = record.db_user

    # Revoke all DB user permissions for this database
    permissions = DbUserPermission.query.filter_by(db_id=record.id).all()
    for perm in permissions:
        try:
            if record.db_type == 'mysql':
                MySQLService.revoke_privileges(db_name, perm.db_user.db_username)
            else:
                PostgreSQLService.revoke_privileges(db_name, perm.db_user.db_username)
        except Exception:
            pass
        db.session.delete(perm)

    # Deprovision from engine
    if record.db_type == 'mysql':
        ok, msg = MySQLService.deprovision_database(db_name, db_user)
    else:
        ok, msg = PostgreSQLService.deprovision_database(db_name, db_user)
        
    if not ok:
        logger.warning(f"{record.db_type.capitalize()} deprovision warning for {db_name}: {msg}")

    # Remove from panel DB
    try:
        db.session.delete(record)
        db.session.commit()
        logger.info(f"Database deleted: {db_name}")
        return True, f"Database '{db_name}' and user '{db_user}' removed."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def update_database_password(db_name: str, new_password: str) -> tuple[bool, str]:
    """Update the primary DB user password for a database."""
    record = ClientDatabase.query.filter_by(db_name=db_name).first()
    if not record:
        return False, f"Database '{db_name}' not found."

    if record.db_type == 'mysql':
        ok, msg = MySQLService.update_user_password(record.db_user, new_password)
    else:
        ok, msg = PostgreSQLService.update_user_password(record.db_user, new_password)
        # Sync to pgAdmin
        if ok:
            sync_user_to_pgadmin(record.db_user, new_password)

    if not ok:
        return False, f"Password update failed: {msg}"

    logger.info(f"Password updated for DB user: {record.db_user}")
    return True, f"Password updated for '{record.db_user}'."


def get_databases_for_user(user_id: int) -> list[ClientDatabase]:
    """Get all databases belonging to a user."""
    return ClientDatabase.query.filter_by(user_id=user_id).order_by(ClientDatabase.created_at.desc()).all()


def get_all_databases() -> list[ClientDatabase]:
    """Get all databases (admin view)."""
    return ClientDatabase.query.order_by(ClientDatabase.created_at.desc()).all()


def get_database_by_name(db_name: str) -> ClientDatabase:
    """Get a database record by name."""
    return ClientDatabase.query.filter_by(db_name=db_name).first()
