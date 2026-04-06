import os
import sys
from werkzeug.security import generate_password_hash

# Ensure we can import from utils
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from config import Config
from db_manager import DBManager

def seed_data():
    print("Checking database initialization...")
    DBManager.init_db()
    
    conn = DBManager._get_connection(db=Config.PANEL_DB_NAME)
    if not conn:
        print("❌ Could not connect to MySQL. Ensure MySQL/MariaDB is running and Config credentials are correct.")
        return

    print("🌱 Seeding dummy client accounts...")
    clients = [
        {"username": "demo_client_a", "password": "password123"},
        {"username": "demo_client_b", "password": "password456"}
    ]
    
    try:
        with conn.cursor() as cursor:
            for client in clients:
                cursor.execute("SELECT id FROM users WHERE username=%s", (client['username'],))
                if not cursor.fetchone():
                    pwd_hash = generate_password_hash(client['password'])
                    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'client')", 
                                   (client['username'], pwd_hash))
                    print(f"  ✅ Created user: {client['username']} (password: {client['password']})")
                else:
                    print(f"  ℹ️ User already exists: {client['username']}")
        conn.commit()
    except Exception as e:
        print(f"❌ Error seeding users: {e}")
        conn.close()
        return
        
    print("\n🌱 Seeding dummy databases...")
    try:
        with conn.cursor() as cursor:
            for client in clients:
                cursor.execute("SELECT id FROM users WHERE username=%s", (client['username'],))
                user = cursor.fetchone()
                if user:
                    user_id = user['id']
                    db_name = f"{client['username']}_wp"
                    db_user = f"{client['username']}_usr"
                    db_pass = "secureDbPass!123"
                    
                    # Verify if DB holds mapping already
                    cursor.execute("SELECT id FROM user_databases WHERE db_name=%s", (db_name,))
                    if not cursor.fetchone():
                        print(f"  🔄 Provisioning DB '{db_name}' for '{client['username']}'...")
                        # This runs the actual GRANT statements on the MySQL server!
                        succ, msg, d_n, d_u = DBManager.create_database(user_id, db_name, db_user, db_pass)
                        if succ:
                            print(f"    ✅ Success: DB {db_name} and User {db_user} natively provisioned.")
                        else:
                            print(f"    ❌ Failed to create DB {db_name}: {msg}")
                    else:
                        print(f"  ℹ️ DB {db_name} already exists.")
    except Exception as e:
        print(f"❌ Error seeding databases: {e}")
    finally:
        conn.close()

    print("\n🎉 Seeding complete! Launch app.py and login to test.")

if __name__ == "__main__":
    seed_data()
