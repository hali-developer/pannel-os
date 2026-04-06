"""
VPS Panel — FTP Schemas
"""
from app.core.security import validate_ftp_username, validate_password


def validate_create_ftp(data: dict) -> tuple[bool, str]:
    """Validate FTP account creation input."""
    ftp_username = (data.get('ftp_username') or '').strip()
    password = data.get('password') or ''

    ok, msg = validate_ftp_username(ftp_username)
    if not ok:
        return False, msg

    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    return True, ""


def validate_change_password(data: dict) -> tuple[bool, str]:
    """Validate FTP password change input."""
    password = data.get('password') or ''
    ok, msg = validate_password(password)
    return ok, msg
