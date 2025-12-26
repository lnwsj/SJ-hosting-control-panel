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

# ============== SSL Management (Phase 5) ==============

def enable_ssl_for_domain(domain_name):
    """Enable SSL using Certbot"""
    try:
        # Run certbot to obtain certificate
        result = subprocess.run([
            'certbot', '--nginx',
            '-d', domain_name,
            '-d', f'www.{domain_name}',
            '--non-interactive',
            '--agree-tos',
            '--email', 'admin@' + domain_name,
            '--redirect'
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            return True, "SSL certificate installed successfully"
        else:
            return False, result.stderr or "Certbot failed"
    except subprocess.TimeoutExpired:
        return False, "Certbot timed out"
    except FileNotFoundError:
        return False, "Certbot not installed"
    except Exception as e:
        return False, str(e)

def check_ssl_status(domain_name):
    """Check if domain has valid SSL certificate"""
    cert_path = f'/etc/letsencrypt/live/{domain_name}/fullchain.pem'
    return os.path.exists(cert_path)

@app.route('/domains/ssl/<domain_name>', methods=['POST'])
@login_required
def toggle_ssl(domain_name):
    """Enable SSL for a domain"""
    domains_list = load_domains()
    
    # Find domain
    domain_info = None
    for domain in domains_list:
        if domain['name'] == domain_name:
            domain_info = domain
            break
    
    if not domain_info:
        flash(f'ไม่พบโดเมน {domain_name}', 'error')
        return redirect(url_for('domains'))
    
    if domain_info.get('ssl', False):
        flash(f'โดเมน {domain_name} มี SSL อยู่แล้ว', 'info')
        return redirect(url_for('domains'))
    
    # Try to enable SSL
    success, message = enable_ssl_for_domain(domain_name)
    
    if success:
        # Update domain SSL status
        domain_info['ssl'] = True
        save_domains(domains_list)
        flash(f'เปิดใช้งาน SSL สำหรับ {domain_name} สำเร็จ!', 'success')
    else:
        flash(f'ไม่สามารถเปิด SSL ได้: {message}', 'error')
    
    return redirect(url_for('domains'))

@app.route('/ssl/renew', methods=['POST'])
@login_required
def renew_all_ssl():
    """Renew all SSL certificates"""
    try:
        result = subprocess.run(
            ['certbot', 'renew', '--quiet'],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            flash('ต่ออายุ SSL certificates สำเร็จ!', 'success')
        else:
            flash(f'เกิดข้อผิดพลาด: {result.stderr}', 'error')
    except FileNotFoundError:
        flash('Certbot ยังไม่ได้ติดตั้ง', 'error')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

# ============== Database Management (Phase 3) ==============

# Database configuration
DB_HOST = os.environ.get('DB_HOST', 'mariadb')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'SjHosting2025!')
DATABASES_FILE = '/data/databases.json'

def get_db_connection():
    """Get MySQL connection"""
    import pymysql
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def load_databases():
    """Load databases list from file"""
    if os.path.exists(DATABASES_FILE):
        with open(DATABASES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_databases(databases):
    """Save databases list to file"""
    os.makedirs(os.path.dirname(DATABASES_FILE), exist_ok=True)
    with open(DATABASES_FILE, 'w') as f:
        json.dump(databases, f, indent=2)

def create_mysql_database(db_name, db_user, db_password):
    """Create MySQL database and user"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            # Create user
            cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'%%' IDENTIFIED BY '{db_password}'")
            
            # Grant privileges
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%%'")
            
            # Flush privileges
            cursor.execute("FLUSH PRIVILEGES")
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        raise e
    finally:
        conn.close()

def delete_mysql_database(db_name, db_user):
    """Delete MySQL database and user"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Drop database
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            
            # Drop user
            cursor.execute(f"DROP USER IF EXISTS '{db_user}'@'%%'")
            
            # Flush privileges
            cursor.execute("FLUSH PRIVILEGES")
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting database: {e}")
        raise e
    finally:
        conn.close()

def generate_password(length=16):
    """Generate a random password"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@app.route('/databases')
@login_required
def databases():
    """List all databases"""
    db_list = load_databases()
    return render_template('databases.html', databases=db_list)

@app.route('/databases/create', methods=['POST'])
@login_required
def create_database():
    """Create a new database"""
    db_name = request.form.get('db_name', '').strip().lower()
    db_user = request.form.get('db_user', '').strip().lower()
    db_password = request.form.get('db_pass', '').strip()
    
    # Validation
    if not db_name or not db_user:
        flash('กรุณากรอกข้อมูลให้ครบ', 'error')
        return redirect(url_for('databases'))
    
    # Validate names (alphanumeric and underscore only)
    if not re.match(r'^[a-z0-9_]+$', db_name) or not re.match(r'^[a-z0-9_]+$', db_user):
        flash('ชื่อ Database และ User ต้องเป็นตัวอักษรภาษาอังกฤษ, ตัวเลข หรือ _ เท่านั้น', 'error')
        return redirect(url_for('databases'))
    
    # Generate password if not provided
    if not db_password:
        db_password = generate_password()
    
    # Check if database already exists
    db_list = load_databases()
    if any(d['name'] == db_name for d in db_list):
        flash(f'Database {db_name} มีอยู่แล้ว', 'error')
        return redirect(url_for('databases'))
    
    try:
        # Create in MySQL
        create_mysql_database(db_name, db_user, db_password)
        
        # Save to file
        new_db = {
            'name': db_name,
            'user': db_user,
            'password': db_password,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        db_list.append(new_db)
        save_databases(db_list)
        
        flash(f'Database {db_name} สร้างเรียบร้อยแล้ว! User: {db_user} / Password: {db_password}', 'success')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('databases'))

@app.route('/databases/delete/<db_name>', methods=['POST'])
@login_required
def delete_database(db_name):
    """Delete a database"""
    db_list = load_databases()
    
    # Find database
    db_info = None
    for i, db in enumerate(db_list):
        if db['name'] == db_name:
            db_info = db
            db_list.pop(i)
            break
    
    if not db_info:
        flash(f'ไม่พบ Database {db_name}', 'error')
        return redirect(url_for('databases'))
    
    try:
        # Delete from MySQL
        delete_mysql_database(db_name, db_info['user'])
        
        # Save updated list
        save_databases(db_list)
        
        flash(f'Database {db_name} ถูกลบแล้ว', 'success')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('databases'))

# ============== File Management (Phase 4) ==============

def get_safe_path(path):
    """Validate and return safe path within WEBSITES_DIR"""
    if not path:
        return WEBSITES_DIR
    
    # Normalize and resolve the path
    full_path = os.path.normpath(os.path.join(WEBSITES_DIR, path))
    
    # Security check: must be within WEBSITES_DIR
    if not full_path.startswith(os.path.normpath(WEBSITES_DIR)):
        return None
    
    return full_path

def get_file_info(filepath):
    """Get file/folder information"""
    stat = os.stat(filepath)
    is_dir = os.path.isdir(filepath)
    return {
        'name': os.path.basename(filepath),
        'path': os.path.relpath(filepath, WEBSITES_DIR),
        'is_dir': is_dir,
        'size': stat.st_size if not is_dir else 0,
        'size_human': format_size(stat.st_size) if not is_dir else '-',
        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
    }

def format_size(size):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

@app.route('/files')
@app.route('/files/<path:subpath>')
@login_required
def files(subpath=''):
    """File browser"""
    current_path = get_safe_path(subpath)
    
    if current_path is None or not os.path.exists(current_path):
        flash('Path not found', 'error')
        return redirect(url_for('files'))
    
    # If it's a file, return it for download
    if os.path.isfile(current_path):
        return send_file(current_path, as_attachment=True)
    
    # List directory contents
    items = []
    try:
        for name in sorted(os.listdir(current_path)):
            filepath = os.path.join(current_path, name)
            items.append(get_file_info(filepath))
    except PermissionError:
        flash('Permission denied', 'error')
    
    # Sort: directories first, then files
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    # Build breadcrumb
    breadcrumb = []
    if subpath:
        parts = subpath.split('/')
        for i, part in enumerate(parts):
            breadcrumb.append({
                'name': part,
                'path': '/'.join(parts[:i+1])
            })
    
    return render_template('files.html', 
                         items=items, 
                         current_path=subpath,
                         breadcrumb=breadcrumb)

@app.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload file"""
    current_path = request.form.get('current_path', '')
    target_dir = get_safe_path(current_path)
    
    if target_dir is None or not os.path.isdir(target_dir):
        flash('Invalid upload path', 'error')
        return redirect(url_for('files'))
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    # Secure the filename
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    if not filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    try:
        filepath = os.path.join(target_dir, filename)
        file.save(filepath)
        flash(f'อัปโหลด {filename} สำเร็จ!', 'success')
    except Exception as e:
        flash(f'Upload error: {str(e)}', 'error')
    
    return redirect(url_for('files', subpath=current_path))

@app.route('/files/create-folder', methods=['POST'])
@login_required
def create_folder():
    """Create new folder"""
    current_path = request.form.get('current_path', '')
    folder_name = request.form.get('folder_name', '').strip()
    
    if not folder_name or not re.match(r'^[a-zA-Z0-9_\-\.]+$', folder_name):
        flash('ชื่อโฟลเดอร์ไม่ถูกต้อง (ใช้ตัวอักษร, ตัวเลข, _, -, . เท่านั้น)', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    target_dir = get_safe_path(current_path)
    if target_dir is None:
        flash('Invalid path', 'error')
        return redirect(url_for('files'))
    
    new_folder = os.path.join(target_dir, folder_name)
    
    try:
        os.makedirs(new_folder, exist_ok=False)
        flash(f'สร้างโฟลเดอร์ {folder_name} สำเร็จ!', 'success')
    except FileExistsError:
        flash(f'โฟลเดอร์ {folder_name} มีอยู่แล้ว', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('files', subpath=current_path))

@app.route('/files/delete', methods=['POST'])
@login_required
def delete_file():
    """Delete file or folder"""
    import shutil
    
    file_path = request.form.get('file_path', '')
    current_path = request.form.get('current_path', '')
    
    target = get_safe_path(file_path)
    
    if target is None or not os.path.exists(target):
        flash('File not found', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    # Prevent deleting root
    if target == os.path.normpath(WEBSITES_DIR):
        flash('Cannot delete root directory', 'error')
        return redirect(url_for('files', subpath=current_path))
    
    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
            flash(f'ลบโฟลเดอร์สำเร็จ!', 'success')
        else:
            os.remove(target)
            flash(f'ลบไฟล์สำเร็จ!', 'success')
    except Exception as e:
        flash(f'Delete error: {str(e)}', 'error')
    
    return redirect(url_for('files', subpath=current_path))

@app.route('/files/download/<path:filepath>')
@login_required
def download_file(filepath):
    """Download file"""
    from flask import send_file
    
    target = get_safe_path(filepath)
    
    if target is None or not os.path.isfile(target):
        flash('File not found', 'error')
        return redirect(url_for('files'))
    
    return send_file(target, as_attachment=True)

# ============== Settings ==============

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validation
    if not current_password or not new_password or not confirm_password:
        flash('กรุณากรอกข้อมูลให้ครบ', 'error')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('รหัสผ่านใหม่ไม่ตรงกัน', 'error')
        return redirect(url_for('settings'))
    
    if len(new_password) < 6:
        flash('รหัสผ่านใหม่ต้องมีอย่างน้อย 6 ตัวอักษร', 'error')
        return redirect(url_for('settings'))
    
    # Verify current password
    users = load_users()
    username = current_user.username
    
    if username not in users:
        flash('ผู้ใช้ไม่ถูกต้อง', 'error')
        return redirect(url_for('settings'))
    
    if not check_password_hash(users[username]['password'], current_password):
        flash('รหัสผ่านปัจจุบันไม่ถูกต้อง', 'error')
        return redirect(url_for('settings'))
    
    # Update password
    users[username]['password'] = generate_password_hash(new_password)
    save_users(users)
    
    flash('เปลี่ยนรหัสผ่านสำเร็จ!', 'success')
    return redirect(url_for('settings'))

# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('error.html', 
                         error_code=404, 
                         error_message='ไม่พบหน้าที่ต้องการ'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('error.html', 
                         error_code=500, 
                         error_message='เกิดข้อผิดพลาดภายในระบบ'), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    return render_template('error.html', 
                         error_code=403, 
                         error_message='ไม่มีสิทธิ์เข้าถึง'), 403

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs('/data', exist_ok=True)
    os.makedirs(WEBSITES_DIR, exist_ok=True)
    
    # Initialize default users
    load_users()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
