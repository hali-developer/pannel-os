"""
VPS Panel — Auth Schemas

Input validation for authentication endpoints.
"""


def validate_login(data: dict) -> tuple[bool, str]:
    """Validate login form/JSON data."""
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username:
        return False, "Username is required."
    if len(username) > 50:
        return False, "Username is too long."
    if not password:
        return False, "Password is required."
    if len(password) > 128:
        return False, "Password is too long."
    return True, ""
