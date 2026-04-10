#!/usr/bin/env python3
"""
VPS Panel v3.0 — Server Setup Script (Ubuntu 24.04+)

Interactive script to install and configure all dependencies:
  - Apache2, vsftpd, MySQL, PHP, phpMyAdmin
  - Create MySQL panel database and user
  - Create MySQL panel admin user with GRANT ALL
  - Configure vsftpd for local users with chroot
  - Generate .env from template
  - Generate Fernet encryption key for DB passwords
  - Run initial database migration
  - Deploy systemd service for Gunicorn

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
    """Run command safely (no shell=True)."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, shell=False, check=check)


def generate_secret(length=64):
    """Generate a random secret key."""
    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_fernet_key():
    """Generate a Fernet encryption key for DB password encryption."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def main():
    print("=" * 60)
    print("  VPS Panel v3.0 — Server Setup (Ubuntu 24.04+)")
    print("=" * 60)
    print()

    if os.geteuid() != 0:
        print("⚠  This script must be run as root (sudo).")
        sys.exit(1)

    # ── Step 1: System Packages ──
    print("\n[1/7] Installing system packages...")
    run(["apt", "update", "-y"])
    run([
        'apt', 'install', '-y',
        'apache2',
        'openssl',
        'mysql-server',
        'proftpd-mod-mysql',
        'proftpd-mod-crypto',
        'libapache2-mod-php',
        'php-mysql',
        'php-mbstring',
        'php-zip',
        'php-gd',
        'php-json',
        'php-curl',
        'phpmyadmin',
        'python3-pip',
        'python3-venv',
        'python3-dev',
        'certbot',
        'python3-certbot-apache',
        'libmysqlclient-dev',
        'build-essential'
    ])
    print("  ✅ System packages installed.")

    # ── Step 2: MySQL Setup (Panel & Admin) ──
    print("\n[2/7] Configuring MySQL...")
    # 2.1 Admin Account (for provisioning)
    mysql_admin_user = input("  MySQL panel admin username [pannel_admin]: ").strip() or "root"
    mysql_admin_pass = getpass.getpass(f"  MySQL password for '{mysql_admin_user}': ") or "XcF@2oC1Dv11yqXFRff"
    
    # 2.2 Panel Metadata Database
    pannel_db = input("  Panel internal database name [pannel_db]: ").strip() or "pannel_db"
    pannel_user = input("  Panel internal DB user [pannel_user]: ").strip() or "admin"
    pannel_pass = getpass.getpass(f"  Panel internal DB password: ") or "StrongPassword123!"

    mysql_cmds = f"""
-- Create provisioning admin
CREATE USER IF NOT EXISTS '{mysql_admin_user}'@'localhost' IDENTIFIED BY '{mysql_admin_pass}';
GRANT ALL PRIVILEGES ON *.* TO '{mysql_admin_user}'@'localhost' WITH GRANT OPTION;

-- Create internal panel database
CREATE DATABASE IF NOT EXISTS {pannel_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{pannel_user}'@'localhost' IDENTIFIED BY '{pannel_pass}';
GRANT ALL PRIVILEGES ON *.* TO '{pannel_user}'@'localhost';

FLUSH PRIVILEGES;
"""
    
    cmd = ['sudo', 'mysql', '-e', mysql_cmds]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print("  ✅ MySQL panel databases and users configured.")
        else:
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

    # ── Step 3: proftpd Configuration ──
    print("\n[3/7] Configuring proftpd...")
    run([
        "openssl",
        "req",
        "-x509",
        "-nodes",
        "-days", "365",
        "-newkey", "rsa:2048",
        "-keyout", "/etc/ssl/private/proftpd.key",
        "-out", "/etc/ssl/certs/proftpd.crt"
    ], check=False)
    ftpd_conf = f"""LoadModule mod_sql.c /usr/lib/proftpd/mod_sql.so
LoadModule mod_sql_mysql.c /usr/lib/proftpd/mod_sql_mysql.so
LoadModule mod_tls.c /usr/lib/proftpd/mod_tls.so

<IfModule mod_sql.c>
    SQLBackend mysql
    SQLAuthTypes Crypt
    SQLAuthenticate users
    SQLDefaultUID 33
    SQLDefaultGID 33
    SQLMinUserUID 30

    SQLConnectInfo {pannel_db}@localhost {pannel_user} {pannel_pass}

    SQLUserInfo ftp_accounts username password NULL NULL home_directory NULL
    SQLUserWhereClause "is_active=1"

    RequireValidShell off
    AllowOverwrite on
</IfModule>

DefaultRoot ~

<IfModule mod_tls.c>
  TLSEngine on
  TLSLog /var/log/proftpd/tls.log
  TLSProtocol TLSv1.2
  TLSRSACertificateFile /etc/ssl/certs/proftpd.crt
  TLSRSACertificateKeyFile /etc/ssl/private/proftpd.key
  TLSRequired on
</IfModule>
"""
    with open('/etc/proftpd/proftpd.conf', 'w') as f:
        f.write(ftpd_conf)

    # os.makedirs('/etc/proftpd/conf.d', exist_ok=True)
    # if not os.path.exists('/etc/proftpd.userlist'):
    #     with open('/etc/proftpd.userlist', 'w') as f: f.write('')
    run(["systemctl", "restart", "proftpd"], check=False)
    print("  ✅ proftpd configured with chroot + local users.")

    # ── Step 4: Generate Fernet Key ──
    print("\n[4/7] Generating encryption keys...")
    try:
        fernet_key = generate_fernet_key()
        print(f"  ✅ Fernet key generated for DB password encryption.")
    except ImportError:
        print("  ⚠ cryptography not installed yet, will generate after pip install.")
        fernet_key = "GENERATE_AFTER_PIP_INSTALL"

    # ── Step 5: Generate .env ──
    print("\n[5/7] Generating .env file...")
    panel_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(panel_dir, '.env')

    env_content = f"""# VPS Panel v3.0 Configuration (Auto-generated)
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

DB_PASSWORD_ENCRYPTION_KEY={fernet_key}


APACHE_SITES_AVAILABLE=/etc/apache2/sites-available
APACHE_SITES_ENABLED=/etc/apache2/sites-enabled

WEB_ROOT=/var/www
LOG_LEVEL=INFO
LOG_FILE=/var/log/pannel/panel.log
PANEL_NAME=VPS Panel
PANEL_VERSION=3.0.0
"""
    with open(env_path, 'w') as f:
        f.write(env_content)
    print(f"  ✅ .env written.")

    # ── Step 6: Python Environment ──
    print("\n[6/7] Setting up Python environment...")
    venv_path = os.path.join(panel_dir, 'venv')
    if not os.path.exists(venv_path):
        run(f"python3 -m venv {venv_path}")

    pip_path = os.path.join(venv_path, 'bin', 'pip')
    run([pip_path, "install", "--upgrade", "pip"])
    run([pip_path, "install", "-r", os.path.join(panel_dir, "requirements.txt")])
    print("  ✅ Python dependencies installed.")

    # Regenerate Fernet key if it was deferred
    if fernet_key == "GENERATE_AFTER_PIP_INSTALL":
        python_path = os.path.join(venv_path, 'bin', 'python')
        result = subprocess.run(
            [python_path, '-c', 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            fernet_key = result.stdout.strip()
            # Update .env
            with open(env_path, 'r') as f:
                env_text = f.read()
            env_text = env_text.replace('GENERATE_AFTER_PIP_INSTALL', fernet_key)
            with open(env_path, 'w') as f:
                f.write(env_text)
            print("  ✅ Fernet key generated and .env updated.")

    # ── Step 7: Final setup ──
    print("\n[7/7] Final cleanup & panel deployment...")
    os.makedirs('/var/log/pannel', exist_ok=True)

    python_path = os.path.join(venv_path, 'bin', 'python')
    # Initialize database
    run(["bash", "-c", f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\""])
    
    # Apache Setup
    run(["a2enmod", "proxy", "proxy_http", "headers", "rewrite"], check=False)
    
   # Ensure phpMyAdmin is included in Apache
    if os.path.exists('/etc/phpmyadmin/apache.conf'):
        run(["ln", "-sf", "/etc/phpmyadmin/apache.conf", "/etc/apache2/conf-available/phpmyadmin.conf"], check=False)
        run(["a2enconf", "phpmyadmin"], check=False)

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
"""
    # Ensure port 8080 is configured
    run(["echo", "Listen 8080", ">", "/etc/apache2/conf-available/vps-panel-ports.conf"], check=False)
    run(["a2enconf", "vps-panel-ports"], check=False)
    with open('/etc/apache2/sites-available/vps-panel.conf', 'w') as f:
        f.write(panel_apache)

    run(["a2ensite", "vps-panel.conf"], check=False)
    run(["systemctl", "restart", "apache2"], check=False)

    # Create systemd service for Gunicorn
    gunicorn_path = os.path.join(venv_path, 'bin', 'gunicorn')
    systemd_service = f"""[Unit]
Description=VPS Panel Gunicorn Service
After=network.target mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory={panel_dir}
Environment="PATH={venv_path}/bin"
ExecStart={gunicorn_path} --workers 3 --bind 127.0.0.1:5000 --timeout 120 run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    with open('/etc/systemd/system/vps-panel.service', 'w') as f:
        f.write(systemd_service)
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "enable", "vps-panel"], check=False)
    run(["systemctl", "start", "vps-panel"], check=False)

    # Copy phpMyAdmin config
    pma_config_src = os.path.join(panel_dir, 'phpmyadmin_config.inc.php')
    pma_config_dst = '/etc/phpmyadmin/conf.d/vps-panel.inc.php'
    if os.path.exists(pma_config_src):
        os.makedirs('/etc/phpmyadmin/conf.d', exist_ok=True)
        shutil.copy2(pma_config_src, pma_config_dst)
        print("  ✅ phpMyAdmin config deployed.")

    # Create sudoers rule for panel
    sudoers_rule = f"""# VPS Panel — allow www-data to manage system users and services
www-data ALL=(ALL) NOPASSWD: /usr/sbin/useradd, /usr/sbin/userdel, /usr/sbin/usermod
www-data ALL=(ALL) NOPASSWD: /usr/bin/chpasswd
www-data ALL=(ALL) NOPASSWD: /bin/chown, /bin/chmod, /bin/mkdir, /bin/rm, /bin/mv, /bin/cp, /bin/ln
www-data ALL=(ALL) NOPASSWD: /usr/sbin/a2ensite, /usr/sbin/a2dissite, /usr/sbin/apache2ctl
www-data ALL=(ALL) NOPASSWD: /bin/systemctl reload apache2, /bin/systemctl restart apache2
www-data ALL=(ALL) NOPASSWD: /bin/systemctl restart vsftpd
www-data ALL=(ALL) NOPASSWD: \
/usr/sbin/useradd, \
/usr/sbin/userdel, \
/usr/sbin/usermod, \
/usr/sbin/chpasswd, \
/bin/chown, \
/bin/chmod, \
/bin/mkdir, \
/bin/rm, \
/bin/mv, \
/usr/sbin/a2ensite, \
/usr/sbin/a2dissite, \
/usr/sbin/apache2ctl, \
/bin/systemctl reload apache2, \
/bin/systemctl restart vsftpd
"""
    with open('/etc/sudoers.d/vps-panel', 'w') as f:
        f.write(sudoers_rule)
    run(["chmod", "440", "/etc/sudoers.d/vps-panel"], check=False)
    print("  ✅ Sudoers rules configured.")

    print("\n" + "=" * 60)

    with open('/usr/local/bin/add_domain.sh', 'w') as f:
        f.write("""#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

DOMAIN=$1
BASE_PATH="/var/www"
WEBROOT="$BASE_PATH/$DOMAIN/public_html"
APACHE_CONF="/etc/apache2/sites-available/$DOMAIN.conf"

if [ -z "$DOMAIN" ]; then
  echo "Domain is required"
  exit 1
fi

echo "Creating directory..."
mkdir -p "$WEBROOT"

chown -R www-data:www-data "$BASE_PATH/$DOMAIN"
chmod -R 755 "$BASE_PATH/$DOMAIN"

echo "Requesting Certificate..."
# certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

echo "Creating Apache config..."
cat > "$APACHE_CONF" <<EOL
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot $WEBROOT

    <Directory $WEBROOT>
        AllowOverride All
        Require all granted
    </Directory>
    
    # Redirect all traffic to HTTPS
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
    ErrorLog \${APACHE_LOG_DIR}/$DOMAIN_error.log
    CustomLog \${APACHE_LOG_DIR}/$DOMAIN_access.log combined
</VirtualHost>
<VirtualHost *:443>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot /var/www/$DOMAIN/public_html

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/$DOMAIN/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/$DOMAIN/privkey.pem

    <Directory /var/www/$DOMAIN/public_html>
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog \${APACHE_LOG_DIR}/$DOMAIN_error.log
    CustomLog \${APACHE_LOG_DIR}/$DOMAIN_access.log combined
</VirtualHost>
EOL

echo "Enabling site..."
a2ensite "$DOMAIN.conf"

echo "Testing Apache config..."
apache2ctl configtest
if [ $? -ne 0 ]; then
  echo "Apache config test failed"
  exit 1
fi


a2enmod ssl

apache2ctl configtest

echo "Reloading Apache..."
systemctl reload apache2

echo "Done ✅"
exit 0
        """)
    run(["chmod", "+x", "/usr/local/bin/add_domain.sh"], check=False)

    with open('/usr/local/bin/remove_domain.sh', 'w') as f:
        f.write("""#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

DOMAIN=$1
BASE_PATH="/var/www"
APACHE_CONF="/etc/apache2/sites-available/$DOMAIN.conf"

if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 domain.com"
  exit 1
fi

echo "Disabling site $DOMAIN..."
if [ -f "$APACHE_CONF" ]; then
    a2dissite "$DOMAIN.conf"
fi

echo "Removing Apache config..."
rm -f "$APACHE_CONF"
rm -f "/etc/apache2/sites-enabled/$DOMAIN.conf"

echo "Removing web directory..."
if [ -d "$BASE_PATH/$DOMAIN" ]; then
    rm -rf "$BASE_PATH/$DOMAIN"
fi

echo "Testing Apache config..."
apache2ctl configtest

echo "Reloading Apache..."
systemctl reload apache2

echo "Domain $DOMAIN removed successfully ✅"
exit 0
    """)

    # Make it executable
    run(["chmod", "+x", "/usr/local/bin/remove_domain.sh"], check=False)

    print("  ✅ VPS Panel v3.0 setup complete!")
    print("=" * 60)
    print(f"""
  Panel URL:      http://YOUR_IP:5246
  phpMyAdmin:     http://YOUR_IP:5246/phpmyadmin
  
  Default login:  admin / admin
  
  Service:        systemctl status vps-panel
  Logs:           journalctl -u vps-panel -f
  
  IMPORTANT: Change the admin password immediately!
  
  vsftpd Config:
    - chroot_local_user=YES
    - allow_writeable_chroot=YES
    - FTPS enabled with SSL
    - Passive ports: 40000-50000
""")


if __name__ == '__main__':
    main()
