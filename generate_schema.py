import sys
import os

# Add the project root to the python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db

# Import all models to ensure they are registered with SQLAlchemy
from app.models.user import User
from app.models.domain import Domain
from app.models.ftp_account import FTPAccount
from app.models.database import ClientDatabase
from app.models.db_user import DbUser
from app.models.db_user_permission import DbUserPermission
from app.models.activity_log import ActivityLog

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

app = create_app('development')
with app.app_context():
    with open('schema.sql', 'w') as f:
        # Create all tables (mock engine)
        from sqlalchemy import create_mock_engine

        def dump(sql, *multiparams, **params):
            f.write(str(sql.compile(dialect=postgresql.dialect())).strip() + ";\n\n")

        engine = create_mock_engine('postgresql://', dump)
        db.metadata.create_all(engine, checkfirst=True)
