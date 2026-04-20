"""
VPS Panel — Database User Model (MySQL)

Tracks MySQL users provisioned for clients.
Each db_user can be granted access to multiple databases.
"""
from datetime import datetime
from app.extensions import db


class DbUser(db.Model):
    __tablename__ = 'db_users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    db_username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    db_type = db.Column(db.String(20), default='postgres', nullable=False)  # 'postgres' or 'mysql'
    db_password_encrypted = db.Column(db.String(512), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    db_host = db.Column(db.String(255), default='localhost', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship('DbUserPermission', backref='db_user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DbUser {self.db_username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'db_username': self.db_username,
            'owner_user_id': self.owner_user_id,
            'db_host': self.db_host,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'owner': self.owner.username if self.owner else None,
            'granted_databases': [p.database.db_name for p in self.permissions.all() if p.database],
        }
