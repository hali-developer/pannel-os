"""
VPS Panel — Apache2 Configuration Service

Generates, enables, disables, and reloads Apache VirtualHosts
for client domains.
"""
import subprocess


def run_domain_script(domain: str):
    try:
        result = subprocess.run(
            ["/usr/local/bin/add_domain.sh", domain],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def remove_domain_script(domain: str):
    try:
        result = subprocess.run(
            ["/usr/local/bin/remove_domain.sh", domain],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

class ApacheService:
    """Manages Apache VirtualHost configurations for client domains."""

    @classmethod
    def deploy_domain(cls, domain: str):
        ok, msg = run_domain_script(domain)
        if not ok:
            return False, msg

        return True, f"Domain deployed:\n{msg}"

    @classmethod
    def undeploy_domain(cls, domain: str) -> tuple[bool, str]:
        """Full removal: disable site → remove config → reload."""
        ok, msg = remove_domain_script(domain)
        if not ok:
            return False, msg
        
        return True, f"Domain '{domain}' undeployed."
