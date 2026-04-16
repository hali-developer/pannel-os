-- VPS Panel PostgreSQL Schema
-- Used for initial database setup via setup_server.py

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    email VARCHAR(120) UNIQUE,
    role VARCHAR(20) DEFAULT 'client',
    home_directory VARCHAR(255),
    system_username VARCHAR(64) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    document_root VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_domains_user_id ON domains(user_id);

CREATE TABLE IF NOT EXISTS ftp_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username VARCHAR(64) UNIQUE NOT NULL,
    home_directory VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ftp_accounts_user_id ON ftp_accounts(user_id);

CREATE TABLE IF NOT EXISTS client_databases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    db_name VARCHAR(64) UNIQUE NOT NULL,
    db_user VARCHAR(32) NOT NULL,
    db_host VARCHAR(255) DEFAULT 'localhost' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_client_databases_user_id ON client_databases(user_id);

CREATE TABLE IF NOT EXISTS db_users (
    id SERIAL PRIMARY KEY,
    db_username VARCHAR(32) UNIQUE NOT NULL,
    db_password_encrypted VARCHAR(255) NOT NULL,
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    db_host VARCHAR(255) DEFAULT 'localhost' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_db_users_owner_id ON db_users(owner_user_id);

CREATE TABLE IF NOT EXISTS db_user_permissions (
    id SERIAL PRIMARY KEY,
    db_user_id INTEGER NOT NULL REFERENCES db_users(id) ON DELETE CASCADE,
    db_id INTEGER NOT NULL REFERENCES client_databases(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(db_user_id, db_id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    target_type VARCHAR(64),
    target_id VARCHAR(64),
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_logs_user_id ON activity_logs(user_id);

-- End of schema
