import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def test_conn():
    user = os.getenv('PANEL_DB_USER')
    password = os.getenv('PANEL_DB_PASSWORD')
    host = os.getenv('PANEL_DB_HOST')
    port = os.getenv('PANEL_DB_PORT')
    db = os.getenv('PANEL_DB_NAME')
    
    print(f"Testing connection for {user}@{host}:{port}/{db}...")
    
    try:
        conn = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=db
        )
        print("✅ Connection successful!")
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_conn()
