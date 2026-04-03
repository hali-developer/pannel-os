import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
from ftp_manager import FTPManager
from db_manager import DBManager

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/')
def index():
    if 'user' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Mock Admin auth
    if username == 'admin' and password == 'admin':
        session['user'] = username
        session['role'] = 'admin'
        return redirect(url_for('admin'))
    # Mock Client auth (accepts any other credentials for now)
    elif username and password:
        session['user'] = username
        session['role'] = 'client'
        return redirect(url_for('dashboard'))
        
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session.get('role') != 'client':
        return redirect(url_for('index'))
    
    # Simulate DB lookup for domain based on user session
    simulated_domain = f"{session['user']}.com"
    
    return render_template('dashboard.html', 
                           username=session['user'],
                           domain=simulated_domain,
                           db_name=f"{session['user']}_db",
                           db_user=f"{session['user']}_user")

@app.route('/admin')
def admin():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin.html')

@app.route('/admin/ftp', methods=['GET', 'POST'])
def admin_ftp():
    if 'user' not in session or session.get('role') != 'admin':
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
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    message = None
    if request.method == 'POST':
        action = request.form.get('action') 
        
        if action == 'create':
            n_db = request.form.get('db_name')
            n_usr = request.form.get('db_user')
            n_pwd = request.form.get('new_password')
            if n_db and n_usr and n_pwd:
                succ, msg, db_name, db_user = DBManager.create_database(n_db, n_usr, n_pwd)
                message = f"Success! DB: {db_name}" if succ else f"Error: {msg}"
                
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
                
        elif action == 'sync_os':
            succ, msg = DBManager.sync_os_dbs()
            message = "Success! " + msg if succ else "Error: " + msg

    dbs_list = DBManager.get_all_databases()
    return render_template('admin_db.html', message=message, dbs=dbs_list)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
