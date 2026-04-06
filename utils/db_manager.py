import pymysql
import os
from config import Config

class DBManager:
    @staticmethod
    def _get_connection(db=None):
        """Get MySQL connection using root credentials"""
        try:
            return pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=db,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    @classmethod
    def init_db(cls):
        """Initialize the panel_db and tables natively in MySQL"""
        conn = cls._get_connection()
        if not conn:
            print("Failed to connect to MySQL to initialize DB.")
            return

        try:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.PANEL_DB_NAME}`;")
                # We do not use parameterized generic DB names here as they are structural schema.
            conn.commit()
        except Exception as e:
            print(f"Error creating panel_db: {e}")
        finally:
            conn.close()

        # Reconnect to panel_db
        conn = cls._get_connection(db=Config.PANEL_DB_NAME)
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role ENUM('admin', 'client') DEFAULT 'client',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_databases (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        db_name VARCHAR(64) UNIQUE NOT NULL,
                        db_user VARCHAR(32) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                ''')
            conn.commit()
        except Exception as e:
            print(f"Error creating panel_db tables: {e}")
        finally:
            if conn: conn.close()

    @classmethod
    def get_all_databases(cls):
        conn = cls._get_connection(db=Config.PANEL_DB_NAME)
        if not conn: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ud.*, u.username as owner FROM user_databases ud JOIN users u ON ud.user_id = u.id")
                return cursor.fetchall()
        finally:
            conn.close()
            
    @classmethod
    def get_user_databases(cls, user_id):
        conn = cls._get_connection(db=Config.PANEL_DB_NAME)
        if not conn: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM user_databases WHERE user_id = %s", (user_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    @classmethod
    def create_database(cls, user_id, db_name, db_user, password):
        """Creates an explicit database and user with grants scoped to localhost"""
        conn = cls._get_connection()
        if not conn:
            return False, "Failed to connect to MySQL", None, None

        # Sanitize names loosely (prevent extreme characters)
        if not db_name.replace('_', '').isalnum():
             return False, "Invalid DB name format", None, None
        if not db_user.replace('_', '').isalnum():
             return False, "Invalid DB user format", None, None
        
        try:
            with conn.cursor() as cursor:
                # 1. Create DB
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                
                # 2. Setup user explicitly on localhost ONLY (no remote %)
                host = 'localhost'
                safe_pwd = conn.escape_string(password)
                
                # It is safer and more reliable to format DDL explicitly.
                try:
                    # Try default modern MYSQL syntax
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'{host}' IDENTIFIED BY '{safe_pwd}';")
                except Exception as e:
                    # Fallback for strict native password plugins
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'{host}' IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';")
                
                try:
                    cursor.execute(f"ALTER USER '{db_user}'@'{host}' IDENTIFIED BY '{safe_pwd}';")
                except Exception:
                    cursor.execute(f"ALTER USER '{db_user}'@'{host}' IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';")
                    
                # 3. Explicit isolation scope
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'{host}';")
                
                # We specifically do not grant *.*
                cursor.execute("FLUSH PRIVILEGES;")
                
            conn.commit()
            
            # Map in panel DB
            panel_conn = cls._get_connection(db=Config.PANEL_DB_NAME)
            try:
                with panel_conn.cursor() as p_cursor:
                    p_cursor.execute("INSERT INTO user_databases (user_id, db_name, db_user) VALUES (%s, %s, %s)", 
                                     (user_id, db_name, db_user))
                panel_conn.commit()
            finally:
                if panel_conn: panel_conn.close()
                
            return True, f"Database {db_name} and User {db_user} created", db_name, db_user
        except Exception as e:
            return False, f"MySQL Error: {str(e)}", None, None
        finally:
            if conn: conn.close()

    @classmethod
    def delete_database(cls, db_name, db_user):
        conn = cls._get_connection()
        if not conn:
            return False, "Connection failed"
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
                cursor.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost';")
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            
            # Remove mapping
            panel_conn = cls._get_connection(db=Config.PANEL_DB_NAME)
            try:
                with panel_conn.cursor() as p_cursor:
                    p_cursor.execute("DELETE FROM user_databases WHERE db_name=%s", (db_name,))
                panel_conn.commit()
            finally:
                if panel_conn: panel_conn.close()
                
            return True, "Deleted DB and User securely"
        except Exception as e:
            return False, str(e)
        finally:
            if conn: conn.close()

    @classmethod
    def assign_user_to_db(cls, db_name, db_user, password):
        # Update user's password/grants
        conn = cls._get_connection()
        if not conn:
             return False, "Connection failed"
             
        try:
            with conn.cursor() as cursor:
                host = 'localhost'
                safe_pwd = conn.escape_string(password)
                
                try:
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'{host}' IDENTIFIED BY '{safe_pwd}';")
                except Exception:
                    cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'{host}' IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';")
                    
                try:
                    cursor.execute(f"ALTER USER '{db_user}'@'{host}' IDENTIFIED BY '{safe_pwd}';")
                except Exception:
                    cursor.execute(f"ALTER USER '{db_user}'@'{host}' IDENTIFIED WITH mysql_native_password BY '{safe_pwd}';")
                    
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'{host}';")
                cursor.execute("FLUSH PRIVILEGES;")
            conn.commit()
            
            panel_conn = cls._get_connection(db=Config.PANEL_DB_NAME)
            try:
                with panel_conn.cursor() as p_cursor:
                    p_cursor.execute("UPDATE user_databases SET db_user=%s WHERE db_name=%s", (db_user, db_name))
                panel_conn.commit()
            finally:
                if panel_conn: panel_conn.close()
                
            return True, f"Updated password/grants for {db_user} on {db_name}"
        except Exception as e:
            return False, str(e)
        finally:
            if conn: conn.close()
