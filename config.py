import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-panel-key'
    # MySQL connection string defaults
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    PANEL_DB_NAME = os.environ.get('PANEL_DB_NAME', 'panel_db')
