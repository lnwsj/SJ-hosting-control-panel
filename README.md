# SJ Panel - Custom Hosting Control Panel

A lightweight, Docker-based web hosting control panel inspired by DirectAdmin. Built with Flask and modern Bootstrap 5 UI.

![SJ Panel](https://img.shields.io/badge/version-1.0-blue) ![Python](https://img.shields.io/badge/python-3.11-green) ![Docker](https://img.shields.io/badge/docker-ready-blue)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🌐 **Domain Management** | Add/delete domains with automatic Nginx config generation |
| 🗄️ **Database Management** | Create/delete MySQL databases and users |
| 📁 **File Manager** | Browse, upload, download, delete files via web UI |
| 🔒 **SSL Certificates** | One-click Let's Encrypt SSL with Certbot |
| 📊 **Server Dashboard** | Real-time CPU, RAM, Disk monitoring |
| 🔐 **Secure Login** | Session-based authentication |

## 🚀 Quick Start

### Prerequisites
- Linux server (Ubuntu 20.04/22.04/24.04)
- Docker & Docker Compose

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/SJ-hosting-control-panel.git
cd SJ-hosting-control-panel

# 2. Start the stack
docker-compose up -d --build

# 3. Access the panel
# Panel: http://YOUR_SERVER_IP:8080
# phpMyAdmin: http://YOUR_SERVER_IP:8081
```

### Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| SJ Panel | admin | admin123 |
| MariaDB | root | SjHosting2025! |

> ⚠️ **Important**: Change these passwords after first login!

## 📁 Project Structure

```
SJ-hosting-control-panel/
├── docker-compose.yml       # Docker stack (Panel + MariaDB + phpMyAdmin)
├── app/
│   ├── Dockerfile          # Python 3.11 + Flask + Certbot
│   ├── requirements.txt    # Python dependencies
│   ├── main.py            # Flask application (all routes)
│   └── templates/         # HTML templates (Jinja2)
│       ├── base.html      # Layout with sidebar
│       ├── login.html     # Login page
│       ├── dashboard.html # Server stats
│       ├── domains.html   # Domain management
│       ├── databases.html # Database management
│       ├── files.html     # File browser
│       ├── settings.html  # Settings & SSL
│       └── error.html     # Error pages
└── putty/                 # Windows SSH tools
```

## � Usage Guide

### Adding a Domain

1. Go to **Domains** → **Add Domain**
2. Enter domain name (e.g., `example.com`)
3. Click **Create Domain**

This creates:
- `/var/www/example.com/public_html/` folder
- Nginx config in `/etc/nginx/sites-available/`
- Default `index.html` landing page

### Creating a Database

1. Go to **Databases** → **Create Database**
2. Enter database name and username
3. Leave password blank for auto-generation
4. Click **Create**

### Enabling SSL

1. Point your domain's DNS to your server IP
2. Go to **Domains** → Click 🛡️ button
3. Certbot will automatically:
   - Obtain Let's Encrypt certificate
   - Configure Nginx for HTTPS
   - Enable HTTP→HTTPS redirect

### Managing Files

1. Go to **Files**
2. Navigate through directories
3. Use **Upload** to add files
4. Use **New Folder** to create directories
5. Click 📥 to download, �️ to delete

## 🛡️ Security

- Path validation prevents directory traversal
- Password hashing with Werkzeug
- Session-based authentication
- Input validation on all forms

## � Development

```bash
# View logs
docker logs -f sj_panel

# Restart after changes
docker-compose restart panel

# Rebuild with new dependencies
docker-compose up -d --build panel
```

## 📋 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | dev_secret_key | Flask session key |
| DB_HOST | mariadb | Database host |
| DB_USER | root | Database user |
| DB_PASSWORD | SjHosting2025! | Database password |

## ✅ Completed Phases

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Foundation (Login, Dashboard) | ✅ |
| 2 | Domain Management | ✅ |
| 3 | Database Management | ✅ |
| 4 | File Manager | ✅ |
| 5 | SSL & Security (Certbot) | ✅ |
| 6 | Polish & Deploy | ✅ |
| 7 | Email Management (Mailserver + Roundcube) | ✅ |
| 8 | Backup System (tar.gz + mysqldump) | ✅ |
| 9 | DNS Management (Cloudflare API) | ✅ |

## 🗺️ Roadmap (Phase 10-19)

| Phase | Feature | Description |
|-------|---------|-------------|
| 10 | **Cron Jobs** | Create/manage scheduled tasks via UI |
| 11 | **Firewall UI** | UFW rules, Block/Allow IPs |
| 12 | **Fail2Ban** | View banned IPs, Unban, Protection settings |
| 13 | **Log Viewer** | Real-time Access/Error logs |
| 14 | **Resource Monitoring** | CPU/RAM/Network graphs with history |
| 15 | **Multi-User** | User management with Admin/Reseller/User roles |
| 16 | **User Quotas** | Disk, Bandwidth, Database limits per user |
| 17 | **Billing Module** | Hosting packages, Invoices, Payment gateway |
| 18 | **One-Click Apps** | Install WordPress, Laravel, Node.js with one click |
| 19 | **API & CLI** | REST API for automation + Command Line Tool |

### Phase Details

#### Phase 10: Cron Jobs
- UI to create/edit/delete cron jobs
- View cron job history and logs
- Pre-built templates (backup daily, cleanup weekly)

#### Phase 11: Firewall UI
- Manage UFW rules via web interface
- Quick allow/block IP addresses
- Port management (open/close)

#### Phase 12: Fail2Ban Integration
- View currently banned IPs
- Manual unban functionality
- Configure jail settings (SSH, Nginx, etc.)

#### Phase 13: Log Viewer
- Real-time access.log and error.log viewing
- Filter by date, IP, status code
- Log rotation settings

#### Phase 14: Resource Monitoring
- CPU/RAM/Disk usage graphs over time
- Network bandwidth monitoring
- Alert thresholds (email when disk > 90%)

#### Phase 15: Multi-User System
- Create user accounts with different roles
- Admin: Full access
- Reseller: Create sub-users and domains
- User: Manage own domains only

#### Phase 16: User Quotas
- Set disk space limit per user
- Set bandwidth limit per month
- Limit number of domains, databases, emails

#### Phase 17: Billing Module
- Create hosting packages (Basic, Pro, Enterprise)
- Generate invoices automatically
- Integrate Stripe/PayPal for payments
- Suspend accounts on overdue

#### Phase 18: One-Click Apps
- WordPress auto-install with database
- Laravel project scaffold
- Node.js app template with PM2
- Static site generators

#### Phase 19: API & CLI
- REST API with JWT authentication
- Create domains, databases via API
- CLI tool for server management
- Webhook notifications

## 🤝 Contributing

1. Fork this repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open Pull Request

## 📜 License

MIT License - Free to use and modify!

---

Made with ❤️ by SJ Panel Team
