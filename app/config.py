"""
VPS Panel — Configuration Classes
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Base configuration shared across all environments."""

    # Flask Core
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-change-in-production')

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_COOKIE_SECURE = False  # Set True in production with HTTPS

    # PostgreSQL (Panel Data)
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
    POSTGRES_USER = os.environ.get('POSTGRES_USER', 'pannel_user')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'StrongPanelPass123!')
    POSTGRES_DB = os.environ.get('POSTGRES_DB', 'pannel_db')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # Apache
    APACHE_SITES_AVAILABLE = os.environ.get('APACHE_SITES_AVAILABLE', '/etc/apache2/sites-available')
    APACHE_SITES_ENABLED = os.environ.get('APACHE_SITES_ENABLED', '/etc/apache2/sites-enabled')

    # Web Root
    WEB_ROOT = os.environ.get('WEB_ROOT', '/var/www')

    # MySQL/MariaDB (Client Databases)
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_UNIX_SOCKET = os.environ.get('MYSQL_UNIX_SOCKET', '/var/run/mysqld/mysqld.sock')
    MYSQL_ADMIN_USER = os.environ.get('MYSQL_ADMIN_USER', 'pannel_admin')
    MYSQL_ADMIN_PASSWORD = os.environ.get('MYSQL_ADMIN_PASSWORD', 'StrongMySQLPass123!')

    # Web Root
    WEB_ROOT = os.environ.get('WEB_ROOT', '/var/www')

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', None)

    # Panel Metadata
    PANEL_NAME = os.environ.get('PANEL_NAME', 'VPS Panel')
    PANEL_VERSION = os.environ.get('PANEL_VERSION', '2.0.0')

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    JWT_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    """Production configuration."""
    DEBUG = False
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}
