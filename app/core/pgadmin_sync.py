"""
VPS Panel — pgAdmin Sync (Replaced by Adminer)

pgAdmin has been replaced with Adminer for database management.
Users log in directly to Adminer using their DB credentials.
This module is kept as a no-op stub for backward compatibility.
"""
import logging

logger = logging.getLogger(__name__)


def sync_user_to_pgadmin(db_username: str, db_password: str) -> bool:
    """
    No-op stub. Previously synced users to pgAdmin.
    Now replaced by Adminer which uses credentials directly.
    """
    logger.debug(f"pgAdmin sync skipped (Adminer in use): {db_username}")
    return True
