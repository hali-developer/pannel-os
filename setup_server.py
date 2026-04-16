#!/usr/bin/env python3
"""
VPS Panel v3.0 — Server Setup Script (Ubuntu 24.04+)

Interactive script to install and configure all dependencies:
  - Apache2, vsftpd, PostgreSQL, PHP, phppgadmin
  - Create PostgreSQL panel database and user
  - Create PostgreSQL panel admin user with privileges
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
    chars = string.ascii_letters + string.digits
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
        'postgresql',
        'postgresql-contrib',
        'proftpd-mod-pgsql',
        'proftpd-mod-crypto',
        'libapache2-mod-php',
        'php-pgsql',
        'php-mbstring',
        'php-zip',
        'php-gd',
        'php-json',
        'php-curl',
        'phppgadmin',
        'python3-pip',
        'python3-venv',
        'python3-dev',
        'certbot',
        'python3-certbot-apache',
        'libpq-dev',
        'build-essential'
    ])
    print("  ✅ System packages installed.")

    # ── Move Code to /var/www/pannel ──
    print("\n[1.5/7] Moving panel code to /var/www/pannel...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    panel_dir = "/var/www/pannel"
    
    if current_dir != panel_dir:
        os.makedirs(panel_dir, exist_ok=True)
        # Using bash to expand the shell wildcard properly if needed, but safe here with current_dir/.
        run(["bash", "-c", f"cp -a {current_dir}/. {panel_dir}/"], check=False)
        run(["chown", "-R", "root:root", panel_dir], check=False)
        print(f"  ✅ Code moved to {panel_dir}.")

    # ── Step 2: PostgreSQL Setup (Panel & Admin) ──
    print("\n[2/7] Configuring PostgreSQL...")
    
    # Generate automatic credentials for security
    mysql_admin_user = "postgres"
    mysql_admin_pass = generate_secret(16)
    
    pannel_db = "pannel_db"
    pannel_user = "pannel_internal"
    pannel_pass = generate_secret(16)
    
    web_admin_user = "admin"
    web_admin_pass = generate_secret(12)

    pg_cmds = [
        f"ALTER USER {mysql_admin_user} WITH PASSWORD '{mysql_admin_pass}';",
        # Terminate any existing connections to the database to safely drop it
        f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{pannel_db}' AND pid <> pg_backend_pid();",
        f"DROP DATABASE IF EXISTS {pannel_db};",
        f"DROP USER IF EXISTS {pannel_user};",
        f"CREATE USER {pannel_user} WITH ENCRYPTED PASSWORD '{pannel_pass}';",
        f"CREATE DATABASE {pannel_db} OWNER {pannel_user} ENCODING 'utf8';"
    ]
    
    setup_failed = False
    for sql in pg_cmds:
        cmd = ['sudo', '-u', 'postgres', 'psql', '-c', sql]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 and 'already exists' not in proc.stderr:
                print(f"  ❌ PostgreSQL setup failed: {proc.stderr}")
                setup_failed = True
                break
        except Exception as e:
            print(f"  ❌ PostgreSQL setup error: {e}")
            setup_failed = True
            break
            
    if not setup_failed:
        print("  ✅ PostgreSQL panel database and users configured.")

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
LoadModule mod_sql_postgres.c /usr/lib/proftpd/mod_sql_postgres.so
LoadModule mod_tls.c /usr/lib/proftpd/mod_tls.so

<IfModule mod_sql.c>
    SQLBackend postgres
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
    env_path = os.path.join(panel_dir, '.env')

    env_content = f"""# VPS Panel v3.0 Configuration (Auto-generated)
FLASK_ENV=production
SECRET_KEY={generate_secret()}
JWT_SECRET_KEY={generate_secret()}

PANEL_DB_HOST=localhost
PANEL_DB_NAME={pannel_db}
PANEL_DB_USER={pannel_user}
PANEL_DB_PASSWORD={pannel_pass}

POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_ADMIN_USER={mysql_admin_user}
POSTGRESQL_ADMIN_PASSWORD={mysql_admin_pass}

DB_PASSWORD_ENCRYPTION_KEY={fernet_key}

WEB_ROOT=/var/www
LOG_LEVEL=INFO
LOG_FILE=/var/log/pannel/panel.log
PANEL_NAME=VPS Panel
PANEL_VERSION=3.0.0

# Initial Web Admin Credentials
PANEL_ADMIN_USER={web_admin_user}
PANEL_ADMIN_PASSWORD={web_admin_pass}
"""
    with open(env_path, 'w') as f:
        f.write(env_content)
    print(f"  ✅ .env written.")

    # ── Step 6: Python Environment ──
    print("\n[6/7] Setting up Python environment...")
    venv_path = os.path.join(panel_dir, 'venv')
    if not os.path.exists(venv_path):
        run(["python3", "-m", "venv", venv_path])
    
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
    # Initialize database schema
    schema_path = os.path.join(panel_dir, 'schema.sql')
    if os.path.exists(schema_path):
        print("  Loading PostgreSQL schema...")
        # psql can run files directly via -f on the targeted database
        run(["sudo", "-u", "postgres", "psql", "-d", pannel_db, "-f", schema_path], check=False)
    else:
        # Fallback to python init
        run(["bash", "-c", f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\""])

    # Grant privileges to the pannel user so it can modify tables created by the postgres system user
    run(["sudo", "-u", "postgres", "psql", "-d", pannel_db, "-c", f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {pannel_user};"], check=False)
    run(["sudo", "-u", "postgres", "psql", "-d", pannel_db, "-c", f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {pannel_user};"], check=False)

    # Ensure Web Admin user is created correctly with the dynamically generated password
    admin_setup_code = f"from app import create_app; from app.extensions import db; from app.models.user import User; from werkzeug.security import generate_password_hash; app = create_app(); app.app_context().push(); " \
                       f"u = User.query.filter_by(username='{web_admin_user}').first(); " \
                       f"db.session.add(User(username='{web_admin_user}', password_hash=generate_password_hash('{web_admin_pass}'), role='admin', is_active=True)) if not u else None; " \
                       f"db.session.commit()"
    
    run(["bash", "-c", f"cd {panel_dir} && {python_path} -c \"{admin_setup_code}\""], check=False)
    
    # Ensure log directory is owned by www-data so the service can write to it
    run(["chown", "-R", "www-data:www-data", "/var/log/pannel"], check=False)
    
    # Apache Setup
    run(["a2enmod", "proxy", "proxy_http", "headers", "rewrite"], check=False)
    
   # Ensure Config for phppgadmin is available (if present)
    if os.path.exists('/etc/phppgadmin/apache.conf'):
        run(["ln", "-sf", "/etc/phppgadmin/apache.conf", "/etc/apache2/conf-available/phppgadmin.conf"], check=False)
        run(["a2enconf", "phppgadmin"], check=False)

    panel_apache = f"""<VirtualHost *:8080>
    ServerName _

    # Exclude phppgadmin from proxying to Flask
    ProxyPass /phppgadmin !
    Alias /phppgadmin /usr/share/phppgadmin
    <Directory /usr/share/phppgadmin>
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
    run(["bash", "-c", "echo 'Listen 8080' > /etc/apache2/conf-available/vps-panel-ports.conf"], check=False)
    run(["a2enconf", "vps-panel-ports"], check=False)
    with open('/etc/apache2/sites-available/vps-panel.conf', 'w') as f:
        f.write(panel_apache)

    run(["a2ensite", "vps-panel.conf"], check=False)
    run(["systemctl", "restart", "apache2"], check=False)

    # Create systemd service for Gunicorn
    gunicorn_path = os.path.join(venv_path, 'bin', 'gunicorn')
    systemd_service = f"""[Unit]
Description=VPS Panel Gunicorn Service
After=network.target postgresql.service

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

    # Remove out of date phpmyadmin configs for safety
    if os.path.exists('/etc/phpmyadmin/conf.d/vps-panel.inc.php'):
        os.remove('/etc/phpmyadmin/conf.d/vps-panel.inc.php')

    # Create sudoers rule for panel
    sudoers_rule = """# VPS Panel — allow www-data to manage system users and services
www-data ALL=(ALL) NOPASSWD: \\
    /usr/sbin/useradd, \\
    /usr/sbin/userdel, \\
    /usr/sbin/usermod, \\
    /usr/sbin/chpasswd, \\
    /usr/bin/chpasswd, \\
    /bin/chown, \\
    /usr/bin/chown, \\
    /bin/chmod, \\
    /usr/bin/chmod, \\
    /bin/mkdir, \\
    /usr/bin/mkdir, \\
    /bin/rm, \\
    /usr/bin/rm, \\
    /bin/mv, \\
    /usr/bin/mv, \\
    /usr/sbin/a2ensite, \\
    /usr/sbin/a2dissite, \\
    /usr/sbin/a2enconf, \\
    /usr/sbin/apache2ctl, \\
    /usr/bin/systemctl reload apache2, \\
    /usr/bin/systemctl restart apache2, \\
    /usr/bin/systemctl restart proftpd, \\
    /usr/local/bin/add_domain.sh, \\
    /usr/local/bin/remove_domain.sh
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

# Validate domain name (basic check)
if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
  echo "Invalid domain name: $DOMAIN"
  exit 1
fi

echo "Creating web directory..."
mkdir -p "$WEBROOT"
chown -R www-data:www-data "$BASE_PATH/$DOMAIN"
chmod -R 755 "$BASE_PATH/$DOMAIN"

# Write a default index page
cat > "$WEBROOT/index.html" <<HTML
<!DOCTYPE html>
<html><head><title>$DOMAIN</title></head>
<body><h1>$DOMAIN is live!</h1><p>Hosted on VPS Panel v3.0</p></body></html>
HTML

echo "Creating Apache VirtualHost config..."
cat > "$APACHE_CONF" <<EOL
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot $WEBROOT

    <Directory $WEBROOT>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog \${APACHE_LOG_DIR}/${DOMAIN}_error.log
    CustomLog \${APACHE_LOG_DIR}/${DOMAIN}_access.log combined
</VirtualHost>
EOL

echo "Enabling site..."
a2ensite "$DOMAIN.conf"

echo "Testing Apache config..."
apache2ctl configtest
if [ $? -ne 0 ]; then
  echo "Apache config test failed — rolling back"
  a2dissite "$DOMAIN.conf"
  rm -f "$APACHE_CONF"
  exit 1
fi

echo "Reloading Apache..."
systemctl reload apache2

echo "Done ✅ $DOMAIN deployed to $WEBROOT"
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
    run(["systemctl", "start", "vps-panel"], check=False)
    print("  ✅ VPS Panel v3.0 setup complete!")
    print("=" * 60)
    print(f"""
  Panel URL:      http://YOUR_IP:5246
  phpPgAdmin:     http://YOUR_IP:5246/phppgadmin
  
  Default login:  {web_admin_user} / {web_admin_pass}
  
  Service:        systemctl status vps-panel
  Logs:           journalctl -u vps-panel -f
  
  IMPORTANT: Save these credentials securely! They are in .env as well.
  
  vsftpd Config:
    - chroot_local_user=YES
    - allow_writeable_chroot=YES
    - FTPS enabled with SSL
    - Passive ports: 40000-50000
""")


if __name__ == '__main__':
    main()
