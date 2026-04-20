-- VPS Panel MySQL Schema
-- Used for initial database setup via setup_server.py

-- ── users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) UNIQUE,
    role VARCHAR(20) DEFAULT 'client',
    home_directory VARCHAR(255),
    system_username VARCHAR(64) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── domains ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS domains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    document_root VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    ssl_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_domains_user_id ON domains(user_id);
CREATE INDEX idx_domains_domain_name ON domains(domain_name);

-- ── ftp_accounts ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ftp_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(64) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    domain_id INT NOT NULL,
    home_directory VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_ftp_accounts_user_id ON ftp_accounts(user_id);
CREATE INDEX idx_ftp_accounts_username ON ftp_accounts(username);
CREATE INDEX idx_ftp_accounts_domain_id ON ftp_accounts(domain_id);

-- ── client_databases ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS client_databases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    db_name VARCHAR(64) UNIQUE NOT NULL,
    db_type VARCHAR(20) DEFAULT 'mysql' NOT NULL,
    db_user VARCHAR(32) NOT NULL,
    db_host VARCHAR(255) DEFAULT 'localhost' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_client_databases_user_id ON client_databases(user_id);
CREATE INDEX idx_client_databases_db_name ON client_databases(db_name);

-- ── db_users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS db_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    db_username VARCHAR(32) UNIQUE NOT NULL,
    db_type VARCHAR(20) DEFAULT 'mysql' NOT NULL,
    db_password_encrypted VARCHAR(512) NOT NULL,
    owner_user_id INT NOT NULL,
    db_host VARCHAR(255) DEFAULT 'localhost' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_db_users_owner_id ON db_users(owner_user_id);
CREATE INDEX idx_db_users_db_username ON db_users(db_username);

-- ── db_user_permissions ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS db_user_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    db_user_id INT NOT NULL,
    db_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_dbuser_db UNIQUE(db_user_id, db_id),
    FOREIGN KEY (db_user_id) REFERENCES db_users(id) ON DELETE CASCADE,
    FOREIGN KEY (db_id) REFERENCES client_databases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_db_user_permissions_user_id ON db_user_permissions(db_user_id);
CREATE INDEX idx_db_user_permissions_db_id ON db_user_permissions(db_id);

-- ── activity_logs ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    target_type VARCHAR(64),
    target_id VARCHAR(100),
    ip_address VARCHAR(45),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX idx_activity_logs_created_at ON activity_logs(created_at);
