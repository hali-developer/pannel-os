"""
VPS Panel — Apache2 Configuration Service

Generates, enables, disables, and reloads Apache VirtualHosts
for client domains. Also manages Let's Encrypt SSL via Certbot.
"""
import os
import subprocess


def run_domain_script(domain: str, web_dir: str):
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "/usr/local/bin/add_domain.sh", domain, web_dir],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def remove_domain_script(domain: str, web_dir: str):
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "/usr/local/bin/remove_domain.sh", domain, web_dir],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def install_ssl_script(domain: str, web_dir: str) -> tuple[bool, str]:
    """
    Run add_ssl.sh to obtain a Let's Encrypt certificate and configure Apache.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "/usr/local/bin/add_ssl.sh", domain, web_dir],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "add_ssl.sh timed out after 180 seconds."
    except Exception as e:
        return False, str(e)


def revoke_ssl_certbot(domain: str) -> tuple[bool, str]:
    """
    Delete the Certbot certificate for the domain without revoking it
    from Let's Encrypt (safe and instant; avoids rate-limit penalties).
    """
    try:
        result = subprocess.run(
            [
                "/usr/bin/sudo", "/usr/bin/certbot",
                "delete",
                "--cert-name", domain,
                "--non-interactive",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Certbot delete timed out."
    except Exception as e:
        return False, str(e)


def generate_ssl_vhost_config(domain: str, document_root: str) -> str:
    """Generate the Apache VirtualHost configuration for port 443 with SSL."""
    return f"""<VirtualHost *:443>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot {document_root}

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/{domain}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{domain}/privkey.pem
    Include /etc/apache2/conf-available/ssl-params.conf

    <Directory {document_root}>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/{domain}_ssl_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}_ssl_access.log combined
</VirtualHost>
"""


class ApacheService:
    """Manages Apache VirtualHost configurations and SSL for client domains."""

    @classmethod
    def deploy_domain(cls, domain: str, web_dir: str):
        ok, msg = run_domain_script(domain, web_dir)
        if not ok:
            return False, msg
        return True, f"Domain deployed:\n{msg}"

    @classmethod
    def undeploy_domain(cls, domain: str, web_dir: str) -> tuple[bool, str]:
        """Full removal: disable site → remove config → reload."""
        ok, msg = remove_domain_script(domain, web_dir)
        if not ok:
            return False, msg
        return True, f"Domain '{domain}' undeployed."

    @classmethod
    def install_ssl(cls, domain: str, web_dir: str, email: str) -> tuple[bool, str]:
        """Obtain and install a Let's Encrypt SSL certificate via add_ssl.sh."""
        ok, msg = install_ssl_script(domain, web_dir)
        if not ok:
            return False, f"SSL installation failed: {msg}"
        return True, f"SSL installed and configured for '{domain}'.\n{msg}"

    @classmethod
    def deploy_ssl_config(cls, domain: str, web_root: str = "/var/www") -> tuple[bool, str]:
        """Generate and write the SSL configuration file, then enable it."""
        document_root = os.path.join(web_root, domain, "public_html")
        config_content = generate_ssl_vhost_config(domain, document_root)
        config_path = f"/etc/apache2/sites-available/{domain}-ssl.conf"

        try:
            # Write config using sudo tee
            process = subprocess.run(
                ["/usr/bin/sudo", "bash", "-c", f"cat > {config_path}"],
                input=config_content,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                return False, f"Failed to write SSL config: {process.stderr}"

            # Enable site
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/a2ensite", f"{domain}-ssl.conf"], check=True)

            # Reload Apache
            subprocess.run(["/usr/bin/sudo", "/usr/bin/systemctl", "reload", "apache2"], check=True)

            return True, f"SSL VirtualHost for {domain} enabled."
        except Exception as e:
            return False, str(e)

    @classmethod
    def revoke_ssl(cls, domain: str) -> tuple[bool, str]:
        """Remove the Certbot certificate and disable SSL config."""
        # Disable and remove SSL config first
        try:
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/a2dissite", f"{domain}-ssl.conf"], check=False)
            subprocess.run(["/usr/bin/sudo", "/bin/rm", "-f", f"/etc/apache2/sites-available/{domain}-ssl.conf"], check=False)
            subprocess.run(["/usr/bin/sudo", "/usr/bin/systemctl", "reload", "apache2"], check=False)
        except Exception as e:
            logger.warning(f"Error removing SSL config for {domain}: {e}")

        ok, msg = revoke_ssl_certbot(domain)
        if not ok:
            return False, f"SSL certificate removal failed: {msg}"
        return True, f"SSL certificate and configuration removed for '{domain}'."

