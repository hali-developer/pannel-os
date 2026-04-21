#!/bin/bash
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

    ErrorLog \${APACHE_LOG_DIR}/${DOMAIN}_ssl_error.log
    CustomLog \${APACHE_LOG_DIR}/${DOMAIN}_ssl_access.log combined
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
  sed -i '/ErrorLog/i \    RewriteEngine On\n    RewriteCond %{HTTPS} off\n    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]\n' "$APACHE_CONF"
fi

echo "Testing Apache config..."
apache2ctl configtest
if [ $? -ne 0 ]; then
  echo "Apache config test failed — rolling back"
  a2dissite "${DOMAIN}-ssl.conf"
  sed -i '/RewriteEngine On/d' "$APACHE_CONF"
  sed -i '/RewriteCond %{HTTPS} off/d' "$APACHE_CONF"
  sed -i '/RewriteRule \^(.\\*)\\$ https/d' "$APACHE_CONF"
  rm -f "$APACHE_SSL_CONF"
  systemctl reload apache2
  exit 1
fi

echo "Reloading Apache..."
systemctl reload apache2

echo "Done ✅ SSL configured for $DOMAIN!"
exit 0
