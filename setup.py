import pymysql
import getpass
import os
import sys

# Ensure we can import from utils
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from config import Config

def configure_mysql():
    print("=== MySQL Database & Schema Automated Setup ===")
    print("We need an administrative MySQL account (usually 'root') to configure the secure Panel User infrastructure.\n")
    
    root_user = input("Enter administrative MySQL username [root]: ") or "root"
    root_pass = getpass.getpass(f"Enter password for {root_user}: ")

    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=root_user,
            password=root_pass,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        print("\n✅ Connected to MySQL successfully as an administrator.")
    except Exception as e:
        print(f"\n❌ Failed to connect: {e}")
        return

    try:
        with conn.cursor() as cursor:
            # 1. Provide the physical Panel User account
            print(f"⏳ Configuring internal panel user '{Config.MYSQL_USER}'...")
            
            cursor.execute(f"CREATE USER IF NOT EXISTS '{Config.MYSQL_USER}'@'localhost' IDENTIFIED BY '{Config.MYSQL_PASSWORD}';")
            
            # Backwards compatibility / strict auth forcing 
            try:
                cursor.execute(f"ALTER USER '{Config.MYSQL_USER}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{Config.MYSQL_PASSWORD}';")
            except:
                pass
            
            # 2. Grant Global Privileges
            # The panel user needs *.* access to act as a Control Panel (provisioning foreign databases and users).
            cursor.execute(f"GRANT ALL PRIVILEGES ON *.* TO '{Config.MYSQL_USER}'@'localhost' WITH GRANT OPTION;")
            
            # 3. Securely Bootstrap the central storage DB
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.PANEL_DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            
            cursor.execute("FLUSH PRIVILEGES;")
        conn.commit()
    except Exception as e:
        print(f"❌ Error configuring internal user/architecture: {e}")
        return

    # 4. Bind Central Schema Structure
    try:
        conn.select_db(Config.PANEL_DB_NAME)
        with conn.cursor() as cursor:
            print("⏳ Preparing Panel architecture schema...")
            
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
        print(f"✅ Local configuration complete!")
        print(f"-> Schema `{Config.PANEL_DB_NAME}` natively stored in MySQL.")
        print(f"-> You can now safely run app.py with {Config.MYSQL_USER}!")
    except Exception as e:
        print(f"❌ Error creating schema tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    configure_mysql()
