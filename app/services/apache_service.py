"""
VPS Panel — Apache2 Configuration Service

Generates, enables, disables, and reloads Apache VirtualHosts
for client domains.
"""
import os
import logging
import tempfile
from flask import current_app
from app.core.subprocess_handler import safe_run
import subprocess
import re

def run(cmd, check=True):
    """Run command safely (no shell=True)."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, shell=False, check=check)

logger = logging.getLogger(__name__)

# ── Apache VirtualHost Template ──
# Using mod_rewrite for flexibility
APACHE_TEMPLATE = """<VirtualHost *:80>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot {document_root}

    <Directory {document_root}>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    # PHP Integration (standard mod_php)
    <FilesMatch \\.php$>
        SetHandler application/x-httpd-php
    </FilesMatch>

    # Logging
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}_access.log combined

    # Security Headers
    Header set X-Frame-Options "SAMEORIGIN"
    Header set X-Content-Type-Options "nosniff"
    Header set X-XSS-Protection "1; mode=block"
</VirtualHost>
"""


class ApacheService:
    """Manages Apache VirtualHost configurations for client domains."""

    @staticmethod
    def _get_sites_available() -> str:
        return current_app.config.get('APACHE_SITES_AVAILABLE', '/etc/apache2/sites-available')

    @staticmethod
    def _get_sites_enabled() -> str:
        return current_app.config.get('APACHE_SITES_ENABLED', '/etc/apache2/sites-enabled')

    @classmethod
    def generate_config(cls, domain: str, document_root: str) -> str:
        """Render an Apache VirtualHost for a domain."""
        if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
            return False, "Invalid domain"
        
        return APACHE_TEMPLATE.format(
            domain=domain,
            document_root=document_root,
        )

    @classmethod
    def write_config(cls, domain: str, document_root: str) -> tuple[bool, str]:
        """Write the Apache config file for a domain."""
        config_content = cls.generate_config(domain, document_root)
        sites_available = cls._get_sites_available()
        config_path = os.path.join(sites_available, f"{domain}.conf")

        try:
            fd, temp_path = tempfile.mkstemp(suffix='.conf')
            with os.fdopen(fd, 'w') as f:
                f.write(config_content)

            ok, msg = run(['sudo', '/bin/mv', temp_path, config_path])
            if not ok:
                return False, f"Failed to write config: {msg}"

            run(['sudo', '/bin/chown', 'root:root', config_path])
            run(['sudo', '/bin/chmod', '644', config_path])

            logger.info(f"Apache config written: {config_path}")
            return True, config_path
        except Exception as e:
            logger.error(f"Failed to write Apache config for {domain}: {e}")
            return False, str(e)

    @classmethod
    def enable_site(cls, domain: str) -> tuple[bool, str]:
        """Activate the domain using a2ensite."""
        ok, msg = run(['sudo', '/usr/sbin/a2ensite', f"{domain}.conf"])
        if not ok:
            return False, f"Failed to enable site: {msg}"

        logger.info(f"Apache site enabled: {domain}")
        return True, f"Site '{domain}' enabled."

    @classmethod
    def disable_site(cls, domain: str) -> tuple[bool, str]:
        """Deactivate the domain using a2dissite."""
        ok, msg = run(['sudo', '/usr/sbin/a2dissite', f"{domain}.conf"])
        if not ok:
            # Maybe it's already disabled
            return True, f"Site '{domain}' already disabled."

        logger.info(f"Apache site disabled: {domain}")
        return True, f"Site '{domain}' disabled."

    @classmethod
    def remove_config(cls, domain: str) -> tuple[bool, str]:
        """Remove the config file and symlink."""
        cls.disable_site(domain)

        sites_available = cls._get_sites_available()
        config_path = os.path.join(sites_available, f"{domain}.conf")

        ok, msg = run(['sudo', '/bin/rm', '-f', config_path])
        if not ok:
            return False, f"Failed to remove config: {msg}"

        logger.info(f"Apache config removed: {domain}")
        return True, f"Config for '{domain}' removed."

    @classmethod
    def test_config(cls) -> tuple[bool, str]:
        """Run apache2ctl configtest to validate configuration."""
        ok, msg = run(['sudo', '/usr/sbin/apache2ctl', 'configtest'])
        if ok:
            logger.info("Apache config test passed.")
        else:
            logger.error(f"Apache config test failed: {msg}")
        return ok, msg

    @classmethod
    def reload(cls) -> tuple[bool, str]:
        """Reload Apache to apply new configurations."""
        ok, msg = cls.test_config()
        if not ok:
            return False, f"Config test failed, not reloading: {msg}"

        ok, msg = run(['sudo', '/bin/systemctl', 'reload', 'apache2'])
        if ok:
            logger.info("Apache reloaded successfully.")
        else:
            logger.error(f"Apache reload failed: {msg}")
        return ok, msg

    @classmethod
    def deploy_domain(cls, domain: str, document_root: str) -> tuple[bool, str]:
        """
        Full deployment: write config → enable site → test → reload.
        """
        ok, msg = cls.write_config(domain, document_root)
        if not ok:
            return False, msg

        ok, msg = cls.enable_site(domain)
        if not ok:
            cls.remove_config(domain)
            return False, msg

        ok, msg = cls.reload()
        if not ok:
            cls.remove_config(domain)
            return False, f"Apache reload failed after deploy: {msg}"

        return True, f"Domain '{domain}' deployed successfully."

    @classmethod
    def undeploy_domain(cls, domain: str) -> tuple[bool, str]:
        """Full removal: disable site → remove config → reload."""
        ok, msg = cls.remove_config(domain)
        if not ok:
            return False, msg

        ok, msg = cls.reload()
        return True, f"Domain '{domain}' undeployed."
