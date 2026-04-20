import mysql.connector
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class MySQLService:
    """Direct MySQL admin operations via the panel's root account."""

    @staticmethod
    def _get_admin_connection():
        """Get a connection using the panel's MySQL root credentials."""
        return mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_ADMIN_USER'],
            password=current_app.config['MYSQL_ADMIN_PASSWORD'],
            port=current_app.config['MYSQL_PORT']
        )

    @classmethod
    def provision_database(cls, db_name, db_user, password):
        """Create MySQL database + user + grant privileges."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            
            # 1. Create Database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            
            # 2. Create User and Grant Privileges
            # We use 'localhost' as default host
            cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{password}';")
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';")
            cursor.execute("FLUSH PRIVILEGES;")
            
            conn.close()
            return True, f"MySQL database '{db_name}' provisioned successfully."
        except mysql.connector.Error as e:
            logger.error(f"MySQL provisioning failed: {e}")
            return False, str(e)

    @classmethod
    def create_user(cls, db_user, password):
        """Create a MySQL user only."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{password}';")
            cursor.execute("FLUSH PRIVILEGES;")
            conn.close()
            return True, f"MySQL user '{db_user}' created."
        except mysql.connector.Error as e:
            logger.error(f"MySQL user creation failed: {e}")
            return False, str(e)

    @classmethod
    def drop_user(cls, db_user):
        """Drop a MySQL user."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            cursor.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost';")
            cursor.execute("FLUSH PRIVILEGES;")
            conn.close()
            return True, f"MySQL user '{db_user}' removed."
        except mysql.connector.Error as e:
            logger.error(f"MySQL drop user failed: {e}")
            return False, str(e)

    @classmethod
    def deprovision_database(cls, db_name, db_user):
        """Drop MySQL database + user."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
            cursor.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost';")
            cursor.execute("FLUSH PRIVILEGES;")
            
            conn.close()
            return True, f"MySQL database '{db_name}' and user '{db_user}' removed."
        except mysql.connector.Error as e:
            logger.error(f"MySQL deprovisioning failed: {e}")
            return False, str(e)

    @classmethod
    def update_user_password(cls, db_user, new_password):
        """Update MySQL user password."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            
            cursor.execute(f"ALTER USER '{db_user}'@'localhost' IDENTIFIED BY '{new_password}';")
            cursor.execute("FLUSH PRIVILEGES;")
            
            conn.close()
            return True, f"MySQL password updated for '{db_user}'."
        except mysql.connector.Error as e:
            logger.error(f"MySQL password update failed: {e}")
            return False, str(e)

    @classmethod
    def grant_privileges(cls, db_name, db_user):
        """Grant a user access to a specific database."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';")
            cursor.execute("FLUSH PRIVILEGES;")
            conn.close()
            return True, f"Privileges granted on `{db_name}` to `{db_user}`."
        except mysql.connector.Error as e:
            logger.error(f"MySQL grant failed: {e}")
            return False, str(e)

    @classmethod
    def revoke_privileges(cls, db_name, db_user):
        """Revoke a user's access from a specific database."""
        try:
            conn = cls._get_admin_connection()
            cursor = conn.cursor()
            cursor.execute(f"REVOKE ALL PRIVILEGES ON `{db_name}`.* FROM '{db_user}'@'localhost';")
            cursor.execute("FLUSH PRIVILEGES;")
            conn.close()
            return True, f"Privileges revoked on `{db_name}` from `{db_user}`."
        except mysql.connector.Error as e:
            logger.error(f"MySQL revoke failed: {e}")
            return False, str(e)
