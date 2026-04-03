import subprocess
import platform
import os
import sqlite3
import tempfile
import pwd
import re

class FTPManager:
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'panel.db')

    # -------------------------
    # Helpers
    # -------------------------
    @classmethod
    def _init_db(cls):
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ftp_users (
                    username TEXT PRIMARY KEY,
                    domain_name TEXT,
                    home_dir TEXT
                )
            ''')

    @staticmethod
    def _is_linux():
        return platform.system() != "Windows"

    @staticmethod
    def _run_cmd(cmd, input_data=None):
        if platform.system() == "Windows":
            print(f"[MOCK] {' '.join(cmd)}")
            return True, "Mock success"

        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.returncode == 0, result.stderr.strip() or result.stdout.strip()
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _validate_username(username):
        return re.match(r'^[a-zA-Z0-9_]+$', username)

    @staticmethod
    def _validate_domain(domain):
        return re.match(r'^[a-zA-Z0-9.-]+$', domain)

    @staticmethod
    def _get_home_dir(username, domain):
        if os.path.exists("/var/www"):
            return f"/var/www/{domain or username}"
        return f"/home/{username}"

    # -------------------------
    # DB
    # -------------------------
    @classmethod
    def get_all_users(cls):
        cls._init_db()
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM ftp_users")]

    # -------------------------
    # Sync OS Users
    # -------------------------
    @classmethod
    def sync_os_users(cls):
        cls._init_db()

        if not cls._is_linux():
            return True, "Mock sync (Windows)"

        added = 0

        try:
            with open('/etc/passwd') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) < 7:
                        continue

                    username, _, uid, _, _, home_dir, shell = parts
                    uid = int(uid)

                    if uid >= 1000 and shell in ['/usr/sbin/nologin', '/bin/false']:
                        domain = os.path.basename(home_dir)

                        with sqlite3.connect(cls.DB_PATH) as conn:
                            exists = conn.execute(
                                "SELECT 1 FROM ftp_users WHERE username=?",
                                (username,)
                            ).fetchone()

                            if not exists:
                                conn.execute(
                                    "INSERT INTO ftp_users VALUES (?, ?, ?)",
                                    (username, domain, home_dir)
                                )
                                conn.commit()
                                added += 1

            return True, f"Synced {added} users"

        except Exception as e:
            return False, str(e)

    # -------------------------
    # Create User
    # -------------------------
    @classmethod
    def create_user(cls, username, password, domain_name=""):
        cls._init_db()

        if not cls._validate_username(username):
            return False, "Invalid username"

        if domain_name and not cls._validate_domain(domain_name):
            return False, "Invalid domain"

        domain_name = domain_name or username
        home_dir = cls._get_home_dir(username, domain_name)

        # Check existing user
        if cls._is_linux():
            try:
                pwd.getpwnam(username)
                return False, "User already exists"
            except KeyError:
                pass

        # Create user
        success, msg = cls._run_cmd([
            "sudo", "useradd",
            "-m",
            "-d", home_dir,
            "-s", "/usr/sbin/nologin",
            username
        ])
        if not success:
            return False, msg

        # Set password
        success, msg = cls._run_cmd(
            ["sudo", "chpasswd"],
            input_data=f"{username}:{password}"
        )
        if not success:
            return False, msg

        # Directories
        cls._run_cmd(["sudo", "mkdir", "-p", f"{home_dir}/public_html"])
        cls._run_cmd(["sudo", "mkdir", "-p", f"{home_dir}/logs"])

        cls._run_cmd(["sudo", "chown", "-R", f"{username}:{username}", home_dir])
        cls._run_cmd(["sudo", "chmod", "750", home_dir])

        if cls._is_linux():
            # Apache
            vhost = f"""<VirtualHost *:80>
    ServerName {domain_name}
    ServerAlias www.{domain_name}
    DocumentRoot {home_dir}/public_html

    <Directory {home_dir}/public_html>
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/{domain_name}_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain_name}_access.log combined
</VirtualHost>
"""
            fd, temp = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f:
                f.write(vhost)

            conf = f"/etc/apache2/sites-available/{domain_name}.conf"

            cls._run_cmd(["sudo", "mv", temp, conf])
            cls._run_cmd(["sudo", "a2ensite", f"{domain_name}.conf"])

            ok, _ = cls._run_cmd(["sudo", "apache2ctl", "configtest"])
            if ok:
                cls._run_cmd(["sudo", "systemctl", "reload", "apache2"])
            else:
                return False, "Apache config error"

            # vsftpd
            cls._run_cmd(["sudo", "mkdir", "-p", "/etc/vsftpd_user_conf"])

            fd2, temp2 = tempfile.mkstemp()
            with os.fdopen(fd2, 'w') as f:
                f.write(f"local_root={home_dir}\n")

            cls._run_cmd([
                "sudo", "mv",
                temp2,
                f"/etc/vsftpd_user_conf/{username}"
            ])

        # Save DB
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ftp_users VALUES (?, ?, ?)",
                (username, domain_name, home_dir)
            )

        return True, "User created successfully"

    # -------------------------
    # Delete User
    # -------------------------
    @classmethod
    def delete_user(cls, username):
        cls._init_db()

        success, msg = cls._run_cmd(["sudo", "userdel", "-r", username])
        if not success:
            return False, msg

        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.execute("DELETE FROM ftp_users WHERE username=?", (username,))

        return True, "User deleted"

    # -------------------------
    # Change Password
    # -------------------------
    @classmethod
    def change_password(cls, username, new_password):
        success, msg = cls._run_cmd(
            ["sudo", "chpasswd"],
            input_data=f"{username}:{new_password}"
        )
        return (True, "Password updated") if success else (False, msg)

    # -------------------------
    # Update Domain
    # -------------------------
    @classmethod
    def update_domain_path(cls, username, new_domain):
        cls._init_db()

        if new_domain and not cls._validate_domain(new_domain):
            return False, "Invalid domain"

        new_home = cls._get_home_dir(username, new_domain or username)

        success, msg = cls._run_cmd([
            "sudo", "usermod",
            "-m",
            "-d", new_home,
            username
        ])
        if not success:
            return False, msg

        cls._run_cmd(["sudo", "mkdir", "-p", f"{new_home}/public_html"])
        cls._run_cmd(["sudo", "chown", "-R", f"{username}:{username}", new_home])

        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.execute(
                "UPDATE ftp_users SET domain_name=?, home_dir=? WHERE username=?",
                (new_domain, new_home, username)
            )

        return True, "Domain updated"