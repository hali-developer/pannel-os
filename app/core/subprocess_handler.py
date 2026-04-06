"""
VPS Panel — Safe Subprocess Handler

Wraps all system command execution with:
  - Command whitelist enforcement
  - No shell=True (prevents injection)
  - Timeout enforcement
  - Structured logging
  - Platform-aware mocking (Windows dev)
"""
import subprocess
import platform
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Allowed Commands ──
# Only these binaries may be executed via safe_run().
ALLOWED_COMMANDS = {
    'useradd', 'userdel', 'usermod', 'chpasswd', 'passwd',
    'chown', 'chmod', 'mkdir', 'rm', 'mv', 'cp', 'ln',
    'nginx', 'systemctl',
    'certbot',          # future: SSL
    'tar', 'gzip',      # future: backups
}

# Commands that require sudo
SUDO_COMMANDS = {
    'useradd', 'userdel', 'usermod', 'chpasswd', 'passwd',
    'chown', 'chmod', 'mkdir', 'rm', 'mv', 'cp', 'ln',
    'nginx', 'systemctl', 'certbot', 'tar',
}


def is_windows() -> bool:
    """Check if running on Windows (development mode)."""
    return platform.system() == 'Windows'


def safe_run(
    cmd: list[str],
    input_data: Optional[str] = None,
    timeout: int = 30,
    use_sudo: bool = True,
    check: bool = False,
) -> tuple[bool, str]:
    """
    Execute a system command safely.

    Args:
        cmd: Command as list of strings (no shell expansion).
        input_data: Optional stdin data to pipe to the command.
        timeout: Maximum execution time in seconds.
        use_sudo: Whether to prepend sudo if command is in SUDO_COMMANDS.
        check: If True, raise on non-zero exit code.

    Returns:
        (success: bool, output: str)

    On Windows, all commands are mocked for development.
    """
    if not cmd:
        return False, "Empty command"

    # Extract the base command (might be 'sudo' wrapping something)
    base_cmd = cmd[0]
    if base_cmd == 'sudo' and len(cmd) > 1:
        base_cmd = cmd[1]

    # ── Whitelist Check ──
    if base_cmd not in ALLOWED_COMMANDS:
        msg = f"Command '{base_cmd}' is not in the allowed commands whitelist."
        logger.error(f"BLOCKED: {msg}")
        return False, msg

    # ── Windows Mock ──
    if is_windows():
        mock_msg = f"[MOCK] {' '.join(cmd)}"
        if input_data:
            mock_msg += f" (stdin: {len(input_data)} bytes)"
        logger.info(mock_msg)
        return True, mock_msg

    # ── Prepend sudo if needed ──
    if use_sudo and base_cmd in SUDO_COMMANDS and cmd[0] != 'sudo':
        cmd = ['sudo'] + cmd

    # ── Execute ──
    cmd_str = ' '.join(cmd)
    logger.info(f"EXEC: {cmd_str}")

    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,  # NEVER use shell=True
        )

        output = result.stdout.strip() or result.stderr.strip()

        if result.returncode != 0:
            logger.error(f"FAILED (exit {result.returncode}): {cmd_str} — {output}")
            if check:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stdout, result.stderr
                )
            return False, output

        logger.info(f"OK: {cmd_str}")
        return True, output

    except subprocess.TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {cmd_str}"
        logger.error(msg)
        return False, msg
    except FileNotFoundError:
        msg = f"Command not found: {base_cmd}"
        logger.error(msg)
        return False, msg
    except PermissionError:
        msg = f"Permission denied executing: {cmd_str}"
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Unexpected error: {str(e)}"
        logger.error(msg)
        return False, msg
