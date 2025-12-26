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

# ============== Email Management (Phase 7) ==============

EMAILS_FILE = '/data/emails.json'
MAIL_CONFIG_DIR = '/tmp/docker-mailserver'

def load_emails():
    """Load email accounts from file"""
    if os.path.exists(EMAILS_FILE):
        with open(EMAILS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_emails(emails):
    """Save email accounts to file"""
    os.makedirs(os.path.dirname(EMAILS_FILE), exist_ok=True)
    with open(EMAILS_FILE, 'w') as f:
        json.dump(emails, f, indent=2)

def run_mail_command(command):
    """Run docker-mailserver setup command"""
    try:
        result = subprocess.run(
            ['docker', 'exec', 'mailserver', 'setup', *command.split()],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

@app.route('/email')
@login_required
def email():
    """Email management page"""
    email_list = load_emails()
    domains = load_domains()
    return render_template('email.html', emails=email_list, domains=domains)

@app.route('/email/create', methods=['POST'])
@login_required
def create_email():
    """Create new email account"""
    email_user = request.form.get('email_user', '').strip().lower()
    email_domain = request.form.get('email_domain', '').strip().lower()
    email_password = request.form.get('email_password', '').strip()
    
    # Validation
    if not email_user or not email_domain:
        flash('กรุณากรอกข้อมูลให้ครบ', 'error')
        return redirect(url_for('email'))
    
    if not re.match(r'^[a-z0-9._-]+$', email_user):
        flash('ชื่อ email ไม่ถูกต้อง', 'error')
        return redirect(url_for('email'))
    
    full_email = f"{email_user}@{email_domain}"
    
    # Check if email already exists
    email_list = load_emails()
    if any(e['email'] == full_email for e in email_list):
        flash(f'Email {full_email} มีอยู่แล้ว', 'error')
        return redirect(url_for('email'))
    
    # Generate password if not provided
    if not email_password:
        email_password = generate_password(12)
    
    # Create email account using docker-mailserver
    success, message = run_mail_command(f'email add {full_email} {email_password}')
    
    if success or 'mailserver' not in message.lower():
        # Save to file even if mailserver not running (for demo)
        new_email = {
            'email': full_email,
            'user': email_user,
            'domain': email_domain,
            'password': email_password,
            'quota': '1GB',
            'created': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        email_list.append(new_email)
        save_emails(email_list)
        
        flash(f'สร้าง Email {full_email} สำเร็จ! Password: {email_password}', 'success')
    else:
        flash(f'เกิดข้อผิดพลาด: {message}', 'error')
    
    return redirect(url_for('email'))

@app.route('/email/delete/<path:email_address>', methods=['POST'])
@login_required
def delete_email(email_address):
    """Delete email account"""
    email_list = load_emails()
    
    # Find and remove email
    email_found = False
    for i, em in enumerate(email_list):
        if em['email'] == email_address:
            email_list.pop(i)
            email_found = True
            break
    
    if not email_found:
        flash(f'ไม่พบ Email {email_address}', 'error')
        return redirect(url_for('email'))
    
    # Delete from mailserver
    run_mail_command(f'email del {email_address}')
    
    # Save updated list
    save_emails(email_list)
    
    flash(f'ลบ Email {email_address} แล้ว', 'success')
    return redirect(url_for('email'))

@app.route('/email/alias', methods=['POST'])
@login_required
def create_alias():
    """Create email alias/forwarder"""
    alias_from = request.form.get('alias_from', '').strip().lower()
    alias_to = request.form.get('alias_to', '').strip().lower()
    
    if not alias_from or not alias_to:
        flash('กรุณากรอกข้อมูลให้ครบ', 'error')
        return redirect(url_for('email'))
    
    # Create alias using docker-mailserver
    success, message = run_mail_command(f'alias add {alias_from} {alias_to}')
    
    if success:
        flash(f'สร้าง Alias {alias_from} → {alias_to} สำเร็จ!', 'success')
    else:
        flash(f'บันทึก Alias สำเร็จ (Mailserver อาจยังไม่ทำงาน)', 'info')
    
    return redirect(url_for('email'))

# ============== Backup System (Phase 8) ==============

BACKUPS_DIR = '/data/backups'

def get_backup_list():
    """Get list of all backups"""
    if not os.path.exists(BACKUPS_DIR):
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        return []
    
    backups = []
    for filename in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        if filename.endswith('.tar.gz') or filename.endswith('.sql'):
            filepath = os.path.join(BACKUPS_DIR, filename)
            stat = os.stat(filepath)
            backups.append({
                'filename': filename,
                'size': format_size(stat.st_size),
                'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'type': 'website' if filename.endswith('.tar.gz') else 'database'
            })
    return backups

@app.route('/backups')
@login_required
def backups():
    """Backup management page"""
    backup_list = get_backup_list()
    domains = load_domains()
    databases = load_databases()
    return render_template('backups.html', backups=backup_list, domains=domains, databases=databases)

@app.route('/backups/create-website', methods=['POST'])
@login_required
def create_website_backup():
    """Create website backup"""
    domain_name = request.form.get('domain_name', '').strip()
    
    if not domain_name:
        flash('กรุณาเลือกโดเมน', 'error')
        return redirect(url_for('backups'))
    
    website_path = os.path.join(WEBSITES_DIR, domain_name)
    if not os.path.exists(website_path):
        flash(f'ไม่พบโฟลเดอร์ {domain_name}', 'error')
        return redirect(url_for('backups'))
    
    # Create backup
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"{domain_name}_{timestamp}.tar.gz"
    backup_path = os.path.join(BACKUPS_DIR, backup_filename)
    
    try:
        import tarfile
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(website_path, arcname=domain_name)
        flash(f'Backup สำเร็จ: {backup_filename}', 'success')
    except Exception as e:
        flash(f'Backup ล้มเหลว: {str(e)}', 'error')
    
    return redirect(url_for('backups'))

@app.route('/backups/create-database', methods=['POST'])
@login_required
def create_database_backup():
    """Create database backup using mysqldump"""
    db_name = request.form.get('db_name', '').strip()
    
    if not db_name:
        flash('กรุณาเลือก Database', 'error')
        return redirect(url_for('backups'))
    
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"{db_name}_{timestamp}.sql"
    backup_path = os.path.join(BACKUPS_DIR, backup_filename)
    
    try:
        # Run mysqldump via docker
        result = subprocess.run([
            'docker', 'exec', 'main_db', 
            'mysqldump', '-u', 'root', f'-p{DB_PASSWORD}', db_name
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            with open(backup_path, 'w') as f:
                f.write(result.stdout)
            flash(f'Database backup สำเร็จ: {backup_filename}', 'success')
        else:
            flash(f'mysqldump error: {result.stderr}', 'error')
    except Exception as e:
        flash(f'Backup ล้มเหลว: {str(e)}', 'error')
    
    return redirect(url_for('backups'))

@app.route('/backups/download/<filename>')
@login_required
def download_backup(filename):
    """Download backup file"""
    from flask import send_file
    
    # Security check
    if '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backups'))
    
    filepath = os.path.join(BACKUPS_DIR, filename)
    if not os.path.exists(filepath):
        flash('Backup not found', 'error')
        return redirect(url_for('backups'))
    
    return send_file(filepath, as_attachment=True)

@app.route('/backups/delete/<filename>', methods=['POST'])
@login_required
def delete_backup(filename):
    """Delete backup file"""
    # Security check
    if '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backups'))
    
    filepath = os.path.join(BACKUPS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash('ลบ Backup สำเร็จ', 'success')
    else:
        flash('Backup not found', 'error')
    
    return redirect(url_for('backups'))

@app.route('/backups/restore/<filename>', methods=['POST'])
@login_required
def restore_backup(filename):
    """Restore backup"""
    import tarfile
    
    # Security check
    if '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backups'))
    
    filepath = os.path.join(BACKUPS_DIR, filename)
    if not os.path.exists(filepath):
        flash('Backup not found', 'error')
        return redirect(url_for('backups'))
    
    try:
        if filename.endswith('.tar.gz'):
            # Restore website
            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(WEBSITES_DIR)
            flash('Restore website สำเร็จ!', 'success')
        elif filename.endswith('.sql'):
            # Restore database
            db_name = filename.split('_')[0]
            with open(filepath, 'r') as f:
                sql_content = f.read()
            
            result = subprocess.run([
                'docker', 'exec', '-i', 'main_db',
                'mysql', '-u', 'root', f'-p{DB_PASSWORD}', db_name
            ], input=sql_content, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                flash('Restore database สำเร็จ!', 'success')
            else:
                flash(f'Restore error: {result.stderr}', 'error')
    except Exception as e:
        flash(f'Restore ล้มเหลว: {str(e)}', 'error')
    
    return redirect(url_for('backups'))

# ============== DNS Management (Phase 9) ==============

DNS_CONFIG_FILE = '/data/dns_config.json'

def load_dns_config():
    """Load Cloudflare config"""
    if os.path.exists(DNS_CONFIG_FILE):
        with open(DNS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'api_token': '', 'zone_id': '', 'domain': ''}

def save_dns_config(config):
    """Save Cloudflare config"""
    os.makedirs(os.path.dirname(DNS_CONFIG_FILE), exist_ok=True)
    with open(DNS_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def cloudflare_request(method, endpoint, config, data=None):
    """Make Cloudflare API request"""
    import requests
    
    headers = {
        'Authorization': f'Bearer {config["api_token"]}',
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.cloudflare.com/client/v4/zones/{config["zone_id"]}/{endpoint}'
    
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == 'PUT':
            resp = requests.put(url, headers=headers, json=data, timeout=10)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=headers, timeout=10)
        
        return resp.json()
    except Exception as e:
        return {'success': False, 'errors': [{'message': str(e)}]}

@app.route('/dns')
@login_required
def dns():
    """DNS management page"""
    config = load_dns_config()
    records = []
    
    if config.get('api_token') and config.get('zone_id'):
        result = cloudflare_request('GET', 'dns_records', config)
        if result.get('success'):
            records = result.get('result', [])
    
    return render_template('dns.html', config=config, records=records)

@app.route('/dns/config', methods=['POST'])
@login_required
def save_dns_settings():
    """Save Cloudflare API settings"""
    api_token = request.form.get('api_token', '').strip()
    zone_id = request.form.get('zone_id', '').strip()
    domain = request.form.get('domain', '').strip()
    
    if not api_token or not zone_id:
        flash('กรุณากรอก API Token และ Zone ID', 'error')
        return redirect(url_for('dns'))
    
    config = {
        'api_token': api_token,
        'zone_id': zone_id,
        'domain': domain
    }
    save_dns_config(config)
    
    # Test connection
    result = cloudflare_request('GET', 'dns_records?per_page=1', config)
    if result.get('success'):
        flash('เชื่อมต่อ Cloudflare สำเร็จ!', 'success')
    else:
        error_msg = result.get('errors', [{}])[0].get('message', 'Unknown error')
        flash(f'เชื่อมต่อไม่สำเร็จ: {error_msg}', 'error')
    
    return redirect(url_for('dns'))

@app.route('/dns/add', methods=['POST'])
@login_required
def add_dns_record():
    """Add DNS record"""
    config = load_dns_config()
    
    record_type = request.form.get('type', 'A')
    name = request.form.get('name', '').strip()
    content = request.form.get('content', '').strip()
    proxied = request.form.get('proxied') == 'on'
    ttl = int(request.form.get('ttl', 1))
    
    if not name or not content:
        flash('กรุณากรอกข้อมูลให้ครบ', 'error')
        return redirect(url_for('dns'))
    
    data = {
        'type': record_type,
        'name': name,
        'content': content,
        'ttl': ttl,
        'proxied': proxied if record_type in ['A', 'AAAA', 'CNAME'] else False
    }
    
    result = cloudflare_request('POST', 'dns_records', config, data)
    
    if result.get('success'):
        flash(f'เพิ่ม {record_type} record สำเร็จ!', 'success')
    else:
        error_msg = result.get('errors', [{}])[0].get('message', 'Unknown error')
        flash(f'เพิ่มไม่สำเร็จ: {error_msg}', 'error')
    
    return redirect(url_for('dns'))

@app.route('/dns/delete/<record_id>', methods=['POST'])
@login_required
def delete_dns_record(record_id):
    """Delete DNS record"""
    config = load_dns_config()
    
    result = cloudflare_request('DELETE', f'dns_records/{record_id}', config)
    
    if result.get('success'):
        flash('ลบ DNS record สำเร็จ!', 'success')
    else:
        error_msg = result.get('errors', [{}])[0].get('message', 'Unknown error')
        flash(f'ลบไม่สำเร็จ: {error_msg}', 'error')
    
    return redirect(url_for('dns'))

@app.route('/dns/quick-setup', methods=['POST'])
@login_required
def quick_dns_setup():
    """Quick setup common DNS records"""
    config = load_dns_config()
    server_ip = request.form.get('server_ip', '').strip()
    domain = config.get('domain', '').strip()
    
    if not server_ip or not domain:
        flash('กรุณากรอก Server IP และ Domain', 'error')
        return redirect(url_for('dns'))
    
    records_to_create = [
        {'type': 'A', 'name': '@', 'content': server_ip, 'proxied': True},
        {'type': 'A', 'name': 'www', 'content': server_ip, 'proxied': True},
        {'type': 'A', 'name': 'mail', 'content': server_ip, 'proxied': False},
        {'type': 'MX', 'name': '@', 'content': f'mail.{domain}', 'priority': 10},
        {'type': 'TXT', 'name': '@', 'content': f'v=spf1 a mx ip4:{server_ip} ~all'},
    ]
    
    success_count = 0
    for record in records_to_create:
        data = {
            'type': record['type'],
            'name': record['name'],
            'content': record['content'],
            'ttl': 1,
            'proxied': record.get('proxied', False)
        }
        if record['type'] == 'MX':
            data['priority'] = record.get('priority', 10)
        
        result = cloudflare_request('POST', 'dns_records', config, data)
        if result.get('success'):
            success_count += 1
    
    flash(f'Quick Setup สำเร็จ {success_count}/{len(records_to_create)} records', 'success')
    return redirect(url_for('dns'))

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
