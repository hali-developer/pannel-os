import sys
import os

# Add the app directory to sys.path to import models
sys.path.insert(0, '/var/www/panel')

from app import create_app
from app.extensions import db
from app.models.ftp_account import FTPAccount
from app.services.ftp_service import FTPSystemService

def sync_users():
    app = create_app('production')
    with app.app_context():
        accounts = FTPAccount.query.all()
        print(f"Found {len(accounts)} FTP accounts to sync...")
        
        for acc in accounts:
            print(f"Syncing user: {acc.username}")
            
            # Since we don't have the plain text password for existing accounts 
            # (they are hashed in the DB), we have two options:
            # 1. Ask the user to change the password in the panel to sync it to the OS.
            # 2. Try to create the user without a password (locked) and they must use keys.
            
            # For this script, we'll try to create the system user. 
            # Note: They won't be able to login with SSH until a password is set via the Panel.
            
            home_dir = acc.home_directory
            ok, msg = FTPSystemService.create_system_user(acc.username, "TEMPORARY_LOCKED_PWD", home_dir)
            
            if ok:
                print(f"  ✅ System user '{acc.username}' created.")
                print(f"  ⚠  Please go to the Panel and change the password for '{acc.username}' to enable SSH login.")
            else:
                if "already exists" in msg:
                    print(f"  ℹ  System user '{acc.username}' already exists.")
                else:
                    print(f"  ❌ Error: {msg}")

if __name__ == "__main__":
    sync_users()
