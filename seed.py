#!/usr/bin/env python3
"""
VPS Panel — Database Seeder

Creates demo client accounts and provisions sample databases.
Run after setup to populate the panel with test data.

Usage: python seed.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure we can import the app
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.domain import Domain
from app.models.ftp_account import FTPAccount
from app.models.database import ClientDatabase
from app.modules.users.services import create_user


def seed():
    app = create_app('development')

    with app.app_context():
        print("🌱 VPS Panel Seeder")
        print("=" * 50)

        # ── Seed Client Users ──
        print("\n📦 Creating demo client accounts...")
        clients = [
            {"username": "demo_client_a", "password": "password123", "email": "clienta@example.com"},
            {"username": "demo_client_b", "password": "password456", "email": "clientb@example.com"},
        ]

        for client in clients:
            existing = User.query.filter_by(username=client['username']).first()
            if existing:
                print(f"  ℹ️  User '{client['username']}' already exists.")
                continue

            ok, msg, user = create_user(
                client['username'],
                client['password'],
                role='client',
                email=client['email'],
            )
            if ok:
                print(f"  ✅ Created user: {client['username']} (password: {client['password']})")
            else:
                print(f"  ❌ Failed: {msg}")

        # ── Seed Domains ──
        print("\n🌍 Creating demo domains...")
        demo_domains = [
            {"username": "demo_client_a", "domain": "clienta.example.com"},
            {"username": "demo_client_b", "domain": "clientb.example.com"},
        ]

        for dd in demo_domains:
            user = User.query.filter_by(username=dd['username']).first()
            if not user:
                continue

            existing = Domain.query.filter_by(domain_name=dd['domain']).first()
            if existing:
                print(f"  ℹ️  Domain '{dd['domain']}' already exists.")
                continue

            domain = Domain(
                user_id=user.id,
                domain_name=dd['domain'],
                document_root=os.path.join(user.home_directory or '/var/www/' + user.username, 'public_html'),
                is_active=True,
            )
            db.session.add(domain)
            print(f"  ✅ Domain: {dd['domain']} → {user.username}")

        # ── Seed FTP Accounts ──
        print("\n📂 Creating demo FTP accounts...")
        demo_ftp = [
            {"username": "demo_client_a", "ftp_user": "ftp_clienta"},
            {"username": "demo_client_b", "ftp_user": "ftp_clientb"},
        ]

        for df in demo_ftp:
            user = User.query.filter_by(username=df['username']).first()
            if not user:
                continue

            existing = FTPAccount.query.filter_by(ftp_username=df['ftp_user']).first()
            if existing:
                print(f"  ℹ️  FTP account '{df['ftp_user']}' already exists.")
                continue

            acct = FTPAccount(
                user_id=user.id,
                ftp_username=df['ftp_user'],
                home_directory=user.home_directory or f"/var/www/{user.username}",
                is_active=True,
            )
            db.session.add(acct)
            print(f"  ✅ FTP: {df['ftp_user']} → {user.username}")

        # ── Seed Database Records (panel-side only, no real MySQL) ──
        print("\n🗄️  Creating demo database records...")
        demo_dbs = [
            {"username": "demo_client_a", "db_name": "demo_client_a_wp", "db_user": "demo_client_a_usr"},
            {"username": "demo_client_b", "db_name": "demo_client_b_shop", "db_user": "demo_client_b_usr"},
        ]

        for dd in demo_dbs:
            user = User.query.filter_by(username=dd['username']).first()
            if not user:
                continue

            existing = ClientDatabase.query.filter_by(db_name=dd['db_name']).first()
            if existing:
                print(f"  ℹ️  Database '{dd['db_name']}' already exists.")
                continue

            record = ClientDatabase(
                user_id=user.id,
                db_name=dd['db_name'],
                db_user=dd['db_user'],
                db_host='localhost',
            )
            db.session.add(record)
            print(f"  ✅ DB: {dd['db_name']} (user: {dd['db_user']}) → {user.username}")

        db.session.commit()

        print("\n" + "=" * 50)
        print("🎉 Seeding complete!")
        print("\nDefault login credentials:")
        print("  Admin:    admin / admin")
        print("  Client A: demo_client_a / password123")
        print("  Client B: demo_client_b / password456")


if __name__ == '__main__':
    seed()
