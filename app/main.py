"""
SJ Panel - Custom Hosting Control Panel
Phase 1: Foundation + Phase 2: Domain Management
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psutil
import os
import json
import subprocess
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# File paths
USERS_FILE = '/data/users.json'
DOMAINS_FILE = '/data/domains.json'
WEBSITES_DIR = '/var/www'
NGINX_SITES_AVAILABLE = '/etc/nginx/sites-available'
NGINX_SITES_ENABLED = '/etc/nginx/sites-enabled'

DEFAULT_ADMIN = {
    'username': 'admin',
    'password': generate_password_hash('admin123'),
    'role': 'admin'
}

# Nginx config template
NGINX_TEMPLATE = """server {{
    listen 80;
    server_name {domain} www.{domain};
    root {document_root};
    index index.php index.html index.htm;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
    }}

    location ~ /\\.ht {{
        deny all;
    }}
}}
"""

# Default index.html for new domains
DEFAULT_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {domain}</title>
    <style>
        body {{
            font-family: 'Segoe UI', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
        }}
        h1 {{ font-size: 3rem; margin-bottom: 0.5rem; }}
        p {{ opacity: 0.8; font-size: 1.2rem; }}
        .badge {{ 
            background: rgba(255,255,255,0.2); 
            padding: 0.5rem 1rem; 
            border-radius: 2rem;
            display: inline-block;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 {domain}</h1>
        <p>Your website is ready!</p>
        <div class="badge">Powered by SJ Panel</div>
    </div>
</body>
</html>
"""

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

# ============== Helper Functions ==============

def load_users():
    """Load users from file or create default"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    else:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        save_users({'admin': DEFAULT_ADMIN})
        return {'admin': DEFAULT_ADMIN}

def save_users(users):
    """Save users to file"""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def load_domains():
    """Load domains from file"""
    if os.path.exists(DOMAINS_FILE):
        with open(DOMAINS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_domains(domains):
    """Save domains to file"""
    os.makedirs(os.path.dirname(DOMAINS_FILE), exist_ok=True)
    with open(DOMAINS_FILE, 'w') as f:
        json.dump(domains, f, indent=2)

def is_valid_domain(domain):
    """Validate domain name format"""
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$'
    return re.match(pattern, domain) is not None

def create_domain_files(domain_name):
    """Create directory structure and files for a new domain"""
    document_root = os.path.join(WEBSITES_DIR, domain_name, 'public_html')
    
    # Create document root directory
    os.makedirs(document_root, exist_ok=True)
    
    # Create default index.html
    index_path = os.path.join(document_root, 'index.html')
    if not os.path.exists(index_path):
        with open(index_path, 'w') as f:
            f.write(DEFAULT_INDEX_HTML.format(domain=domain_name))
    
    # Create Nginx config
    nginx_config = NGINX_TEMPLATE.format(domain=domain_name, document_root=document_root)
    nginx_config_path = os.path.join(NGINX_SITES_AVAILABLE, domain_name)
    
    # Ensure nginx directories exist
    os.makedirs(NGINX_SITES_AVAILABLE, exist_ok=True)
    os.makedirs(NGINX_SITES_ENABLED, exist_ok=True)
    
    with open(nginx_config_path, 'w') as f:
        f.write(nginx_config)
    
    # Create symlink to sites-enabled
    symlink_path = os.path.join(NGINX_SITES_ENABLED, domain_name)
    if not os.path.exists(symlink_path):
        os.symlink(nginx_config_path, symlink_path)
    
    return document_root

def delete_domain_files(domain_name):
    """Delete domain files and nginx config"""
    import shutil
    
    # Remove nginx symlink
    symlink_path = os.path.join(NGINX_SITES_ENABLED, domain_name)
    if os.path.exists(symlink_path):
        os.remove(symlink_path)
    
    # Remove nginx config
    nginx_config_path = os.path.join(NGINX_SITES_AVAILABLE, domain_name)
    if os.path.exists(nginx_config_path):
        os.remove(nginx_config_path)
    
    # Optionally remove website files (commented out for safety)
    # website_dir = os.path.join(WEBSITES_DIR, domain_name)
    # if os.path.exists(website_dir):
    #     shutil.rmtree(website_dir)

def reload_nginx():
    """Reload nginx configuration"""
    try:
        subprocess.run(['nginx', '-t'], check=True, capture_output=True)
        subprocess.run(['nginx', '-s', 'reload'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        # Nginx not installed in this container, skip
        return True

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
        'hostname': os.uname().nodename if hasattr(os, 'uname') else 'localhost',
        'domain_count': len(load_domains())
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
    domain_list = load_domains()
    return render_template('domains.html', domains=domain_list)

@app.route('/domains/add', methods=['GET', 'POST'])
@login_required
def add_domain():
    """Add new domain"""
    if request.method == 'POST':
        domain_name = request.form.get('domain_name', '').strip().lower()
        enable_ssl = request.form.get('enable_ssl') == 'on'
        
        # Validate domain name
        if not domain_name:
            flash('กรุณากรอกชื่อโดเมน', 'error')
            return render_template('add_domain.html')
        
        if not is_valid_domain(domain_name):
            flash('รูปแบบโดเมนไม่ถูกต้อง', 'error')
            return render_template('add_domain.html')
        
        # Check if domain already exists
        domains_list = load_domains()
        if any(d['name'] == domain_name for d in domains_list):
            flash(f'โดเมน {domain_name} มีอยู่แล้ว', 'error')
            return render_template('add_domain.html')
        
        try:
            # Create domain files and nginx config
            document_root = create_domain_files(domain_name)
            
            # Reload nginx
            reload_nginx()
            
            # Save to domains list
            new_domain = {
                'name': domain_name,
                'path': document_root,
                'ssl': False,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'status': 'active'
            }
            domains_list.append(new_domain)
            save_domains(domains_list)
            
            flash(f'โดเมน {domain_name} ถูกเพิ่มเรียบร้อยแล้ว!', 'success')
            return redirect(url_for('domains'))
            
        except Exception as e:
            flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
            return render_template('add_domain.html')
    
    return render_template('add_domain.html')

@app.route('/domains/delete/<domain_name>', methods=['POST'])
@login_required
def delete_domain(domain_name):
    """Delete a domain"""
    domains_list = load_domains()
    
    # Find and remove domain
    domain_found = False
    for i, domain in enumerate(domains_list):
        if domain['name'] == domain_name:
            domains_list.pop(i)
            domain_found = True
            break
    
    if not domain_found:
        flash(f'ไม่พบโดเมน {domain_name}', 'error')
        return redirect(url_for('domains'))
    
    try:
        # Delete nginx config (but keep website files for safety)
        delete_domain_files(domain_name)
        reload_nginx()
        
        # Save updated domains list
        save_domains(domains_list)
        
        flash(f'โดเมน {domain_name} ถูกลบแล้ว', 'success')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('domains'))

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
    os.makedirs(WEBSITES_DIR, exist_ok=True)
    
    # Initialize default users
    load_users()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
