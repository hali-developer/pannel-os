-- ══════════════════════════════════════════════════════════
-- VPS Panel v3.0 — MySQL Schema
-- Panel Database: pannel_db
-- ══════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS pannel_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE pannel_db;

-- ── Users ──
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) DEFAULT NULL,
    role VARCHAR(10) NOT NULL DEFAULT 'client',
    home_directory VARCHAR(255) DEFAULT NULL,
    system_username VARCHAR(50) DEFAULT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_username (username),
    INDEX idx_users_system_username (system_username),
    INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Domains ──
CREATE TABLE IF NOT EXISTS domains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    domain_name VARCHAR(255) NOT NULL UNIQUE,
    document_root VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ssl_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_domains_user_id (user_id),
    INDEX idx_domains_domain_name (domain_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── FTP Accounts ──
CREATE TABLE IF NOT EXISTS ftp_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ftp_username VARCHAR(50) NOT NULL UNIQUE,
    home_directory VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ftp_user_id (user_id),
    INDEX idx_ftp_username (ftp_username),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Client Databases ──
CREATE TABLE IF NOT EXISTS client_databases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    db_name VARCHAR(64) NOT NULL UNIQUE,
    db_user VARCHAR(32) NOT NULL,
    db_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_clientdb_user_id (user_id),
    INDEX idx_clientdb_db_name (db_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Database Users ──
CREATE TABLE IF NOT EXISTS db_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    db_username VARCHAR(32) NOT NULL UNIQUE,
    db_password_encrypted VARCHAR(512) NOT NULL,
    owner_user_id INT NOT NULL,
    db_host VARCHAR(255) NOT NULL DEFAULT 'localhost',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_dbusers_username (db_username),
    INDEX idx_dbusers_owner (owner_user_id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Database User Permissions ──
CREATE TABLE IF NOT EXISTS db_user_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    db_user_id INT NOT NULL,
    db_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_dbperm_user (db_user_id),
    INDEX idx_dbperm_db (db_id),
    UNIQUE KEY uq_dbuser_db (db_user_id, db_id),
    FOREIGN KEY (db_user_id) REFERENCES db_users(id) ON DELETE CASCADE,
    FOREIGN KEY (db_id) REFERENCES client_databases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Activity Logs ──
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT NULL,
    action VARCHAR(255) NOT NULL,
    target_type VARCHAR(50) DEFAULT NULL,
    target_id VARCHAR(100) DEFAULT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    details TEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_logs_user_id (user_id),
    INDEX idx_logs_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
