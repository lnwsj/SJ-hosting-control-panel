# SJ Panel - Custom Hosting Control Panel

A lightweight, Docker-based web hosting control panel inspired by DirectAdmin.

## 🚀 Quick Start

### Prerequisites
- A Linux server (Ubuntu 20.04/22.04/24.04 recommended)
- Docker & Docker Compose installed

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/SJ-hosting-control-panel.git
cd SJ-hosting-control-panel
```

### 2. Start the Stack
```bash
docker-compose up -d --build
```

### 3. Access the Panel
| Service | URL | Default Login |
|---------|-----|---------------|
| **SJ Panel** | http://YOUR_SERVER_IP:8080 | admin / admin123 |
| **phpMyAdmin** | http://YOUR_SERVER_IP:8081 | root / SjHosting2025! |

---

## 📁 Project Structure

```
SJ-hosting-control-panel/
├── docker-compose.yml        # Docker stack definition
├── app/
│   ├── Dockerfile           # Python 3.11 + Flask image
│   ├── requirements.txt     # Python dependencies
│   ├── main.py             # Flask application
│   └── templates/          # HTML templates (Jinja2)
│       ├── base.html       # Layout + Sidebar
│       ├── login.html      # Login page
│       ├── dashboard.html  # Server stats
│       ├── domains.html    # Domain list
│       ├── add_domain.html # Add domain form
│       ├── databases.html  # DB management
│       ├── files.html      # File manager (placeholder)
│       └── settings.html   # Settings
└── putty/                  # SSH tools for Windows deployment
```

---

## 🛠️ Development

### Local Development (with hot-reload)
```bash
# Start with logs visible
docker-compose up --build

# Or run Flask directly (requires Python 3.11+)
cd app
pip install -r requirements.txt
python main.py
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

### View logs
```bash
docker logs -f sj_panel
```

---

## 📋 Development Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation (Login, Dashboard, UI) | ✅ Complete |
| 2 | Domain Management (Add/Delete domains, Nginx config) | 🔲 TODO |
| 3 | Database Management (Create/Delete MySQL DBs) | 🔲 TODO |
| 4 | File Management (Upload, Download, Edit) | 🔲 TODO |
| 5 | SSL & Security (Let's Encrypt, Firewall) | 🔲 TODO |
| 6 | Polish & Deploy (Error handling, Docs) | 🔲 TODO |

---

## 🔧 Configuration

### Change Database Password
Edit `docker-compose.yml`:
```yaml
mariadb:
  environment:
    MYSQL_ROOT_PASSWORD: YOUR_NEW_PASSWORD
```

### Change Panel Admin Password
After first login, use Settings page or edit `/data/users.json` inside the container.

---

## 🤝 Contributing

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📜 License

MIT License - Feel free to use and modify!
