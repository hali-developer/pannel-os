"""
VPS Panel — DB User Schemas

Input validation for database user management endpoints.
"""
from app.core.security import validate_db_user, validate_password, validate_db_name


def validate_create_db_user(data: dict) -> tuple[bool, str]:
    """Validate DB user creation input."""
    db_username = (data.get('db_username') or '').strip()
    password = data.get('password') or ''

    ok, msg = validate_db_user(db_username)
    if not ok:
        return False, msg

    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    return True, ""


def validate_update_db_user_password(data: dict) -> tuple[bool, str]:
    """Validate DB user password update input."""
    db_username = (data.get('db_username') or '').strip()
    password = data.get('password') or ''

    if not db_username:
        return False, "DB username is required."

    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    return True, ""


def validate_grant_permission(data: dict) -> tuple[bool, str]:
    """Validate DB user permission grant input."""
    db_username = (data.get('db_username') or '').strip()
    db_name = (data.get('db_name') or '').strip()

    if not db_username:
        return False, "DB username is required."
    if not db_name:
        return False, "Database name is required."

    return True, ""
