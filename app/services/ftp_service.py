"""
VPS Panel — FTP System Service

Low-level OS operations for managing vsftpd virtual users:
  - System user creation/deletion
  - Password management
  - Directory provisioning
  - vsftpd per-user config generation
"""
import os
import logging
from flask import current_app
from app.core.subprocess_handler import safe_run

logger = logging.getLogger(__name__)


class FTPSystemService:
    """System-level FTP user operations."""

    @staticmethod
    def _get_web_root() -> str:
        return current_app.config.get('WEB_ROOT', '/var/www')

    @staticmethod
    def _get_ftp_conf_dir() -> str:
        return current_app.config.get('FTP_USER_CONF_DIR', '/etc/vsftpd_user_conf')

    @classmethod
    def get_home_directory(cls, username: str) -> str:
        """Get the home directory path for a user."""
        return os.path.join(cls._get_web_root(), username)


   
    @classmethod
    def setup_directories(cls, home_dir: str, username: str) -> tuple[bool, str]:
        """
        Create the standard directory structure and set permissions:
          - public_html/  (document root)
          - logs/         (per-user logs)
          - tmp/          (temporary files)
        """
        dirs = [
            os.path.join(home_dir, 'public_html'),
            os.path.join(home_dir, 'logs'),
            os.path.join(home_dir, 'tmp'),
        ]

        for d in dirs:
            ok, msg = safe_run(['sudo', '/bin/mkdir', '-p', d])
            if not ok:
                return False, f"Failed to create directory {d}: {msg}"

        # Create a default index.html
        default_index = os.path.join(home_dir, 'public_html', 'index.html')
        # We'll write via a temp file approach
        import tempfile
        try:
            fd, temp_path = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f:
                f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome</title>
    <style>
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; margin: 0;
            background: linear-gradient(135deg, #0f172a, #1e1b4b);
            color: #f8fafc;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px; padding: 3rem;
            text-align: center; max-width: 500px;
        }}
        h1 {{ background: linear-gradient(to right, #fff, #8b5cf6);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome to {username}'s site</h1>
        <p>This domain is managed by VPS Panel.</p>
    </div>
</body>
</html>""")
            safe_run(['sudo', '/bin/mv', temp_path, default_index])
        except Exception:
            pass

        # Set ownership: user owns everything inside
        ok, msg = safe_run(['sudo', '/bin/chown', '-R', f'{username}:{username}', home_dir])
        if not ok:
            return False, f"Failed to set ownership: {msg}"

        # Set permissions: 750 for home, 755 for public_html
        safe_run(['sudo', '/bin/chmod', '750', home_dir])
        safe_run(['sudo', '/bin/chmod', '755', os.path.join(home_dir, 'public_html')])

        logger.info(f"Directories provisioned for {username}: {home_dir}")
        return True, "Directories created and permissions set."

    @classmethod
    def create_vsftpd_config(cls, username: str, home_dir: str) -> tuple[bool, str]:
        """Create per-user vsftpd configuration for chroot jail."""
        conf_dir = cls._get_ftp_conf_dir()

        # Ensure config directory exists
        safe_run(['sudo', '/bin/mkdir', '-p', conf_dir])

        vsftpd_config = f"local_root={home_dir}\n"

        import tempfile
        try:
            fd, temp_path = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f:
                f.write(vsftpd_config)

            conf_path = os.path.join(conf_dir, username)
            ok, msg = safe_run(['sudo', '/bin/mv', temp_path, conf_path])
            if not ok:
                return False, f"Failed to write vsftpd config: {msg}"

            logger.info(f"vsftpd config created: {conf_path}")
            return True, f"vsftpd config for '{username}' created."
        except Exception as e:
            logger.error(f"Failed to create vsftpd config for {username}: {e}")
            return False, str(e)



    @classmethod
    def deprovision_ftp_user(cls, username: str) -> tuple[bool, str]:
        """Full cleanup: remove vsftpd config + delete system user."""
        errors = []

        ok, msg = cls.remove_vsftpd_config(username)
        if not ok:
            errors.append(msg)

        ok, msg = cls.delete_system_user(username)
        if not ok:
            errors.append(msg)

        if errors:
            return False, "; ".join(errors)
        return True, f"FTP user '{username}' deprovisioned."
