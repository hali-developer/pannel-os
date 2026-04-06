#!/usr/bin/env python3
"""
VPS Panel — Server Setup Script (Ubuntu 24.04+)

Interactive script to install and configure all dependencies:
  - Apache2, vsftpd, MySQL, PHP, phpMyAdmin
  - Create MySQL panel database and user
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
import tempfile


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
    print("  VPS Panel — Server Setup (Ubuntu 24.04+)")
    print("=" * 60)
    print()

    if os.geteuid() != 0:
        print("⚠  This script must be run as root (sudo).")
        sys.exit(1)

    # ── Step 1: System Packages ──
    print("\n[1/6] Installing system packages...")
    run("apt update -y")
    run("apt install -y apache2 mysql-server vsftpd libapache2-mod-php php-mysql "
        "phpmyadmin python3-pip python3-venv certbot python3-certbot-apache")
    print("  ✅ System packages installed.")

    # ── Step 2: MySQL Setup (Panel & Admin) ──
    print("\n[2/6] Configuring MySQL...")
    mysql_root_pass = getpass.getpass("  MySQL root password (hit enter if empty): ").strip()
    
    # 2.1 Admin Account (for provisioning)
    mysql_admin_user = input("  MySQL panel admin username [pannel_admin]: ").strip() or "pannel_admin"
    mysql_admin_pass = getpass.getpass(f"  MySQL password for '{mysql_admin_user}': ") or "StrongMySQLPass123!"
    
    # 2.2 Panel Metadata Database
    pannel_db = input("  Panel internal database name [pannel_db]: ").strip() or "pannel_db"
    pannel_user = input("  Panel internal DB user [pannel_user]: ").strip() or "pannel_user"
    pannel_pass = getpass.getpass(f"  Panel internal DB password: ") or "StrongPanelPass123!"

    mysql_cmds = f"""
-- Create provisioning admin
CREATE USER IF NOT EXISTS '{mysql_admin_user}'@'localhost' IDENTIFIED BY '{mysql_admin_pass}';
GRANT ALL PRIVILEGES ON *.* TO '{mysql_admin_user}'@'localhost' WITH GRANT OPTION;

-- Create internal panel database
CREATE DATABASE IF NOT EXISTS {pannel_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{pannel_user}'@'localhost' IDENTIFIED BY '{pannel_pass}';
GRANT ALL PRIVILEGES ON {pannel_db}.* TO '{pannel_user}'@'localhost';

FLUSH PRIVILEGES;
"""
    
    cmd = ['sudo', 'mysql', '-e', mysql_cmds]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print("  ✅ MySQL panel databases and users configured.")
        else:
            # Fallback for systems where root uses auth_socket and passwords aren't needed
            if "using password: NO" in proc.stderr or "Access denied" in proc.stderr:
                 print("  ⚠ Root access denied with password. Attempting via auth_socket...")
                 proc = subprocess.run(['sudo', 'mysql', '-e', mysql_cmds], capture_output=True, text=True)
                 if proc.returncode == 0:
                     print("  ✅ MySQL configured via sudo/auth_socket.")
                 else:
                     print(f"  ❌ MySQL setup failed: {proc.stderr}")
            else:
                print(f"  ❌ MySQL setup failed: {proc.stderr}")
    except Exception as e:
        print(f"  ❌ MySQL setup error: {e}")

    # ── Step 3: vsftpd Configuration ──
    print("\n[3/6] Configuring vsftpd...")
    # ... (vsftpd logic same as before)
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
    if not os.path.exists('/etc/vsftpd.userlist'):
        with open('/etc/vsftpd.userlist', 'w') as f: f.write('')
    run("systemctl restart vsftpd", check=False)
    print("  ✅ vsftpd configured.")

    # ── Step 4: Generate .env ──
    print("\n[4/6] Generating .env file...")
    panel_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(panel_dir, '.env')

    env_content = f"""# VPS Panel Configuration (Auto-generated)
FLASK_ENV=production
SECRET_KEY={generate_secret()}
JWT_SECRET_KEY={generate_secret()}

PANEL_DB_HOST=localhost
PANEL_DB_NAME={pannel_db}
PANEL_DB_USER={pannel_user}
PANEL_DB_PASSWORD={pannel_pass}
PANEL_DB_SOCKET=/var/run/mysqld/mysqld.sock

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
    print(f"  ✅ .env written.")

    # ── Step 5: Python Environment ──
    print("\n[5/6] Setting up Python environment...")
    venv_path = os.path.join(panel_dir, 'venv')
    if not os.path.exists(venv_path):
        run(f"python3 -m venv {venv_path}")

    pip_path = os.path.join(venv_path, 'bin', 'pip')
    run(f"{pip_path} install --upgrade pip")
    run(f"{pip_path} install -r {os.path.join(panel_dir, 'requirements.txt')}")
    print("  ✅ Python dependencies installed.")

    # ── Step 6: Final setup ──
    print("\n[6/6] Final cleanup & panel deployment...")
    os.makedirs('/var/log/pannel', exist_ok=True)

    python_path = os.path.join(venv_path, 'bin', 'python')
    # Initialize database
    run(f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\"")
    
    # Apache Setup
    run("a2enmod proxy proxy_http headers rewrite")
    
    # Ensure phpMyAdmin is included in Apache
    if os.path.exists('/etc/phpmyadmin/apache.conf'):
        run("ln -sf /etc/phpmyadmin/apache.conf /etc/apache2/conf-available/phpmyadmin.conf", check=False)
        run("a2enconf phpmyadmin", check=False)

    panel_apache = f"""<VirtualHost *:8080>
    ServerName _

    # Exclude phpMyAdmin from proxying to Flask
    ProxyPass /phpmyadmin !
    Alias /phpmyadmin /usr/share/phpmyadmin
    <Directory /usr/share/phpmyadmin>
        Options FollowSymLinks
        DirectoryIndex index.php
        AllowOverride All
        Require all granted
    </Directory>

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

# Listen is usually defined in ports.conf, but we'll ensure it's here too for 8080
<IfModule mod_ssl.c>
    # If standard ports.conf doesn't have 8080
</IfModule>
"""
    # Note: Listen 8080 should ideally be in /etc/apache2/ports.conf
    run("echo 'Listen 8080' > /etc/apache2/conf-available/vps-panel-ports.conf", check=False)
    run("a2enconf vps-panel-ports", check=False)
    with open('/etc/apache2/sites-available/vps-panel.conf', 'w') as f:
        f.write(panel_apache)

    run("a2ensite vps-panel.conf", check=False)
    run("systemctl restart apache2", check=False)

    print("\n" + "=" * 60)
    print("  ✅ VPS Panel (MySQL Edition) setup complete!")
    print("=" * 60)
    print(f"  Panel URL: http://YOUR_IP:8080\n")


if __name__ == '__main__':
    main()
