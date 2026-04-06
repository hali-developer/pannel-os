"""
VPS Panel — User Schemas
"""
from app.core.security import validate_username, validate_password


def validate_create_user(data: dict) -> tuple[bool, str]:
    """Validate user creation input."""
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    role = data.get('role', 'client')

    ok, msg = validate_username(username)
    if not ok:
        return False, msg

    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    if role not in ('admin', 'client'):
        return False, "Role must be 'admin' or 'client'."

    return True, ""
