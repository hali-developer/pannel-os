# VPS Hosting Control Panel 🚀

A robust, multi-tenant VPS Hosting Control Panel designed to orchestrate isolated web environments, manage databases, and automate Let's Encrypt SSL certificates from a single UI. Built purely on Python (Flask), MySQL, PostgreSQL, and native Ubuntu/Debian bash scripts.

---

## 📖 How It Works

Traditional web panels are bloated and resource-heavy. This panel takes a native, lightweight approach:
1. **Linux Integration:** When a client is created via the dashboard, the panel creates an actual Linux system user. Their web root (`public_html`) is completely sequestered to their virtual directory, preventing cross-site contamination.
2. **Web Server Automation:** Domains added via the UI trigger dynamic generation of Apache `VirtualHost` files, securely parsed through local Bash scripts executing via restricted `sudo` privileges.
3. **Database Segregation:** Clients can provision MySQL or PostgreSQL databases instantly. Privileges are rigidly assigned solely to the provisioned database using parameterized SQL queries. 
4. **FTP Security:** Users leverage ProFTPD over FTPS. Their authentication credentials correspond specifically to customized database rows managed natively by the panel.

---

## ⚙️ 1. Initial Installation Guide

> **WARNING:** The panel must be installed on a **Brand New, Freshly Installed Ubuntu/Debian Server**! Do NOT run this on a server already running Apache, Nginx, or existing websites, as the setup script will heavily overwrite configurations to establish its architecture.

### Step 1: Install Baseline Dependencies
Before you can pull the panel code, your fresh server needs Git to clone the repository, and Python to execute the installation scripts. Log into your server as `root` (or a user with `sudo` access) and run:

```bash
# Update base repositories
sudo apt update -y

# Install Git and Python 3 infrastructure
sudo apt install -y git python3 python3-pip python3-venv python-is-python3
```

### Step 2: Clone the Repository
Pull the panel source code to a working directory on your server (for example, `/root/pannel-os` or `/home/ubuntu/pannel-os`):

```bash
git clone https://github.com/hali-developer/pannel-os.git panel-src
cd panel-src
```

### Step 3: Execute the Server Setup Script
With the code downloaded, launch the primary setup script. This script acts as the master orchestrator.

```bash
sudo python3 setup_server.py
```

### What `setup_server.py` does automatically behind the scenes:
*   **Apt Installations:** Reads `system_requirements.txt` and automatically installs Apache, MySQL Server, PostgreSQL, ProFTPD, Node.js, PHP, Let's Encrypt (Certbot), and build tools.
*   **Virtual Environment:** Creates an isolated Python sandbox (`venv`) to install Flask, SQLAlchemy, Gunicorn, and background schedulers from `requirements.txt`.
*   **Environment & Secrets:** Generates secure, randomized salts and passwords, building your `.env` configuration file automatically. No manual credential writing is required.
*   **Database Initializations:** Boots the root MySQL `panel_db` database, establishing the foundational schemas the web app needs to run.
*   **Transfers Automation Scripts:** Moves the core networking shell scripts (`scripts/*.sh`) securely to `/usr/local/bin` and assigns `www-data` NOPASSWD sudo access exclusively over them.
*   **Launches the App:** Migrates the application layer into `/var/h-panel` and registers `vps-panel.service` with `systemd` to keep the dashboard permanently online on Port 8800.

Upon completion, the terminal will print out your new Panel URL, your admin login credentials (save these!), and links to Adminer/phpMyAdmin/pgAdmin.

---

## 🔄 2. Safely Updating the Panel

As you continue developing the panel (adding new HTML templates, updating Python route logic, or tweaking bash scripts), you will naturally push those updates to GitHub. 

When it is time to deploy those updates to your live production server, you **do not** run `setup_server.py` again, as that would risk resetting database credentials and generating a new `.env` file! 

Instead, you use the dedicated Update script.

### Step 1: Pull the Latest Code
Go back to the exact directory where you originally cloned the source code or re clone the latest repo.

```bash
git clone https://github.com/hali-developer/pannel-os.git panel-src
cd panel-src
git pull origin main
```

### Step 2: Run the Update Script
Tell the panel to seamlessly migrate the new changes over to the live directory.

```bash
sudo python3 update_panel.py
```

### What `update_panel.py` does automatically behind the scenes:
*   **Dependency Audits:** Checks if you've added new packages to `system_requirements.txt` or `requirements.txt` and securely installs them using `apt` and inside the `/var/h-panel/venv/` accordingly.
*   **Code Synchronization:** Mirrors your new `app/` python models, CSS updates, and frontend HTML templates directly into `/var/h-panel` while rigidly ignoring and preserving the `.env` file and user data.
*   **Script Swapping:** Migrates any newly modified Bash shell orchestration logic (`add_domain.sh`, etc.) seamlessly over to `/usr/local/bin`.
*   **Zero-Downtime Reload:** Issues `systemctl daemon-reload`, restarts the `apache2` web server, and bounces the `vps-panel` Gunicorn service natively, pushing your newest application code live instantly!
