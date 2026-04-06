"""
VPS Panel — Shared Extension Instances

These are initialized here so they can be imported across modules
without circular imports. They get bound to the actual app in create_app().
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
