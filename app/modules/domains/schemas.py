"""
VPS Panel — Domain Schemas
"""
from app.core.security import validate_domain


def validate_add_domain(data: dict) -> tuple[bool, str]:
    """Validate domain addition input."""
    domain_name = (data.get('domain_name') or '').strip().lower()
    if not domain_name:
        return False, "Domain name is required."

    ok, msg = validate_domain(domain_name)
    if not ok:
        return False, msg

    return True, ""
