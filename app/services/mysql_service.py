"""
VPS Panel — MySQL Administration Service

Low-level MySQL operations for provisioning client databases and users.
Uses PyMySQL with parameterized DDL where possible, and strict input
validation for identifiers that cannot be parameterized.
"""
import pymysql
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class MySQLService:
    """Direct MySQL admin operations via the panel's admin account."""

    @staticmethod
    def _get_admin_connection(database: str = None) -> pymysql.Connection:
        """Get a connection using the panel's MySQL admin credentials."""
        try:
            return pymysql.connect(
                host=current_app.config['MYSQL_HOST'],
                port=current_app.config['MYSQL_PORT'],
                user=current_app.config['MYSQL_ADMIN_USER'],
                password=current_app.config['MYSQL_ADMIN_PASSWORD'],
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
            )
        except pymysql.Error as e:
            logger.error(f"MySQL connection failed: {e}")
            raise ConnectionError(f"Cannot connect to MySQL: {e}")

    @classmethod
    def create_database(cls, db_name: str) -> tuple[bool, str]:
        """Create a MySQL database with UTF8MB4 encoding."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # db_name is pre-validated by security.validate_db_name()
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            conn.commit()
            logger.info(f"Created MySQL database: {db_name}")
            return True, f"Database '{db_name}' created."
        except pymysql.Error as e:
            logger.error(f"Failed to create database {db_name}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def drop_database(cls, db_name: str) -> tuple[bool, str]:
        """Drop a MySQL database."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
            conn.commit()
            logger.info(f"Dropped MySQL database: {db_name}")
            return True, f"Database '{db_name}' dropped."
        except pymysql.Error as e:
            logger.error(f"Failed to drop database {db_name}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def create_user(cls, username: str, password: str, host: str = 'localhost') -> tuple[bool, str]:
        """Create a MySQL user, or update their password if they exist."""
        conn = cls._get_admin_connection()
        try:
            safe_pwd = conn.escape_string(password)
            with conn.cursor() as cursor:
                # Create user (idempotent)
                try:
                    cursor.execute(
                        f"CREATE USER IF NOT EXISTS '{username}'@'{host}' "
                        f"IDENTIFIED BY '{safe_pwd}';"
                    )
                except pymysql.Error:
                    cursor.execute(
                        f"CREATE USER IF NOT EXISTS '{username}'@'{host}' "
                        f"IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';"
                    )

                # Ensure password is set correctly
                try:
                    cursor.execute(
                        f"ALTER USER '{username}'@'{host}' IDENTIFIED BY '{safe_pwd}';"
                    )
                except pymysql.Error:
                    cursor.execute(
                        f"ALTER USER '{username}'@'{host}' "
                        f"IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';"
                    )

            conn.commit()
            logger.info(f"Created/updated MySQL user: {username}@{host}")
            return True, f"User '{username}'@'{host}' created."
        except pymysql.Error as e:
            logger.error(f"Failed to create MySQL user {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def drop_user(cls, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Drop a MySQL user."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP USER IF EXISTS '{username}'@'{host}';")
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            logger.info(f"Dropped MySQL user: {username}@{host}")
            return True, f"User '{username}'@'{host}' dropped."
        except pymysql.Error as e:
            logger.error(f"Failed to drop MySQL user {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def grant_privileges(cls, db_name: str, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Grant ALL privileges on a specific database to a user."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{username}'@'{host}';"
                )
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            logger.info(f"Granted privileges on {db_name} to {username}@{host}")
            return True, f"Privileges granted on '{db_name}' to '{username}'@'{host}'."
        except pymysql.Error as e:
            logger.error(f"Failed to grant privileges: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def revoke_privileges(cls, db_name: str, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Revoke all privileges on a specific database from a user."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"REVOKE ALL PRIVILEGES ON `{db_name}`.* FROM '{username}'@'{host}';"
                )
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            logger.info(f"Revoked privileges on {db_name} from {username}@{host}")
            return True, f"Privileges revoked."
        except pymysql.Error as e:
            logger.error(f"Failed to revoke privileges: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def provision_database(cls, db_name: str, db_user: str, password: str) -> tuple[bool, str]:
        """
        Full provisioning: create database + user + grant.
        This is the high-level method used by the database module.
        """
        # Step 1: Create database
        ok, msg = cls.create_database(db_name)
        if not ok:
            return False, f"DB creation failed: {msg}"

        # Step 2: Create user
        ok, msg = cls.create_user(db_user, password)
        if not ok:
            # Rollback: drop the database we just created
            cls.drop_database(db_name)
            return False, f"User creation failed: {msg}"

        # Step 3: Grant privileges (isolated to this database only)
        ok, msg = cls.grant_privileges(db_name, db_user)
        if not ok:
            cls.drop_database(db_name)
            cls.drop_user(db_user)
            return False, f"Grant failed: {msg}"

        return True, f"Database '{db_name}' provisioned with user '{db_user}'."

    @classmethod
    def deprovision_database(cls, db_name: str, db_user: str) -> tuple[bool, str]:
        """Full cleanup: drop database + user."""
        errors = []

        ok, msg = cls.drop_database(db_name)
        if not ok:
            errors.append(f"Drop DB: {msg}")

        ok, msg = cls.drop_user(db_user)
        if not ok:
            errors.append(f"Drop user: {msg}")

        if errors:
            return False, "; ".join(errors)
        return True, f"Database '{db_name}' and user '{db_user}' removed."

    @classmethod
    def test_connection(cls) -> tuple[bool, str]:
        """Test if the MySQL admin connection is working."""
        try:
            conn = cls._get_admin_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
            conn.close()
            return True, "MySQL connection successful."
        except Exception as e:
            return False, str(e)
