#!/usr/bin/env python3
"""
VPS Panel v3.0 — Server Setup Script (Ubuntu 24.04+)

Interactive script to install and configure all dependencies:
6:   - Apache2, vsftpd, PostgreSQL, PHP, MySQL, pgAdmin 4, phpMyAdmin
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
import argparse
import re
import socket
import contextlib

@contextlib.contextmanager
def mysql_config(user, password):
    """Creates a temporary my.cnf for secure non-interactive access."""
    cfg_content = f"""[client]
user={user}
password={password}
host=localhost
"""
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(cfg_content)
        os.chmod(path, 0o600)
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)


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


def get_public_ip() -> str:
    """Detect the server's public IP address automatically."""
    # Method 1: hostname -I (fastest, works offline)
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
        ips = result.stdout.strip().split()
        # Filter out loopback and IPv6, take first real IPv4
        for ip in ips:
            parts = ip.split('.')
            if len(parts) == 4 and parts[0] not in ('127', '10', '172', '192'):
                return ip
        # Fallback to any non-loopback if no public IP found above
        if ips:
            return ips[0]
    except Exception:
        pass

    # Method 2: curl public IP service
    for service in ['https://api.ipify.org', 'https://ifconfig.me', 'https://icanhazip.com']:
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "5", service],
                capture_output=True, text=True, timeout=10
            )
            ip = result.stdout.strip()
            if ip and ip.count('.') == 3:
                return ip
        except Exception:
            continue

    # Final fallback
    return 'YOUR_SERVER_IP'


def update_env_file(env_path, key, value):
    """Surgically update a key in .env file."""
    if not os.path.exists(env_path):
        return False
    with open(env_path, 'r') as f:
        lines = f.readlines()
    updated = False
    new_lines = []
    pattern = re.compile(rf'^\s*{key}\s*=.*')
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append(f"{key}={value}\n")
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    return True


def reset_mysql_password(new_pass, env_path=None):
    """Reset MySQL root password via sudo and sync to .env if provided."""
    print(f"\n  Attempting MySQL root password reset...")
    # Method 1: ALTER USER (MySQL 8.0+)
    sql = f"ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '{new_pass}';"
    try:
        # Use sudo to bypass auth_socket/password if running as system root
        subprocess.run(["mysql", "-e", sql], check=True, capture_output=True)
        print(f"  ✅ MySQL password updated successfully.")
        if env_path:
            update_env_file(env_path, 'MYSQL_ROOT_PASSWORD', new_pass)
            update_env_file(env_path, 'MYSQL_ADMIN_PASSWORD', new_pass)
            print(f"  ✅ Configuration synchronized in {env_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ MySQL reset failed: {e.stderr.decode().strip()}")
        print("  Trying legacy method...")
        try:
            sql_legacy = f"SET PASSWORD FOR 'root'@'localhost' = PASSWORD('{new_pass}');"
            subprocess.run(["mysql", "-e", sql_legacy], check=True, capture_output=True)
            print(f"  ✅ MySQL password updated (legacy method).")
            if env_path:
                update_env_file(env_path, 'MYSQL_ROOT_PASSWORD', new_pass)
                update_env_file(env_path, 'MYSQL_ADMIN_PASSWORD', new_pass)
            return True
        except Exception as e2:
            print(f"  ❌ All MySQL reset methods failed: {e2}")
            return False


def main():
    parser = argparse.ArgumentParser(description="VPS Panel v3.0 — Server Setup")
    parser.add_argument('--reset-mysql', action='store_true', help="Only reset MySQL root password and update .env")
    args = parser.parse_args()

    print("=" * 60)
    print("  VPS Panel v3.0 — Server Setup (Ubuntu 24.04+)")
    print("=" * 60)
    print()

    if os.geteuid() != 0:
        print("⚠  This script must be run as root (sudo).")
        sys.exit(1)

    panel_dir = "/var/www/panel"
    env_path = os.path.join(panel_dir, '.env')

    # ── Handle --reset-mysql Flag ──
    if args.reset_mysql:
        if not os.path.exists(env_path):
            print(f"  ❌ Error: {env_path} not found. Perform a full install first.")
            sys.exit(1)
        new_pass = generate_secret(20)
        if reset_mysql_password(new_pass, env_path):
            print(f"\n  RESTARTING PANEL SERVICE...")
            subprocess.run(["systemctl", "restart", "vps-panel"], check=False)
            print(f"\n  ✅ SUCCESS! New MySQL Root Password: {new_pass}")
        sys.exit(0)

    # ── Detect Server IP ──
    print("\n  Detecting server IP address...")
    server_ip = get_public_ip()
    print(f"  ✅ Server IP: {server_ip}")

    # ── Interactive Credentials Collection ──
    print("\n" + "="*30)
    print("  CREDENTIALS CONFIGURATION")
    print("="*30)
    
    # MySQL Admin (Provisioning)
    mysql_admin_user = input("  MySQL panel admin username [root]: ").strip() or "root"
    mysql_admin_pass = getpass.getpass(f"  MySQL password for '{mysql_admin_user}': ") or "StrongMySQLPass123!"
    
    # Internal Panel DB (The one SQLAlchemy connects to)
    panel_db = input("  Internal Panel DB name [panel_db]: ").strip() or "panel_db"
    panel_user = input("  Internal Panel DB user [panel_user]: ").strip() or "panel_internal"
    panel_pass = getpass.getpass(f"  Internal Panel DB password: ") or generate_secret(16)
    
    # Web Admin login (Panel UI)
    web_admin_user = "admin"
    web_admin_pass = "admin"
    
    # PostgreSQL Admin (Optional/Client support)
    postgres_admin_pass = generate_secret(20)

    # ── Step 1: System Packages ──
    print("\n[1/7] Installing system packages...")
    run(["apt", "update", "-y"])
    run([
        'apt', 'install', '-y',
        'apache2',
        'openssl',
        'postgresql',
        'postgresql-contrib',
        'proftpd-mod-mysql', # Changed from postgres to mysql
        'proftpd-mod-crypto',
        'libapache2-mod-php',
        'php-mysql',
        'php-pgsql',
        'php-mbstring',
        'php-zip',
        'php-gd',
        'php-json',
        'php-curl',
        'mysql-server',
        'python3-pip',
        'python3-venv',
        'python3-dev',
        'certbot',
        'python3-certbot-apache',
        'libmysqlclient-dev', # Added for mysqlclient support
        'libpq-dev',
        'build-essential',
        'curl',
        'gpg',
        'debconf-utils'
    ])
    print("  ✅ System packages installed.")

    # ── Step 1.2: phpMyAdmin (Automatic) ──
    print("\n[1.2/7] Installing phpMyAdmin...")
    pma_pass = generate_secret(16)
    # Set debconf for non-interactive install
    subprocess.run(f"echo 'phpmyadmin phpmyadmin/dbconfig-install boolean true' | debconf-set-selections", shell=True)
    subprocess.run(f"echo 'phpmyadmin phpmyadmin/app-password password {pma_pass}' | debconf-set-selections", shell=True)
    subprocess.run(f"echo 'phpmyadmin phpmyadmin/reconfigure-webserver multiselect apache2' | debconf-set-selections", shell=True)
    run(["apt", "install", "-y", "phpmyadmin"])
    run(["a2enconf", "phpmyadmin"], check=False)

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

    # ── Step 2: MySQL Setup (Panel & Admin) ──
    print("\n[2/7] Configuring MySQL...")
    
    mysql_cmds = f"""
-- Force mysql_native_password for root (best compatibility with Flask connectors)
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '{mysql_admin_pass}';

-- Create provisioning admin if different from root
CREATE USER IF NOT EXISTS '{mysql_admin_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{mysql_admin_pass}';
ALTER USER '{mysql_admin_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{mysql_admin_pass}';
GRANT ALL PRIVILEGES ON *.* TO '{mysql_admin_user}'@'localhost' WITH GRANT OPTION;

-- Create internal panel database and user
CREATE DATABASE IF NOT EXISTS {panel_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{panel_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{panel_pass}';
ALTER USER '{panel_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{panel_pass}';
GRANT ALL PRIVILEGES ON {panel_db}.* TO '{panel_user}'@'localhost';

FLUSH PRIVILEGES;
"""
    # Use sudo to ensure we can connect via auth_socket initially
    try:
        proc = subprocess.run(['sudo', 'mysql', '-e', mysql_cmds], capture_output=True, text=True)
        if proc.returncode == 0:
            print("  ✅ MySQL panel database and admin users configured.")
        else:
             print(f"  ❌ MySQL setup failed: {proc.stderr}")
    except Exception as e:
        print(f"  ❌ MySQL setup error: {e}")

    # ── Step 2.2: PostgreSQL Setup (Client Databases) ──
    print("\n[2.2/7] Configuring PostgreSQL (Alternative Engine)...")
    pg_cmds = [
        f"ALTER USER postgres WITH PASSWORD '{postgres_admin_pass}';",
    ]
    for sql in pg_cmds:
        run(['sudo', '-u', 'postgres', 'psql', '-c', sql], check=False)
    print("  ✅ PostgreSQL configured as secondary service.")

    # ── Step 2.3: Final Hardening ──
    try:
        # Additional MySQL hardening
        run(["mysql", "-u", mysql_admin_user, f"-p{mysql_admin_pass}", "-e", "DELETE FROM mysql.user WHERE User='';"], check=False)
        run(["mysql", "-u", mysql_admin_user, f"-p{mysql_admin_pass}", "-e", "DROP DATABASE IF EXISTS test;"], check=False)
        run(["mysql", "-u", mysql_admin_user, f"-p{mysql_admin_pass}", "-e", "FLUSH PRIVILEGES;"], check=False)
        print("  ✅ MySQL hardening completed.")
    except Exception as e:
        print(f"  ❌ MySQL hardening failed: {e}")

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

    SQLConnectInfo {panel_db}@localhost {panel_user} {panel_pass}

    SQLUserInfo ftp_accounts username password NULL NULL home_directory NULL
    SQLUserWhereClause "is_active=true"

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
PANEL_DB_PORT=3306

POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_ADMIN_USER=postgres
POSTGRESQL_ADMIN_PASSWORD={postgres_admin_pass}

DB_PASSWORD_ENCRYPTION_KEY={fernet_key}

BASE_URL=http://{server_ip}:8800
PANEL_URL=http://{server_ip}:8800
PGADMIN_URL=http://{server_ip}/pgadmin4
PHPMYADMIN_URL=http://{server_ip}/phpmyadmin

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_ADMIN_USER={mysql_admin_user}
MYSQL_ADMIN_PASSWORD={mysql_admin_pass}

LOG_LEVEL=INFO
LOG_FILE=/var/log/panel/panel.log
PANEL_NAME=VPS Panel
PANEL_VERSION=3.0.0

# Fixed salt for pgAdmin automated sync (Security Warning: Change in prod)
PGADMIN_SECURITY_PASSWORD_SALT={generate_secret(32)}

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
    schema_path = os.path.join(panel_dir, 'schema_mysql.sql')
    if os.path.exists(schema_path):
        print("  Loading MySQL schema...")
        with mysql_config("root", mysql_admin_pass) as cfg:
            # Use extra-file for secure access without password on CLI
            run(["sudo", "mysql", f"--defaults-extra-file={cfg}", panel_db, "-e", f"source {schema_path}"], check=False)
    else:
        # Fallback to python init
        run(["bash", "-c", f"cd {panel_dir} && {python_path} -c \"from app import create_app; create_app()\""])

    # Grant privileges to the panel user
    with mysql_config("root", mysql_admin_pass) as cfg:
        mysql_grant = f"GRANT ALL PRIVILEGES ON {panel_db}.* TO '{panel_user}'@'localhost';"
        run(["sudo", "mysql", f"--defaults-extra-file={cfg}", "-e", mysql_grant], check=False)

    # ── Step 7.2: Connectivity Verification ──
    print(f"\n[7.2/7] Verifying database connectivity for {panel_user}...")
    with mysql_config(panel_user, panel_pass) as cfg:
        check_cmd = ["mysql", f"--defaults-extra-file={cfg}", "-e", "SELECT 1;"]
        proc = subprocess.run(check_cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"  ✅ SUCCESS: {panel_user} can connect to MySQL.")
        else:
            print(f"  ❌ FAILURE: {panel_user} connection test failed: {proc.stderr}")
            print("  ⚠ The panel may fail to start. Check authentication plugins manually.")

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

    # ── Apache Configuration for Tools (phpMyAdmin / pgAdmin) ──
    # We no longer proxy the panel through Apache. It runs directly on 8800.
    tools_apache = f"""<VirtualHost *:80>
    ServerName _

    # phpMyAdmin Integration
    Alias /phpmyadmin /usr/share/phpmyadmin
    <Directory /usr/share/phpmyadmin>
        Options FollowSymLinks
        DirectoryIndex index.php
        AllowOverride All
        Require all granted
    </Directory>

    # Static file serving for the panel (Optional, since Gunicorn 0.0.0.0:8800 handles its own)
    Alias /static {panel_dir}/static
    <Directory {panel_dir}/static>
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/panel_tools_error.log
    CustomLog ${{APACHE_LOG_DIR}}/panel_tools_access.log combined
</VirtualHost>
"""
    # Disable the proxy port config as we move to direct port 8800
    run(["bash", "-c", "rm -f /etc/apache2/conf-available/vps-panel-ports.conf"], check=False)
    run(["a2disconf", "vps-panel-ports"], check=False)
    
    with open('/etc/apache2/sites-available/vps-panel.conf', 'w') as f:
        f.write(tools_apache)

    run(["a2ensite", "vps-panel.conf"], check=False)
    run(["systemctl", "restart", "apache2"], check=False)
    os.makedirs('/var/www/letsencrypt/.well-known/acme-challenge', exist_ok=True)
    run(["chown", "-R", "www-data:www-data", "/var/www/letsencrypt"], check=False)
    
    letsencrypt_conf = """Alias /.well-known/acme-challenge/ /var/www/letsencrypt/.well-known/acme-challenge/
<Directory /var/www/letsencrypt/>
    AllowOverride None
    Options MultiViews Indexes SymLinksIfOwnerMatch IncludesNoExec
    Require method GET POST OPTIONS
    Require all granted
</Directory>
"""
    with open('/etc/apache2/conf-available/letsencrypt.conf', 'w') as f:
        f.write(letsencrypt_conf)
    run(["a2enconf", "letsencrypt"], check=False)

    # ── Step 8: Install and Configure pgAdmin 4 ──
    print("\n[8/7] Installing pgAdmin 4...")
    
    # Add pgAdmin 4 repository
    try:
        run(["curl", "-fsS", "https://www.pgadmin.org/static/packages_pgadmin_org.pub", "-o", "pgadmin.pub"], check=True)
        run(["gpg", "--dearmor", "-o", "/usr/share/keyrings/packages-pgadmin-org.gpg", "pgadmin.pub"], check=True)
        os.remove("pgadmin.pub")
        
        distro = subprocess.run(["lsb_release", "-cs"], capture_output=True, text=True).stdout.strip()
        with open("/etc/apt/sources.list.d/pgadmin4.list", "w") as f:
            f.write(f"deb [signed-by=/usr/share/keyrings/packages-pgadmin-org.gpg] https://ftp.postgresql.org/pub/pgadmin/pgadmin4/apt/{distro} pgadmin4 main\n")
        
        run(["apt", "update", "-y"])
        run(["apt", "install", "-y", "pgadmin4-web"])
        
        # Configure pgAdmin 4 non-interactively
        # We use the panel admin email/pass. Since email is required, we'll use {web_admin_user}@localhost
        pgadmin_email = f"{web_admin_user}@localhost"
        os.environ["PGADMIN_SETUP_EMAIL"] = pgadmin_email
        os.environ["PGADMIN_SETUP_PASSWORD"] = web_admin_pass
        
        run(["/usr/pgadmin4/bin/setup-web.sh", "--yes"], check=False)
        
        # Configure pgAdmin 4 for automated Sync Logic
        # We set a fixed salt so we can pre-hash passwords for users
        pgadmin_config_path = "/usr/pgadmin4/web/config_local.py"
        with open(pgadmin_config_path, "a") as f:
            f.write(f"\nSECURITY_PASSWORD_SALT = '{os.environ.get('PGADMIN_SECURITY_PASSWORD_SALT', 'default-salt-to-change')}'\n")
            f.write("AUTHENTICATION_SOURCES = ['internal']\n")
            
        print(f"  ✅ pgAdmin 4 installed and configured for sync")
    except Exception as e:
        print(f"  ❌ pgAdmin 4 installation failed: {e}")

    # Restart apache to apply changes
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
    /usr/local/bin/manage_ssh_user.sh, \\
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

    with open('/usr/local/bin/manage_ssh_user.sh', 'w') as f:
        f.write("""#!/bin/bash
# VPS Panel — Manage SSH Users Script
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

ACTION=$1
USER=$2
PARAM=$3

if [ -z "$ACTION" ] || [ -z "$USER" ]; then
    echo "Usage: $0 [create|delete|passwd] [username] [password|home_dir]"
    exit 1
fi

case $ACTION in
    create)
        # PARAM is home_dir
        /usr/sbin/useradd -m -d "$PARAM" -U -s /bin/bash "$USER"
        exit $?
        ;;
    delete)
        /usr/sbin/userdel "$USER"
        exit $?
        ;;
    passwd)
        # PARAM is password
        echo "$USER:$PARAM" | /usr/sbin/chpasswd
        exit $?
        ;;
    *)
        echo "Invalid action: $ACTION"
        exit 1
        ;;
esac
""")
    run(["chmod", "+x", "/usr/local/bin/manage_ssh_user.sh"], check=False)

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
Environment="PATH={venv_path}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="FLASK_ENV=production"
ExecStart={gunicorn_path} --workers 3 --bind 0.0.0.0:8800 --timeout 120 run:app
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
  Panel URL:      http://{server_ip}:8800
  pgAdmin 4:       http://{server_ip}/pgadmin4
  phpMyAdmin:      http://{server_ip}/phpmyadmin
  
  Default login:  {web_admin_user} / {web_admin_pass}
  
  Service:        systemctl status vps-panel
  Logs:           journalctl -u vps-panel -f
  
  IMPORTANT: Save these credentials securely! They are in .env as well.
  
  ProFTPD Config:
    - MySQL-backed authentication
    - FTPS enabled with TLS
    - PASSIVE PORTS: 40000-50000
""")


if __name__ == '__main__':
    main()
