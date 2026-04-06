"""
VPS Panel — Nginx Configuration Service

Generates, enables, disables, and reloads Nginx server blocks
for client domains.
"""
import os
import logging
import tempfile
from flask import current_app
from app.core.subprocess_handler import safe_run

logger = logging.getLogger(__name__)

# ── Nginx Server Block Template ──
NGINX_TEMPLATE = """server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};

    root {document_root};
    index index.html index.htm index.php;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Document root
    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    # PHP-FPM (if PHP is installed)
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}

    # Deny access to hidden files
    location ~ /\\. {{
        deny all;
        access_log off;
        log_not_found off;
    }}

    # Logging
    access_log /var/log/nginx/{domain}_access.log;
    error_log /var/log/nginx/{domain}_error.log;
}}
"""


class NginxService:
    """Manages Nginx server block configurations for client domains."""

    @staticmethod
    def _get_sites_available() -> str:
        return current_app.config.get('NGINX_SITES_AVAILABLE', '/etc/nginx/sites-available')

    @staticmethod
    def _get_sites_enabled() -> str:
        return current_app.config.get('NGINX_SITES_ENABLED', '/etc/nginx/sites-enabled')

    @classmethod
    def generate_config(cls, domain: str, document_root: str) -> str:
        """Render an Nginx server block for a domain."""
        return NGINX_TEMPLATE.format(
            domain=domain,
            document_root=document_root,
        )

    @classmethod
    def write_config(cls, domain: str, document_root: str) -> tuple[bool, str]:
        """Write the Nginx config file for a domain."""
        config_content = cls.generate_config(domain, document_root)
        sites_available = cls._get_sites_available()
        config_path = os.path.join(sites_available, domain)

        try:
            # Write to temp file first, then move (atomic on Linux)
            fd, temp_path = tempfile.mkstemp(suffix='.conf')
            with os.fdopen(fd, 'w') as f:
                f.write(config_content)

            # Move to sites-available
            ok, msg = safe_run(['sudo', 'mv', temp_path, config_path])
            if not ok:
                return False, f"Failed to write config: {msg}"

            # Set correct ownership
            safe_run(['sudo', 'chown', 'root:root', config_path])
            safe_run(['sudo', 'chmod', '644', config_path])

            logger.info(f"Nginx config written: {config_path}")
            return True, config_path
        except Exception as e:
            logger.error(f"Failed to write Nginx config for {domain}: {e}")
            return False, str(e)

    @classmethod
    def enable_site(cls, domain: str) -> tuple[bool, str]:
        """Create symlink in sites-enabled to activate the domain."""
        sites_available = cls._get_sites_available()
        sites_enabled = cls._get_sites_enabled()
        source = os.path.join(sites_available, domain)
        target = os.path.join(sites_enabled, domain)

        ok, msg = safe_run(['sudo', 'ln', '-sf', source, target])
        if not ok:
            return False, f"Failed to enable site: {msg}"

        logger.info(f"Nginx site enabled: {domain}")
        return True, f"Site '{domain}' enabled."

    @classmethod
    def disable_site(cls, domain: str) -> tuple[bool, str]:
        """Remove symlink from sites-enabled."""
        sites_enabled = cls._get_sites_enabled()
        link_path = os.path.join(sites_enabled, domain)

        ok, msg = safe_run(['sudo', 'rm', '-f', link_path])
        if not ok:
            return False, f"Failed to disable site: {msg}"

        logger.info(f"Nginx site disabled: {domain}")
        return True, f"Site '{domain}' disabled."

    @classmethod
    def remove_config(cls, domain: str) -> tuple[bool, str]:
        """Remove both the config file and symlink."""
        # Disable first
        cls.disable_site(domain)

        # Remove config
        sites_available = cls._get_sites_available()
        config_path = os.path.join(sites_available, domain)

        ok, msg = safe_run(['sudo', 'rm', '-f', config_path])
        if not ok:
            return False, f"Failed to remove config: {msg}"

        logger.info(f"Nginx config removed: {domain}")
        return True, f"Config for '{domain}' removed."

    @classmethod
    def test_config(cls) -> tuple[bool, str]:
        """Run nginx -t to validate configuration."""
        ok, msg = safe_run(['sudo', 'nginx', '-t'])
        if ok:
            logger.info("Nginx config test passed.")
        else:
            logger.error(f"Nginx config test failed: {msg}")
        return ok, msg

    @classmethod
    def reload(cls) -> tuple[bool, str]:
        """Reload Nginx to apply new configurations."""
        # Test first
        ok, msg = cls.test_config()
        if not ok:
            return False, f"Config test failed, not reloading: {msg}"

        ok, msg = safe_run(['sudo', 'systemctl', 'reload', 'nginx'])
        if ok:
            logger.info("Nginx reloaded successfully.")
        else:
            logger.error(f"Nginx reload failed: {msg}")
        return ok, msg

    @classmethod
    def deploy_domain(cls, domain: str, document_root: str) -> tuple[bool, str]:
        """
        Full deployment: write config → enable site → test → reload.
        This is the high-level method used by the domains module.
        """
        # Step 1: Write config
        ok, msg = cls.write_config(domain, document_root)
        if not ok:
            return False, msg

        # Step 2: Enable site
        ok, msg = cls.enable_site(domain)
        if not ok:
            cls.remove_config(domain)
            return False, msg

        # Step 3: Test & Reload
        ok, msg = cls.reload()
        if not ok:
            cls.remove_config(domain)
            return False, f"Nginx reload failed after deploy: {msg}"

        return True, f"Domain '{domain}' deployed successfully."

    @classmethod
    def undeploy_domain(cls, domain: str) -> tuple[bool, str]:
        """Full removal: remove config → reload."""
        ok, msg = cls.remove_config(domain)
        if not ok:
            return False, msg

        ok, msg = cls.reload()
        if not ok:
            logger.warning(f"Nginx reload after undeploy failed: {msg}")

        return True, f"Domain '{domain}' undeployed."
