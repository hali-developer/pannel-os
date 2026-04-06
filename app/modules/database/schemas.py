"""
VPS Panel — Database Schemas
"""
from app.core.security import validate_db_name, validate_db_user, validate_password


def validate_create_db(data: dict) -> tuple[bool, str]:
    """Validate database creation input."""
    db_name = (data.get('db_name') or '').strip()
    db_user = (data.get('db_user') or '').strip()
    password = data.get('password') or ''

    ok, msg = validate_db_name(db_name)
    if not ok:
        return False, msg

    ok, msg = validate_db_user(db_user)
    if not ok:
        return False, msg

    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    return True, ""


def validate_delete_db(data: dict) -> tuple[bool, str]:
    """Validate database deletion input."""
    db_name = (data.get('db_name') or '').strip()
    if not db_name:
        return False, "Database name is required."
    return True, ""
