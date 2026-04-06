"""
VPS Panel — Database Module Services

Business logic for client MySQL database management.
Orchestrates between PostgreSQL records and MySQL provisioning.
"""
import logging
from app.extensions import db
from app.models.database import ClientDatabase
from app.models.user import User
from app.services.mysql_service import MySQLService

logger = logging.getLogger(__name__)


def create_database(user_id: int, db_name: str, db_user: str, password: str) -> tuple[bool, str]:
    """
    Create a client MySQL database:
      1. Validate user exists
      2. Check for duplicates in panel DB
      3. Provision on MySQL (CREATE DATABASE, CREATE USER, GRANT)
      4. Record in PostgreSQL
    """
    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    # Check for existing
    existing = ClientDatabase.query.filter_by(db_name=db_name).first()
    if existing:
        return False, f"Database '{db_name}' already exists."

    # Provision on MySQL
    ok, msg = MySQLService.provision_database(db_name, db_user, password)
    if not ok:
        return False, f"MySQL provisioning failed: {msg}"

    # Record in PostgreSQL
    record = ClientDatabase(
        user_id=user_id,
        db_name=db_name,
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
        # Rollback MySQL provisioning
        MySQLService.deprovision_database(db_name, db_user)
        return False, f"Database error: {str(e)}"


def delete_database(db_name: str) -> tuple[bool, str]:
    """Delete a client MySQL database from both MySQL and panel DB."""
    record = ClientDatabase.query.filter_by(db_name=db_name).first()
    if not record:
        return False, f"Database '{db_name}' not found in panel."

    db_user = record.db_user

    # Deprovision from MySQL
    ok, msg = MySQLService.deprovision_database(db_name, db_user)
    if not ok:
        logger.warning(f"MySQL deprovision warning for {db_name}: {msg}")

    # Remove from PostgreSQL
    try:
        db.session.delete(record)
        db.session.commit()
        logger.info(f"Database deleted: {db_name}")
        return True, f"Database '{db_name}' and user '{db_user}' removed."
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


def get_databases_for_user(user_id: int) -> list[ClientDatabase]:
    """Get all databases belonging to a user."""
    return ClientDatabase.query.filter_by(user_id=user_id).order_by(ClientDatabase.created_at.desc()).all()


def get_all_databases() -> list[ClientDatabase]:
    """Get all databases (admin view)."""
    return ClientDatabase.query.order_by(ClientDatabase.created_at.desc()).all()


def get_database_by_name(db_name: str) -> ClientDatabase:
    """Get a database record by name."""
    return ClientDatabase.query.filter_by(db_name=db_name).first()
