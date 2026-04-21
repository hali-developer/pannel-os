#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

DOMAIN=$1
BASE_PATH=${2:-/var/www}
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
