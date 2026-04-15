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

    # Panel Database (Using PostgreSQL for all data)
    PANEL_DB_HOST = os.environ.get('PANEL_DB_HOST', 'localhost')
    PANEL_DB_PORT = int(os.environ.get('PANEL_DB_PORT', 5432))
    PANEL_DB_USER = os.environ.get('PANEL_DB_USER', 'pannel_user')
    PANEL_DB_PASSWORD = os.environ.get('PANEL_DB_PASSWORD', 'StrongPanelPass123!')
    PANEL_DB_NAME = os.environ.get('PANEL_DB_NAME', 'pannel_db')

    # Construct PostgreSQL URI
    SQLALCHEMY_DATABASE_URI = f"postgresql://{PANEL_DB_USER}:{PANEL_DB_PASSWORD}@{PANEL_DB_HOST}:{PANEL_DB_PORT}/{PANEL_DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # Web Root
    WEB_ROOT = os.environ.get('WEB_ROOT', '/var/www')

    # PostgreSQL (Client Databases)
    POSTGRESQL_HOST = os.environ.get('POSTGRESQL_HOST', 'localhost')
    POSTGRESQL_PORT = int(os.environ.get('POSTGRESQL_PORT', 5432))
    POSTGRESQL_ADMIN_USER = os.environ.get('POSTGRESQL_ADMIN_USER', 'postgres')
    POSTGRESQL_ADMIN_PASSWORD = os.environ.get('POSTGRESQL_ADMIN_PASSWORD', 'StrongPostgresPass123!')

    # DB Password Encryption
    DB_PASSWORD_ENCRYPTION_KEY = os.environ.get('DB_PASSWORD_ENCRYPTION_KEY', None)

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', None)

    # Panel Metadata
    PANEL_NAME = os.environ.get('PANEL_NAME', 'VPS Panel')
    PANEL_VERSION = os.environ.get('PANEL_VERSION', '3.0.0')

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
    JWT_COOKIE_SECURE = False  # Set to True only when using HTTPS
    SESSION_COOKIE_SECURE = False  # Set to True only when using HTTPS
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
