"""
VPS Panel — Email Account Model (MySQL)
"""
from datetime import datetime
from app.extensions import db


class EmailAccount(db.Model):
    __tablename__ = 'email_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    
    email_user = db.Column(db.String(100), nullable=False)  # 'info' from info@domain.com
    email_address = db.Column(db.String(255), unique=True, nullable=False, index=True)  # info@domain.com
    password_hash = db.Column(db.String(255), nullable=False)
    
    quota_mb = db.Column(db.Integer, default=1024, nullable=False)  # Default 1GB
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    domain = db.relationship('Domain', backref=db.backref('email_accounts', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<EmailAccount {self.email_address}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'domain_id': self.domain_id,
            'email_user': self.email_user,
            'email_address': self.email_address,
            'quota_mb': self.quota_mb,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'domain_name': self.domain.domain_name if self.domain else None,
            'owner': self.owner.username if self.owner else None,
        }
