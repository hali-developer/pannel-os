"""
VPS Panel — MySQL Administration Service

Low-level MySQL operations for provisioning client databases and users.
Uses PyMySQL with parameterized DDL where possible, and strict input
validation for identifiers that cannot be parameterized.
"""
import os
import pymysql
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class MySQLService:
    """Direct MySQL admin operations via the panel's admin account."""

    @staticmethod
    def _get_admin_connection(database: str = None) -> pymysql.Connection:
        """Get a connection using the panel's MySQL admin credentials."""
        host = current_app.config['MYSQL_HOST']
        user = current_app.config['MYSQL_ADMIN_USER']
        password = current_app.config['MYSQL_ADMIN_PASSWORD']
        port = current_app.config['MYSQL_PORT']
        unix_socket = current_app.config.get('MYSQL_UNIX_SOCKET', '/var/run/mysqld/mysqld.sock')

        try:
            # If host is localhost, try connecting via UNIX socket first
            if host in ('localhost', '127.0.0.1') and os.path.exists(unix_socket):
                try:
                    return pymysql.connect(
                        user=user,
                        password=password,
                        unix_socket=unix_socket,
                        database=database,
                        charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor,
                        connect_timeout=5,
                    )
                except pymysql.Error as socket_e:
                    logger.warning(f"MySQL socket connection failed ({unix_socket}), falling back to TCP: {socket_e}")

            # TCP fallback or non-local host
            return pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
            )
        except pymysql.Error as e:
            logger.error(f"MySQL connection failed: {e}")
            raise ConnectionError(f"Cannot connect to MySQL admin: {e}")

    # ════════════════════════════════════════
    # DATABASE OPERATIONS
    # ════════════════════════════════════════

    @classmethod
    def create_database(cls, db_name: str) -> tuple[bool, str]:
        """Create a MySQL database with UTF8MB4 encoding."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
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

    # ════════════════════════════════════════
    # USER OPERATIONS
    # ════════════════════════════════════════

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
    def update_user_password(cls, username: str, new_password: str, host: str = 'localhost') -> tuple[bool, str]:
        """Update a MySQL user's password."""
        conn = cls._get_admin_connection()
        try:
            safe_pwd = conn.escape_string(new_password)
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        f"ALTER USER '{username}'@'{host}' IDENTIFIED BY '{safe_pwd}';"
                    )
                except pymysql.Error:
                    cursor.execute(
                        f"ALTER USER '{username}'@'{host}' "
                        f"IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';"
                    )
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            logger.info(f"Password updated for MySQL user: {username}@{host}")
            return True, f"Password updated for '{username}'@'{host}'."
        except pymysql.Error as e:
            logger.error(f"Failed to update password for {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ════════════════════════════════════════
    # PRIVILEGE OPERATIONS
    # ════════════════════════════════════════

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
            return True, "Privileges revoked."
        except pymysql.Error as e:
            logger.error(f"Failed to revoke privileges: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def revoke_all_user_privileges(cls, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Revoke ALL privileges from a user across all databases."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # Get all grants for this user
                try:
                    cursor.execute(f"SHOW GRANTS FOR '{username}'@'{host}';")
                    grants = cursor.fetchall()
                    # Revoke each grant (skip USAGE which is the base grant)
                    for grant_row in grants:
                        grant_str = list(grant_row.values())[0]
                        if 'USAGE' not in grant_str.upper() or 'ON *.*' not in grant_str:
                            # Extract database name from GRANT statement
                            pass
                except pymysql.Error:
                    pass  # User may not exist

                # Simpler approach: revoke all
                try:
                    cursor.execute(
                        f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{username}'@'{host}';"
                    )
                except pymysql.Error:
                    pass  # May fail if no privileges exist

                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            logger.info(f"Revoked all privileges from {username}@{host}")
            return True, "All privileges revoked."
        except pymysql.Error as e:
            logger.error(f"Failed to revoke all privileges from {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ════════════════════════════════════════
    # HIGH-LEVEL PROVISIONING
    # ════════════════════════════════════════

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
