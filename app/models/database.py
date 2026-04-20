"""
VPS Panel — Client Database Model (MySQL)

Tracks MySQL databases provisioned for each client user.
"""
from datetime import datetime
from app.extensions import db


class ClientDatabase(db.Model):
    __tablename__ = 'client_databases'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    db_name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    db_type = db.Column(db.String(20), default='postgres', nullable=False)  # 'postgres' or 'mysql'
    db_user = db.Column(db.String(32), nullable=False)
    db_host = db.Column(db.String(255), default='localhost', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def granted_users(self):
        """List of db_usernames that have been granted access to this database."""
        return [p.db_user.db_username for p in self.permissions.all() if p.db_user]

    def __repr__(self):
        return f'<ClientDatabase {self.db_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'db_name': self.db_name,
            'db_type': self.db_type,
            'db_user': self.db_user,
            'db_host': self.db_host,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'owner': self.owner.username if self.owner else None,
            'granted_users': [p.db_user.db_username for p in self.permissions.all() if p.db_user],
        }
