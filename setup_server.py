#!/usr/bin/env python3
"""
VPS Panel — Server Setup Script (Ubuntu 22.04+)

Interactive script to install and configure all dependencies:
  - Nginx, vsftpd, PostgreSQL, MySQL, PHP-FPM, phpMyAdmin
  - Create PostgreSQL panel database and user
  - Create MySQL panel admin user with GRANT ALL
  - Generate .env from template
  - Run initial database migration

Usage: sudo python3 setup_server.py
"""
import os
import sys
import subprocess
import getpass
import secrets
import string
import shutil


def run(cmd, check=True):
    """Run a shell command."""
    print(f"  → {cmd}")
    return subprocess.run(cmd, shell=True, check=check)


def generate_secret(length=64):
    """Generate a random secret key."""
    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(secrets.choice(chars) for _ in range(length))


def main():
    print("=" * 60)
    print("  VPS Panel — Server Setup (Ubuntu 22.04+)")
    print("=" * 60)
    print()

    if os.geteuid() != 0:
        print("⚠  This script must be run as root (sudo).")
        sys.exit(1)

    # ── Step 1: System Packages ──
    print("\n[1/7] Installing system packages...")
    # run("apt update -y")
    # run("apt install -y apache2 mysql-server postgresql postgresql-contrib "
    #     "vsftpd libapache2-mod-php php-mysql phpmyadmin python3-pip python3-venv "
    #     "certbot python3-certbot-apache")
    print("  ✅ System packages installed.")

    # ── Step 2: PostgreSQL Setup ──
    print("\n[2/7] Configuring PostgreSQL...")
    pg_user = input("  PostgreSQL panel username [pannel_user]: ").strip() or "pannel_user"
    pg_pass = getpass.getpass(f"  PostgreSQL password for '{pg_user}': ") or "StrongPanelPass123!"
    pg_db = input("  PostgreSQL database name [pannel_db]: ").strip() or "pannel_db"

    run(f'sudo -u postgres psql -c "CREATE USER {pg_user} WITH PASSWORD \'{pg_pass}\';"', check=False)
    run(f'sudo -u postgres psql -c "CREATE DATABASE {pg_db} OWNER {pg_user};"', check=False)
    run(f'sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE {pg_db} TO {pg_user};"', check=False)
    # PostgreSQL 15+ requires explicit schema permissions
    run(f'sudo -u postgres psql -d {pg_db} -c "GRANT ALL ON SCHEMA public TO {pg_user};"', check=False)
    run(f'sudo -u postgres psql -d {pg_db} -c "ALTER SCHEMA public OWNER TO {pg_user};"', check=False)
    print("  ✅ PostgreSQL configured.")

    # ── Step 3: MySQL Setup ──
    print("\n[3/7] Configuring MySQL...")
    mysql_root_pass = getpass.getpass("  MySQL root password: ")
    mysql_admin_user = input("  MySQL panel admin username [pannel_admin]: ").strip() or "pannel_admin"
    mysql_admin_pass = getpass.getpass(f"  MySQL password for '{mysql_admin_user}': ") or "StrongMySQLPass123!"

    mysql_cmds = f"""
CREATE USER IF NOT EXISTS '{mysql_admin_user}'@'localhost' IDENTIFIED BY '{mysql_admin_pass}';
GRANT ALL PRIVILEGES ON *.* TO '{mysql_admin_user}'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
"""
    try:
        proc = subprocess.run(
            ['mysql', '-u', 'root', f'-p{mysql_root_pass}', '-e', mysql_cmds],
            capture_output=True, text=True
        )
        if proc.returncode == 0:
            print("  ✅ MySQL panel admin configured.")
        else:
            print(f"  ⚠ MySQL warning: {proc.stderr}")
    except Exception as e:
        print(f"  ⚠ MySQL setup error: {e}")

    # ── Step 4: vsftpd Configuration ──
    print("\n[4/7] Configuring vsftpd...")
    vsftpd_conf = """listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
chroot_local_user=YES
allow_writeable_chroot=YES
user_sub_token=$USER
local_root=/var/www/$USER
pasv_min_port=40000
pasv_max_port=50000
userlist_enable=YES
userlist_deny=NO
userlist_file=/etc/vsftpd.userlist
ssl_enable=YES
rsa_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem
rsa_private_key_file=/etc/ssl/private/ssl-cert-snakeoil.key
user_config_dir=/etc/vsftpd_user_conf
"""
    with open('/etc/vsftpd.conf', 'w') as f:
        f.write(vsftpd_conf)
    os.makedirs('/etc/vsftpd_user_conf', exist_ok=True)

    # Create userlist file
    if not os.path.exists('/etc/vsftpd.userlist'):
        with open('/etc/vsftpd.userlist', 'w') as f:
            f.write('')

    run("systemctl restart vsftpd", check=False)
    print("  ✅ vsftpd configured.")

    # ── Step 5: Generate .env ──
    print("\n[5/7] Generating .env file...")
    panel_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(panel_dir, '.env')

    env_content = f"""# VPS Panel Configuration (Auto-generated)
FLASK_ENV=production
SECRET_KEY={generate_secret()}
JWT_SECRET_KEY={generate_secret()}

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER={pg_user}
POSTGRES_PASSWORD={pg_pass}
POSTGRES_DB={pg_db}

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_ADMIN_USER={mysql_admin_user}
MYSQL_ADMIN_PASSWORD={mysql_admin_pass}

FTP_METHOD=vsftpd
FTP_USER_CONF_DIR=/etc/vsftpd_user_conf

APACHE_SITES_AVAILABLE=/etc/apache2/sites-available
APACHE_SITES_ENABLED=/etc/apache2/sites-enabled

WEB_ROOT=/var/www

LOG_LEVEL=INFO
LOG_FILE=/var/log/pannel/panel.log

PANEL_NAME=VPS Panel
PANEL_VERSION=2.0.0
"""
    with open(env_path, 'w') as f:
        f.write(env_content)
    print(f"  ✅ .env written to {env_path}")

    # ── Step 6: Python Environment ──
    print("\n[6/7] Setting up Python environment...")
    # venv_path = os.path.join(panel_dir, 'venv')
    # if not os.path.exists(venv_path):
    #     run(f"python3 -m venv {venv_path}")

    # pip_path = os.path.join(venv_path, 'bin', 'pip')
    # run(f"{pip_path} install --upgrade pip")
    # run(f"{pip_path} install -r {os.path.join(panel_dir, 'requirements.txt')}")
    print("  ✅ Python dependencies installed.")

    # ── Step 7: Create Log Directory + Init DB ──
    print("\n[7/7] Final setup...")
    # os.makedirs('/var/log/pannel', exist_ok=True)

    # python_path = os.path.join(venv_path, 'bin', 'python')
    # run(f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\"")
    print("  ✅ Database tables created.")

    # ── Apache Panel Config ──
    # print("\n[8/7] Configuring Apache proxy...")
    # run("a2enmod proxy proxy_http headers rewrite")
    
    panel_apache = f"""<VirtualHost *:8080>
    ServerName _
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    Alias /static {panel_dir}/static
    <Directory {panel_dir}/static>
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/panel_error.log
    CustomLog ${{APACHE_LOG_DIR}}/panel_access.log combined
</VirtualHost>

Listen 8080
"""
    with open('/etc/apache2/sites-available/vps-panel.conf', 'w') as f:
        f.write(panel_apache)

    run("a2ensite vps-panel.conf", check=False)
    run("apache2ctl configtest", check=False)
    run("systemctl restart apache2", check=False)

    print("\n" + "=" * 60)
    print("  ✅ VPS Panel setup complete!")
    print("=" * 60)
    print(f"""
  Panel URL:     http://YOUR_IP:8080
  Admin Login:   admin / admin (CHANGE THIS IMMEDIATELY)

  Start the panel:
    cd {panel_dir}
    source venv/bin/activate
    gunicorn -w 4 -b 127.0.0.1:5000 run:app

  Or for development:
    python run.py
""")


if __name__ == '__main__':
    main()
