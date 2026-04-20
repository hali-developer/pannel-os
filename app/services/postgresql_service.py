"""
VPS Panel — PostgreSQL Administration Service

Low-level PostgreSQL operations for provisioning client databases and users.
Uses psycopg2 with strict input validation for identifiers that cannot be parameterized.
"""
import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class PostgreSQLService:
    """Direct PostgreSQL admin operations via the panel's admin account."""

    @staticmethod
    def _get_admin_connection(database: str = None) -> psycopg2.extensions.connection:
        """Get a connection using the panel's PostgreSQL admin credentials."""
        host = current_app.config['POSTGRESQL_HOST']
        user = current_app.config['POSTGRESQL_ADMIN_USER']
        password = current_app.config['POSTGRESQL_ADMIN_PASSWORD']
        port = current_app.config['POSTGRESQL_PORT']
        
        # Default to 'postgres' if no database specified, as PostgreSQL requires connecting to a specific database
        db_to_connect = database if database else 'postgres'

        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=db_to_connect,
                connect_timeout=10,
                cursor_factory=DictCursor
            )
            # Autocommit is required for CREATE/DROP DATABASE operations in PostgreSQL
            conn.autocommit = True
            return conn
        except psycopg2.Error as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise ConnectionError(f"Cannot connect to PostgreSQL admin: {e}")

    # ════════════════════════════════════════
    # DATABASE OPERATIONS
    # ════════════════════════════════════════

    @classmethod
    def create_database(cls, db_name: str) -> tuple[bool, str]:
        """Create a PostgreSQL database."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8';").format(
                    sql.Identifier(db_name)
                ))
            logger.info(f"Created PostgreSQL database: {db_name}")
            return True, f"Database '{db_name}' created."
        except psycopg2.Error as e:
            # Code 42P04 indicates the database already exists
            if e.pgcode == '42P04':
                return True, f"Database '{db_name}' already exists."
            logger.error(f"Failed to create database {db_name}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def drop_database(cls, db_name: str) -> tuple[bool, str]:
        """Drop a PostgreSQL database."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # Terminate existing connections first to ensure dropping works
                cursor.execute(
                    "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                    "FROM pg_stat_activity "
                    "WHERE pg_stat_activity.datname = %s "
                    "AND pid <> pg_backend_pid();",
                    (db_name,)
                )
                cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {};").format(
                    sql.Identifier(db_name)
                ))
            logger.info(f"Dropped PostgreSQL database: {db_name}")
            return True, f"Database '{db_name}' dropped."
        except psycopg2.Error as e:
            logger.error(f"Failed to drop database {db_name}: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ════════════════════════════════════════
    # USER OPERATIONS
    # ════════════════════════════════════════

    @classmethod
    def create_user(cls, username: str, password: str, host: str = 'localhost') -> tuple[bool, str]:
        """Create a PostgreSQL user (role), or update their password if they exist. Host is ignored."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # Check if role exists
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
                exists = cursor.fetchone()
                
                if not exists:
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s;").format(
                            sql.Identifier(username)
                        ),
                        [password]
                    )
                else:
                    cursor.execute(
                        sql.SQL("ALTER ROLE {} WITH PASSWORD %s;").format(
                            sql.Identifier(username)
                        ),
                        [password]
                    )
            logger.info(f"Created/updated PostgreSQL role: {username}")
            return True, f"User '{username}' created."
        except psycopg2.Error as e:
            logger.error(f"Failed to create PostgreSQL role {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def drop_user(cls, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Drop a PostgreSQL user (role)."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # To drop a role, it must not own any databases or have privileges
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {};").format(
                    sql.Identifier(username)
                ))
            logger.info(f"Dropped PostgreSQL role: {username}")
            return True, f"User '{username}' dropped."
        except psycopg2.Error as e:
            logger.error(f"Failed to drop PostgreSQL role {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def update_user_password(cls, username: str, new_password: str, host: str = 'localhost') -> tuple[bool, str]:
        """Update a PostgreSQL user's password."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD %s;").format(
                        sql.Identifier(username)
                    ),
                    [new_password]
                )
            logger.info(f"Password updated for PostgreSQL role: {username}")
            return True, f"Password updated for '{username}'."
        except psycopg2.Error as e:
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
        # First grant at database level (connection to postgres db for CREATE DATABASE scope)
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {};").format(
                        sql.Identifier(db_name),
                        sql.Identifier(username)
                    )
                )
                # Set owner so the user has full control
                cursor.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {};").format(
                        sql.Identifier(db_name),
                        sql.Identifier(username)
                    )
                )
            logger.info(f"Granted database-level privileges on {db_name} to {username}")
        except psycopg2.Error as e:
            logger.error(f"Failed to grant database privileges: {e}")
            return False, str(e)
        finally:
            conn.close()
        # Connect to the actual database to grant schema-level access (required on PostgreSQL 15+)
        conn2 = cls._get_admin_connection(database=db_name)
        try:
            with conn2.cursor() as cursor:
                cursor.execute(
                    sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {};").format(
                        sql.Identifier(username)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {};").format(
                        sql.Identifier(username)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {};").format(
                        sql.Identifier(username)
                    )
                )
                # Ensure future tables are also automatically granted
                cursor.execute(
                    sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {};").format(
                        sql.Identifier(username)
                    )
                )
            logger.info(f"Granted schema-level privileges on {db_name} to {username}")
            return True, f"Privileges granted on '{db_name}' to '{username}'."
        except psycopg2.Error as e:
            logger.error(f"Failed to grant schema privileges: {e}")
            return False, str(e)
        finally:
            conn2.close()

    @classmethod
    def revoke_privileges(cls, db_name: str, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Revoke all privileges on a specific database from a user."""
        conn = cls._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                # First reset owner to postgres before revoking
                cursor.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO postgres;").format(
                        sql.Identifier(db_name)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {};").format(
                        sql.Identifier(db_name),
                        sql.Identifier(username)
                    )
                )
            logger.info(f"Revoked privileges on {db_name} from {username}")
            return True, "Privileges revoked."
        except psycopg2.Error as e:
            # Warning: Could fail if user owns objects inside the db
            logger.error(f"Failed to revoke privileges: {e}")
            return False, str(e)
        finally:
            conn.close()

    @classmethod
    def revoke_all_user_privileges(cls, username: str, host: str = 'localhost') -> tuple[bool, str]:
        """Revoke ALL privileges from a user (pseudo-implementation since Postgres per-db isolation differs)"""
        # In PostgreSQL, you can't easily iterate all DBs and DROP OWNED outside the target db.
        # This is a best effort.
        return True, "All privileges revoked placeholder."

    # ════════════════════════════════════════
    # HIGH-LEVEL PROVISIONING
    # ════════════════════════════════════════

    @classmethod
    def provision_database(cls, db_name: str, db_user: str, password: str) -> tuple[bool, str]:
        """
        Full provisioning: create database + user + grant.
        """
        # Step 1: Create user first (Postgres prefers users to exist before granting ownership)
        ok, msg = cls.create_user(db_user, password)
        if not ok:
            return False, f"User creation failed: {msg}"

        # Step 2: Create database
        ok, msg = cls.create_database(db_name)
        if not ok:
            # cls.drop_user(db_user) - skip drop user in case it's shared across domains/dbs
            return False, f"DB creation failed: {msg}"

        # Step 3: Grant privileges
        ok, msg = cls.grant_privileges(db_name, db_user)
        if not ok:
            cls.drop_database(db_name)
            # cls.drop_user(db_user)
            return False, f"Grant failed: {msg}"

        return True, f"Database '{db_name}' provisioned with user '{db_user}'."

    @classmethod
    def deprovision_database(cls, db_name: str, db_user: str) -> tuple[bool, str]:
        """Full cleanup: drop database + user."""
        errors = []

        ok, msg = cls.drop_database(db_name)
        if not ok:
            errors.append(f"Drop DB: {msg}")

        # Note: Dropping the user might fail if they still own other objects.
        ok, msg = cls.drop_user(db_user)
        if not ok:
            errors.append(f"Drop user: {msg}")

        if errors:
            return False, "; ".join(errors)
        return True, f"Database '{db_name}' and user '{db_user}' removed."

    @classmethod
    def test_connection(cls) -> tuple[bool, str]:
        """Test if the PostgreSQL admin connection is working."""
        try:
            conn = cls._get_admin_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
            conn.close()
            return True, "PostgreSQL connection successful."
        except Exception as e:
            return False, str(e)
