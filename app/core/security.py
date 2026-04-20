"""
VPS Panel — Input Validation & Security Utilities

Centralizes all input sanitization to prevent injection attacks,
path traversal, and invalid system identifiers.
"""
import re
import os
import secrets
import string


# ── Validation Patterns ──
USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{2,31}$')
DOMAIN_PATTERN = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)
DB_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,63}$')
DB_USER_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,31}$')
FTP_USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{2,31}$')

# Characters that must NEVER appear in shell arguments
SHELL_DANGEROUS = set(';&|`$(){}[]!#~\'"\\<>?\n\r\x00')


def validate_username(name: str) -> tuple[bool, str]:
    """Validate a panel username. Returns (is_valid, error_message)."""
    if not name:
        return False, "Username is required."
    if not USERNAME_PATTERN.match(name):
        return False, "Username must start with a letter, contain only letters/numbers/underscores, and be 3-32 characters."
    # Forbid system usernames
    forbidden = {'root', 'admin', 'www-data', 'nginx', 'PostgreSQL', 'postgres',
                 'nobody', 'daemon', 'bin', 'sys', 'mail', 'ftp'}
    if name.lower() in forbidden:
        return False, f"Username '{name}' is reserved."
    return True, ""


def validate_domain(domain: str) -> tuple[bool, str]:
    """Validate a fully qualified domain name."""
    if not domain:
        return False, "Domain name is required."
    if len(domain) > 253:
        return False, "Domain name is too long (max 253 characters)."
    if not DOMAIN_PATTERN.match(domain):
        return False, "Invalid domain name format."
    return True, ""


def validate_db_name(name: str) -> tuple[bool, str]:
    """Validate a PostgreSQL database name."""
    if not name:
        return False, "Database name is required."
    if not DB_NAME_PATTERN.match(name):
        return False, "Database name must start with a letter and contain only letters/numbers/underscores (max 64 chars)."
    # Forbid system databases
    forbidden = {'PostgreSQL', 'information_schema', 'performance_schema', 'sys',
                 'pgadmin4', 'pgadmin', 'panel_db'}
    if name.lower() in forbidden:
        return False, f"Database name '{name}' is reserved."
    return True, ""


def validate_db_user(name: str) -> tuple[bool, str]:
    """Validate a PostgreSQL user name."""
    if not name:
        return False, "DB username is required."
    if not DB_USER_PATTERN.match(name):
        return False, "DB username must start with a letter and contain only letters/numbers/underscores (max 32 chars)."
    return True, ""


def validate_ftp_username(name: str) -> tuple[bool, str]:
    """Validate an FTP username."""
    if not name:
        return False, "FTP username is required."
    if not FTP_USERNAME_PATTERN.match(name):
        return False, "FTP username must start with a letter, contain only letters/numbers/underscores, and be 3-32 characters."
    return True, ""


def validate_password(password: str, min_length: int = 8) -> tuple[bool, str]:
    """Validate password strength."""
    if not password:
        return False, "Password is required."
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters."
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)."
    # Check for shell-dangerous characters that could cause issues
    if any(c == '\x00' for c in password):
        return False, "Password contains invalid characters."
    return True, ""


def sanitize_path(path: str, base_dir: str) -> tuple[bool, str]:
    """
    Ensure a path stays within the base directory.
    Prevents directory traversal attacks.
    Returns (is_safe, resolved_path).
    """
    try:
        base = os.path.realpath(base_dir)
        target = os.path.realpath(os.path.join(base_dir, path))
        if target.startswith(base + os.sep) or target == base:
            return True, target
        return False, "Path traversal detected."
    except (ValueError, OSError):
        return False, "Invalid path."


def check_shell_safety(value: str) -> tuple[bool, str]:
    """Check that a string is safe to use near shell commands."""
    if not value:
        return False, "Value is required."
    dangerous_found = SHELL_DANGEROUS.intersection(set(value))
    if dangerous_found:
        return False, f"Value contains dangerous characters: {dangerous_found}"
    return True, ""


def generate_secure_password(length: int = 24) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    # Guarantee at least one of each type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*'),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    # Shuffle to randomize position of guaranteed chars
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return ''.join(password_list)
