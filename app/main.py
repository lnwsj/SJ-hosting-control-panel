"""
SJ Panel - Custom Hosting Control Panel
Phase 1: Foundation
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psutil
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple user storage (will be replaced with DB later)
USERS_FILE = '/data/users.json'
DEFAULT_ADMIN = {
    'username': 'admin',
    'password': generate_password_hash('admin123'),
    'role': 'admin'
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

def load_users():
    """Load users from file or create default"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    else:
        # Create default admin
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        save_users({'admin': DEFAULT_ADMIN})
        return {'admin': DEFAULT_ADMIN}

def save_users(users):
    """Save users to file"""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        return User(username)
    return None

# ============== Routes ==============

@app.route('/')
@login_required
def dashboard():
    """Main dashboard with server stats"""
    stats = {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory': psutil.virtual_memory(),
        'disk': psutil.disk_usage('/'),
        'hostname': os.uname().nodename if hasattr(os, 'uname') else 'localhost'
    }
    return render_template('dashboard.html', stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users()
        if username in users and check_password_hash(users[username]['password'], password):
            user = User(username)
            login_user(user)
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('ออกจากระบบแล้ว', 'info')
    return redirect(url_for('login'))

# ============== Domain Management (Phase 2) ==============

@app.route('/domains')
@login_required
def domains():
    """List all domains"""
    # TODO: Load from database
    domain_list = []
    return render_template('domains.html', domains=domain_list)

@app.route('/domains/add', methods=['GET', 'POST'])
@login_required
def add_domain():
    """Add new domain"""
    if request.method == 'POST':
        domain_name = request.form.get('domain_name')
        # TODO: Implement domain creation logic
        flash(f'โดเมน {domain_name} ถูกเพิ่มแล้ว', 'success')
        return redirect(url_for('domains'))
    return render_template('add_domain.html')

# ============== Database Management (Phase 3) ==============

@app.route('/databases')
@login_required
def databases():
    """List all databases"""
    # TODO: Load from MySQL
    db_list = []
    return render_template('databases.html', databases=db_list)

# ============== File Management (Phase 4) ==============

@app.route('/files')
@login_required
def files():
    """File browser"""
    # TODO: Implement file browser
    return render_template('files.html')

# ============== Settings ==============

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    return render_template('settings.html')

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs('/data', exist_ok=True)
    
    # Initialize default users
    load_users()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
