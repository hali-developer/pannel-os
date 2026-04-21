"""
VPS Panel — Mail Module Schemas
"""

def validate_add_mailbox(form):
    """Simple validation for mailbox creation."""
    email_user = form.get('email_user', '').strip()
    password = form.get('password', '')
    domain_id = form.get('domain_id')

    if not email_user:
        return False, "Email username is required (e.g., 'info')."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not domain_id:
        return False, "Domain selection is required."
    
    # Basic character check for username
    if not email_user.isalnum() and '.' not in email_user and '-' not in email_user:
        return False, "Invalid email username characters."

    return True, None
