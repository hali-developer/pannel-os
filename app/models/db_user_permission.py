"""
VPS Panel — Database User Permission Model (MySQL)

Maps which db_users have access to which databases.
One db_user can access multiple databases.
One database can be accessed by multiple db_users.
"""
from datetime import datetime
from app.extensions import db


class DbUserPermission(db.Model):
    __tablename__ = 'db_user_permissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    db_user_id = db.Column(db.Integer, db.ForeignKey('db_users.id', ondelete='CASCADE'), nullable=False, index=True)
    db_id = db.Column(db.Integer, db.ForeignKey('client_databases.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint: one permission entry per (db_user, database) pair
    __table_args__ = (
        db.UniqueConstraint('db_user_id', 'db_id', name='uq_dbuser_db'),
    )

    # Relationships
    database = db.relationship('ClientDatabase', backref=db.backref('permissions', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<DbUserPermission db_user_id={self.db_user_id} db_id={self.db_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'db_user_id': self.db_user_id,
            'db_id': self.db_id,
            'db_username': self.db_user.db_username if self.db_user else None,
            'db_name': self.database.db_name if self.database else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
