"""
VPS Panel — User Model (PostgreSQL)
"""
from datetime import datetime
from app.extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(10), nullable=False, default='client')  # 'admin' or 'client'
    home_directory = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    domains = db.relationship('Domain', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    ftp_accounts = db.relationship('FTPAccount', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    databases = db.relationship('ClientDatabase', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='actor', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'home_directory': self.home_directory,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'domains_count': self.domains.count(),
            'ftp_accounts_count': self.ftp_accounts.count(),
            'databases_count': self.databases.count(),
        }
