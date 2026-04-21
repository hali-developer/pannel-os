#!/usr/bin/env python3
"""
VPS Panel v3.0 — Continuous Update Script

Safely updates the live panel installation with new changes from the repository.
It skips overwriting .env files and preserves databases/SSL certs.

Usage: sudo python3 update_panel.py
"""
import os
import sys
import subprocess
import shutil

def run(cmd, check=True):
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, shell=False, check=check)

def main():
    print("=" * 60)
    print("  VPS Panel v3.0 — Update Installer")
    print("=" * 60)
    print()

    if os.geteuid() != 0:
        print("⚠  This script must be run as root (sudo).")
        sys.exit(1)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    panel_dir = "/var/www/panel"

    if os.path.abspath(current_dir) == os.path.abspath(panel_dir):
        print("⚠  You are running this from /var/www/panel already.")
        print("   This script should be run from your standalone repo to synchronize over.")
        sys.exit(1)

    # ── 1. System Packages ──
    print("\n[1/5] Updating system packages...")
    req_path = os.path.join(current_dir, 'system_requirements.txt')
    if os.path.exists(req_path):
        with open(req_path, 'r') as f:
            packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        run(["apt", "update", "-y"])
        install_cmd = ['apt', 'install', '-y', '--no-install-recommends'] + packages
        run(install_cmd, check=False)
        print("  ✅ System packages updated.")
    else:
        print(f"  ⚠ Required file {req_path} not found. Skipping apt install.")

    # ── 2. File Synchronization ──
    print("\n[2/5] Synchronizing files to live directory...")
    os.makedirs(panel_dir, exist_ok=True)
    shutil.copytree(
        current_dir, 
        panel_dir, 
        dirs_exist_ok=True, 
        ignore=shutil.ignore_patterns('venv', '__pycache__', '.git', '.env')
    )
    run(["chown", "-R", "www-data:www-data", panel_dir], check=False)
    print(f"  ✅ Files synchronized to: {panel_dir}")

    # ── 3. Python Environment Update ──
    print("\n[3/5] Updating Python packages...")
    venv_path = os.path.join(panel_dir, 'venv')
    if not os.path.exists(venv_path):
        print(f"  ⚠ Virtual environment missing at {venv_path}. Run setup_server.py first.")
        sys.exit(1)

    pip_path = os.path.join(venv_path, 'bin', 'pip')
    run([pip_path, "install", "-r", os.path.join(panel_dir, "requirements.txt")], check=False)
    print("  ✅ Python dependencies updated.")

    # ── 4. Bash Scripts Update ──
    print("\n[4/5] Updating panel automation bash scripts...")
    scripts_dir = os.path.join(panel_dir, 'scripts')
    scripts_to_deploy = ['add_domain.sh', 'remove_domain.sh', 'add_ssl.sh', 'manage_ssh_user.sh']
    for script_name in scripts_to_deploy:
        src = os.path.join(scripts_dir, script_name)
        dest = f'/usr/local/bin/{script_name}'
        if os.path.exists(src):
            shutil.copy2(src, dest)
            run(["chmod", "+x", dest], check=False)
            print(f"  ✅ Updated {script_name}")
        else:
            print(f"  ⚠ Missing script to update: {src}")

    # ── 5. Reload Services ──
    print("\n[5/5] Restarting services to apply changes...")
    run(["systemctl", "daemon-reload"], check=False)
    run(["systemctl", "restart", "vps-panel"], check=False)
    run(["systemctl", "restart", "apache2"], check=False)

    print("\n  ✅ VPS Panel successfully updated!")
    print("=" * 60)


if __name__ == '__main__':
    main()
