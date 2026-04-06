"""
VPS Panel — Auth Services

JWT token management and credential verification.
"""
import logging
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str):
    """
    Verify credentials and return the user if valid.
    Returns None if invalid.
    """
    user = User.query.filter_by(username=username, is_active=True).first()
    if user and check_password_hash(user.password_hash, password):
        logger.info(f"Authenticated user: {username}")
        return user
    logger.warning(f"Failed login attempt for: {username}")
    return None


def create_tokens(user: User) -> dict:
    """Generate JWT access and refresh tokens for a user."""
    additional_claims = {
        'role': user.role,
        'username': user.username,
    }
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims=additional_claims,
    )
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    }
