#!/bin/bash
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
