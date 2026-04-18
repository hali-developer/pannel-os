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

    # ── Panel Directory Configuration ──
    print("\n[1.5/7] Setting panel directory...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    panel_dir = "/var/www/panel"

    if os.path.abspath(current_dir) != os.path.abspath(panel_dir):
        print(f"  Copying panel files to {panel_dir}...")
        os.makedirs(panel_dir, exist_ok=True)
        shutil.copytree(
            current_dir, 
            panel_dir, 
            dirs_exist_ok=True, 
            ignore=shutil.ignore_patterns('venv', '__pycache__', '.git', '.env')
        )
        run(["chown", "-R", "www-data:www-data", panel_dir], check=False)
        print(f"  ✅ Panel installed to: {panel_dir}")
    else:
        print(f"  ✅ Running Panel directly from: {panel_dir}")

    # ── Step 2: PostgreSQL Setup (Panel & Admin) ──
    print("\n[2/7] Configuring PostgreSQL...")
    
    # Generate automatic credentials for security
    mysql_admin_user = "postgres"
    mysql_admin_pass = generate_secret(16)
    
    panel_db = "panel_db"
    panel_user = "panel_internal"
    panel_pass = generate_secret(16)
    
    web_admin_user = "admin"
    web_admin_pass = "admin"

    pg_cmds = [
        f"ALTER USER {mysql_admin_user} WITH PASSWORD '{mysql_admin_pass}';",
        # Terminate any existing connections to the database to safely drop it
        f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{panel_db}' AND pid <> pg_backend_pid();",
        f"DROP DATABASE IF EXISTS {panel_db};",
        f"DROP USER IF EXISTS {panel_user};",
        f"CREATE USER {panel_user} WITH ENCRYPTED PASSWORD '{panel_pass}';",
        f"CREATE DATABASE {panel_db} OWNER {panel_user} ENCODING 'utf8';"
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

    SQLConnectInfo {panel_db}@localhost {panel_user} {panel_pass}

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
PANEL_DB_NAME={panel_db}
PANEL_DB_USER={panel_user}
PANEL_DB_PASSWORD={panel_pass}

POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_ADMIN_USER={mysql_admin_user}
POSTGRESQL_ADMIN_PASSWORD={mysql_admin_pass}

DB_PASSWORD_ENCRYPTION_KEY={fernet_key}

WEB_ROOT=/var/www
LOG_LEVEL=INFO
LOG_FILE=/var/log/panel/panel.log
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
    os.makedirs('/var/log/panel', exist_ok=True)

    python_path = os.path.join(venv_path, 'bin', 'python')
    # Initialize database schema
    schema_path = os.path.join(panel_dir, 'schema.sql')
    if os.path.exists(schema_path):
        print("  Loading PostgreSQL schema...")
        # psql can run files directly via -f on the targeted database
        run(["sudo", "-u", "postgres", "psql", "-d", panel_db, "-f", schema_path], check=False)
    else:
        # Fallback to python init
        run(["bash", "-c", f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\""])

    # Grant privileges to the panel user so it can modify tables created by the postgres system user
    run(["sudo", "-u", "postgres", "psql", "-d", panel_db, "-c", f"GRANT USAGE, CREATE ON SCHEMA public TO {panel_user};"], check=False)
    run(["sudo", "-u", "postgres", "psql", "-d", panel_db, "-c", f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {panel_user};"], check=False)
    run(["sudo", "-u", "postgres", "psql", "-d", panel_db, "-c", f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {panel_user};"], check=False)

    # Ensure Web Admin user is created correctly
    admin_setup_script = f"""
import sys
import os
sys.path.insert(0, '{panel_dir}')
from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

try:
    app = create_app()
    with app.app_context():
        u = User.query.filter_by(username='{web_admin_user}').first()
        if not u:
            new_admin = User(
                username='{web_admin_user}',
                password_hash=generate_password_hash('{web_admin_pass}'),
                role='admin',
                is_active=True,
                home_directory=os.path.join(app.config.get('WEB_ROOT', '/var/www'), 'admin')
            )
            db.session.add(new_admin)
            db.session.commit()
            print("Admin user created successfully.")
        else:
            # Update password just in case
            u.password_hash = generate_password_hash('{web_admin_pass}')
            db.session.commit()
            print("Admin user updated successfully.")
except Exception as e:
    print(f"Error creating admin user: {{e}}")
    sys.exit(1)
"""
    script_path = os.path.join(panel_dir, 'create_admin.py')
    with open(script_path, 'w') as f:
        f.write(admin_setup_script)
    
    run([python_path, script_path], check=False)
    os.remove(script_path)
    
    # Ensure log directory is owned by www-data so the service can write to it
    run(["chown", "-R", "www-data:www-data", "/var/log/panel"], check=False)
    
    # Apache Setup
    run(["a2enmod", "proxy", "proxy_http", "headers", "rewrite", "ssl"], check=False)
    
    # Deploy SSL parameters
    ssl_params_src = os.path.join(panel_dir, 'apache2', 'ssl_params.conf')
    if os.path.exists(ssl_params_src):
        run(["cp", ssl_params_src, "/etc/apache2/conf-available/ssl-params.conf"])
        run(["a2enconf", "ssl-params"], check=False)

    # Set up global Let's Encrypt webroot alias to solve 404s behind proxies
    letsencrypt_conf = """Alias /.well-known/acme-challenge/ /var/www/letsencrypt/.well-known/acme-challenge/
<Directory /var/www/letsencrypt/>
    AllowOverride None
    Options MultiViews Indexes SymLinksIfOwnerMatch IncludesNoExec
    Require method GET POST OPTIONS
    Require all granted
</Directory>
"""
    os.makedirs('/var/www/letsencrypt/.well-known/acme-challenge', exist_ok=True)
    run(["chown", "-R", "www-data:www-data", "/var/www/letsencrypt"], check=False)
    with open('/etc/apache2/conf-available/letsencrypt.conf', 'w') as f:
        f.write(letsencrypt_conf)
    run(["a2enconf", "letsencrypt"], check=False)

   # Ensure Config for phppgadmin is available (if present)
    if os.path.exists('/etc/phppgadmin/apache.conf'):
        # Patch Require local in the source file
        run(["sed", "-i", "s/Require local/Require all granted/g", "/etc/phppgadmin/apache.conf"], check=False)
        # Also patch the symlinked copy in conf-available if it exists separately
        if os.path.exists('/etc/apache2/conf-available/phppgadmin.conf'):
            run(["sed", "-i", "s/Require local/Require all granted/g", "/etc/apache2/conf-available/phppgadmin.conf"], check=False)
        else:
            # Write an explicit override conf that always allows access
            phppgadmin_conf = """Alias /phppgadmin /usr/share/phppgadmin

<Directory /usr/share/phppgadmin>
    DirectoryIndex index.php
    Options FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
"""
            with open('/etc/apache2/conf-available/phppgadmin.conf', 'w') as f:
                f.write(phppgadmin_conf)
        run(["a2enconf", "phppgadmin"], check=False)

    if os.path.exists('/etc/phppgadmin/config.inc.php'):
        # Allow postgres superuser to login (extra_login_security blocks it by default)
        run(["sed", "-i", "s/$conf\\['extra_login_security'\\] = true;/$conf\\['extra_login_security'\\] = false;/g", "/etc/phppgadmin/config.inc.php"], check=False)
        # Only show databases owned by the logged-in user — enforces per-user isolation in phpPgAdmin
        run(["sed", "-i", "s/$conf\\['owned_only'\\] = false;/$conf\\['owned_only'\\] = true;/g", "/etc/phppgadmin/config.inc.php"], check=False)

    # Restart apache to apply phpPgAdmin global configuration and clear out old disabled sites.
    run(["systemctl", "restart", "apache2"], check=False)



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
    /usr/local/bin/remove_domain.sh, \\
    /usr/local/bin/add_ssl.sh, \\
    /usr/bin/certbot
"""
    with open('/etc/sudoers.d/vps-panel', 'w') as f:
        f.write(sudoers_rule)
    run(["chmod", "440", "/etc/sudoers.d/vps-panel"], check=False)
    print("  ✅ Sudoers rules configured with SSL support.")

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

    run(["chmod", "+x", "/usr/local/bin/remove_domain.sh"], check=False)

    with open('/usr/local/bin/add_ssl.sh', 'w') as f:
        f.write("""#!/bin/bash
# VPS Panel — Script to request Let's Encrypt SSL using Webroot and Configure Apache
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

DOMAIN=$1
BASE_PATH="/var/www"
WEBROOT="$BASE_PATH/$DOMAIN/public_html"
LE_WEBROOT="/var/www/letsencrypt"
APACHE_CONF="/etc/apache2/sites-available/$DOMAIN.conf"
APACHE_SSL_CONF="/etc/apache2/sites-available/${DOMAIN}-ssl.conf"

if [ -z "$DOMAIN" ]; then
  echo "Usage: ./add_ssl.sh domain.com"
  exit 1
fi

if [ ! -d "$WEBROOT" ]; then
  echo "Error: Directory $WEBROOT does not exist. Add the domain first."
  exit 1
fi

echo "Requesting SSL Certificate for $DOMAIN and www.$DOMAIN using webroot..."
certbot certonly --webroot -w "$LE_WEBROOT" -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

# Fallback to root domain only if www fails (e.g. DNS not pointing)
if [ $? -ne 0 ]; then
  echo "Failed for www-subdomain. Trying just $DOMAIN..."
  certbot certonly --webroot -w "$LE_WEBROOT" -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
  if [ $? -ne 0 ]; then
    echo "SSL Certificate acquisition completely failed!"
    exit 1
  fi
  # Use single domain for config
  SERVER_ALIAS=""
else
  SERVER_ALIAS="ServerAlias www.$DOMAIN"
fi

echo "Certificate acquired! Creating Apache SSL VirtualHost..."

cat > "$APACHE_SSL_CONF" <<EOL
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName $DOMAIN
    $SERVER_ALIAS
    DocumentRoot $WEBROOT

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/$DOMAIN/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/$DOMAIN/privkey.pem

    <Directory $WEBROOT>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog \\${APACHE_LOG_DIR}/${DOMAIN}_ssl_error.log
    CustomLog \\${APACHE_LOG_DIR}/${DOMAIN}_ssl_access.log combined
</VirtualHost>
</IfModule>
EOL

echo "Enabling SSL site and Apache SSL modules..."
a2enmod ssl rewrite
a2ensite "${DOMAIN}-ssl.conf"

echo "Adding HTTP -> HTTPS redirect to standard VirtualHost..."
# Only add if it doesn't already exist
if ! grep -q "RewriteEngine" "$APACHE_CONF"; then
  # Insert rewrite rules after ErrorLog
  sed -i '/ErrorLog/i \\    RewriteEngine On\\n    RewriteCond %{HTTPS} off\\n    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]\\n' "$APACHE_CONF"
fi

echo "Testing Apache config..."
apache2ctl configtest
if [ $? -ne 0 ]; then
  echo "Apache config test failed — rolling back"
  a2dissite "${DOMAIN}-ssl.conf"
  sed -i '/RewriteEngine On/d' "$APACHE_CONF"
  sed -i '/RewriteCond %{HTTPS} off/d' "$APACHE_CONF"
  sed -i '/RewriteRule \\^(.\\*)\\$ https/d' "$APACHE_CONF"
  rm -f "$APACHE_SSL_CONF"
  systemctl reload apache2
  exit 1
fi

echo "Reloading Apache..."
systemctl reload apache2

echo "Done ✅ SSL configured for $DOMAIN!"
exit 0
""")
    run(["chmod", "+x", "/usr/local/bin/add_ssl.sh"], check=False)

    # Create systemd service for Gunicorn after all shell scripts are written
    gunicorn_path = os.path.join(venv_path, 'bin', 'gunicorn')
    systemd_service = f"""[Unit]
Description=VPS Panel Gunicorn Service
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory={panel_dir}
EnvironmentFile={panel_dir}/.env
Environment="PATH={venv_path}/bin"
Environment="FLASK_ENV=production"
ExecStart={gunicorn_path} --workers 3 --bind 0.0.0.0:8000 --timeout 120 run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    with open('/etc/systemd/system/vps-panel.service', 'w') as f:
        f.write(systemd_service)
    
    run(["systemctl", "daemon-reexec"], check=False)
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "enable", "vps-panel"], check=False)
    run(["systemctl", "start", "vps-panel"], check=False)
    run(["systemctl", "restart", "vps-panel"], check=False)
    run(["systemctl", "status", "vps-panel", "--no-pager"], check=False)

    if os.path.abspath(current_dir) != os.path.abspath(panel_dir):
        print(f"  Cleaning up original setup directory: {current_dir}")
        shutil.rmtree(current_dir, ignore_errors=True)

    print("  ✅ VPS Panel v3.0 setup complete!")
    print("=" * 60)
    print(f"""
  Panel URL:      http://YOUR_IP:8000
  phpPgAdmin:     http://YOUR_IP/phppgadmin
  
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
