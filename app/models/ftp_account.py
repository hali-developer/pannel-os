"""
VPS Panel — FTP Account Model (MySQL)
"""
from datetime import datetime
from app.extensions import db


class FTPAccount(db.Model):
    __tablename__ = 'ftp_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    ftp_username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    home_directory = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<FTPAccount {self.ftp_username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ftp_username': self.ftp_username,
            'home_directory': self.home_directory,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'owner': self.owner.username if self.owner else None,
        }
