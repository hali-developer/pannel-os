import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from ftp_manager import FTPManager
from db_manager import DBManager

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database and create default admin if not exists
with app.app_context():
    DBManager.init_db()
    conn = DBManager._get_connection(db=Config.PANEL_DB_NAME)
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username='admin'")
                if not cursor.fetchone():
                    pwd_hash = generate_password_hash('admin')
                    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')", (pwd_hash,))
                    conn.commit()
        finally:
            conn.close()

def get_user_by_username(username):
    conn = DBManager._get_connection(db=Config.PANEL_DB_NAME)
    if not conn: return None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            return cursor.fetchone()
    finally:
        conn.close()

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user'] = user['username']
        session['role'] = user['role']
        
        if user['role'] == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
        
    # Invalid credentials
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('index'))
        
    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create_db':
            n_db = request.form.get('db_name')
            n_usr = request.form.get('db_user')
            n_pwd = request.form.get('new_password')
            if n_db and n_usr and n_pwd:
                # Force prefix for some isolation based on username
                prefix = f"{session['user']}_"
                if not n_db.startswith(prefix): n_db = prefix + n_db
                if not n_usr.startswith(prefix): n_usr = prefix + n_usr
                
                succ, msg, db_name, db_user = DBManager.create_database(session['user_id'], n_db, n_usr, n_pwd)
                message = f"Success! DB: {db_name}" if succ else f"Error: {msg}"

    user_dbs = DBManager.get_user_databases(session['user_id'])
    simulated_domain = f"{session['user']}.com"
    
    return render_template('dashboard.html', 
                           username=session['user'],
                           domain=simulated_domain,
                           dbs=user_dbs,
                           message=message)

@app.route('/admin')
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin.html')

# Quick endpoint to create clients from admin
@app.route('/admin/users', methods=['POST'])
def admin_create_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Unauthorized"
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        pwd_hash = generate_password_hash(password)
        conn = DBManager._get_connection(db=Config.PANEL_DB_NAME)
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'client')", (username, pwd_hash))
                    conn.commit()
            except Exception as e:
                pass
            finally:
                conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/ftp', methods=['GET', 'POST'])
def admin_ftp():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    message = None
    if request.method == 'POST':
        action = request.form.get('action') 
        
        if action == 'create':
            n_usr = request.form.get('new_username')
            n_pwd = request.form.get('new_password')
            d_name = request.form.get('domain_name')
            if n_usr and n_pwd and d_name:
                succ, msg = FTPManager.create_user(n_usr, n_pwd, d_name)
                message = "Success! " + msg if succ else "Error: " + msg
                
        elif action == 'delete':
            tgt_usr = request.form.get('target_username')
            if tgt_usr:
                succ, msg = FTPManager.delete_user(tgt_usr)
                message = "Success! " + msg if succ else "Error: " + msg
                
        elif action == 'update_pwd':
            tgt_usr = request.form.get('target_username')
            new_pwd = request.form.get('new_password')
            if tgt_usr and new_pwd:
                succ, msg = FTPManager.change_password(tgt_usr, new_pwd)
                message = "Success! " + msg if succ else "Error: " + msg
                
        elif action == 'update_domain':
            tgt_usr = request.form.get('target_username')
            new_domain = request.form.get('new_domain')
            if tgt_usr and new_domain:
                succ, msg = FTPManager.update_domain_path(tgt_usr, new_domain)
                message = "Success! " + msg if succ else "Error: " + msg
                
        elif action == 'sync_os':
            succ, msg = FTPManager.sync_os_users()
            message = "Success! " + msg if succ else "Error: " + msg

    users_list = FTPManager.get_all_users()
    return render_template('admin_ftp.html', message=message, users=users_list)

@app.route('/admin/db', methods=['GET', 'POST'])
def admin_db():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    message = None
    if request.method == 'POST':
        action = request.form.get('action') 
        
        if action == 'create':
            n_db = request.form.get('db_name')
            n_usr = request.form.get('db_user')
            n_pwd = request.form.get('new_password')
            target_username = request.form.get('target_client_username')
            
            client = get_user_by_username(target_username)
            if client and n_db and n_usr and n_pwd:
                succ, msg, db_name, db_user = DBManager.create_database(client['id'], n_db, n_usr, n_pwd)
                message = f"Success! DB: {db_name}" if succ else f"Error: {msg}"
            else:
                message = "Error: Invalid client username or missing fields."
                
        elif action == 'delete':
            tgt_db = request.form.get('target_db_name')
            tgt_usr = request.form.get('target_db_user')
            if tgt_db and tgt_usr:
                succ, msg = DBManager.delete_database(tgt_db, tgt_usr)
                message = "Success! " + msg if succ else "Error: " + msg
                
        elif action == 'update_user':
            tgt_db = request.form.get('target_db_name')
            new_usr = request.form.get('new_db_user')
            new_pwd = request.form.get('new_password')
            if tgt_db and new_usr and new_pwd:
                succ, msg = DBManager.assign_user_to_db(tgt_db, new_usr, new_pwd)
                message = "Success! " + msg if succ else "Error: " + msg

    dbs_list = DBManager.get_all_databases()
    return render_template('admin_db.html', message=message, dbs=dbs_list)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
