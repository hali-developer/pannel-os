"""
VPS Panel — Domain Model (MySQL)
"""
from datetime import datetime
from app.extensions import db


class Domain(db.Model):
    __tablename__ = 'domains'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    domain_name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    document_root = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    ssl_enabled = db.Column(db.Boolean, default=False, nullable=False)  # Future: Certbot
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Domain {self.domain_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'domain_name': self.domain_name,
            'document_root': self.document_root,
            'is_active': self.is_active,
            'ssl_enabled': self.ssl_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'owner': self.owner.username if self.owner else None,
        }
