#!/bin/bash
# VPS Panel — Mail Server Setup Script (Postfix + Dovecot + MySQL)
# This script configures the mail server to use the panel database for virtual users.

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

PANEL_DIR="/var/h-panel"
ENV_FILE="$PANEL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

# Load DB credentials from .env
DB_USER=$(grep "^PANEL_DB_USER=" "$ENV_FILE" | cut -d'=' -f2)
DB_PASS=$(grep "^PANEL_DB_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
DB_NAME=$(grep "^PANEL_DB_NAME=" "$ENV_FILE" | cut -d'=' -f2)
DB_HOST=$(grep "^PANEL_DB_HOST=" "$ENV_FILE" | cut -d'=' -f2)

echo "[1/4] Configuring Postfix with MySQL maps..."

# 1. Postfix Virtual Domains
cat > /etc/postfix/mysql-virtual-mailbox-domains.cf <<EOF
user = $DB_USER
password = $DB_PASS
hosts = $DB_HOST
dbname = $DB_NAME
query = SELECT 1 FROM domains WHERE domain_name='%s' AND is_active=1
EOF

# 2. Postfix Virtual Mailboxes
cat > /etc/postfix/mysql-virtual-mailbox-maps.cf <<EOF
user = $DB_USER
password = $DB_PASS
hosts = $DB_HOST
dbname = $DB_NAME
query = SELECT 1 FROM email_accounts WHERE email_address='%s' AND is_active=1
EOF

# 3. Postfix Virtual Aliases (Simple fallback to owner for now)
cat > /etc/postfix/mysql-virtual-alias-maps.cf <<EOF
user = $DB_USER
password = $DB_PASS
hosts = $DB_HOST
dbname = $DB_NAME
query = SELECT email_address FROM email_accounts WHERE email_address='%s' AND is_active=1
EOF

# Set permissions
chmod 640 /etc/postfix/mysql-virtual-*.cf
chown root:postfix /etc/postfix/mysql-virtual-*.cf

# Configure main.cf
postconf -e "virtual_mailbox_domains = mysql:/etc/postfix/mysql-virtual-mailbox-domains.cf"
postconf -e "virtual_mailbox_maps = mysql:/etc/postfix/mysql-virtual-mailbox-maps.cf"
postconf -e "virtual_alias_maps = mysql:/etc/postfix/mysql-virtual-alias-maps.cf"
postconf -e "virtual_transport = lmtp:unix:private/dovecot-lmtp"
postconf -e "smtpd_sasl_type = dovecot"
postconf -e "smtpd_sasl_path = private/auth"
postconf -e "smtpd_sasl_auth_enable = yes"

echo "[2/4] Setting up vmail user..."

# Create vmail user if not exists
if ! id "vmail" &>/dev/null; then
    groupadd -g 5000 vmail
    useradd -u 5000 -g vmail -s /usr/sbin/nologin -d /var/mail/vmail -m vmail
fi

echo "[3/4] Configuring Dovecot with MySQL..."

# 1. Dovecot SQL Config
cat > /etc/dovecot/dovecot-sql.conf.ext <<EOF
driver = mysql
connect = host=$DB_HOST dbname=$DB_NAME user=$DB_USER password=$DB_PASS
default_pass_scheme = BLF-CRYPT
password_query = SELECT email_address as user, password_hash as password FROM email_accounts WHERE email_address = '%u' AND is_active=1
user_query = SELECT '/var/mail/vmail/%d/%n' as home, 5000 as uid, 5000 as gid FROM email_accounts WHERE email_address = '%u' AND is_active=1
EOF

# 2. Enable SQL in Dovecot
sed -i 's/#!include auth-sql.conf.ext/!include auth-sql.conf.ext/' /etc/dovecot/conf.d/10-auth.conf

# 3. Set mail location
echo "mail_location = maildir:/var/mail/vmail/%d/%n" >> /etc/dovecot/conf.d/10-mail.conf

# 4. Master config for LMTP and Auth
cat > /etc/dovecot/conf.d/10-master.conf <<EOF
service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}
service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0660
    user = postfix
    group = postfix
  }
}
EOF

echo "[4/4] Restarting services..."
systemctl restart postfix
systemctl restart dovecot

echo "✅ Mail server configured with panel database."
