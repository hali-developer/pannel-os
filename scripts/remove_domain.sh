#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

DOMAIN=$1
BASE_PATH=${2:-/var/www}
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
