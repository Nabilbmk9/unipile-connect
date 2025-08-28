# 🚀 Production Deployment Guide

## 📋 Prerequisites

- **Python 3.8+** installed on your server
- **PostgreSQL** database (recommended for production)
- **Domain name** and SSL certificate
- **Server** (VPS, cloud instance, or dedicated server)

## 🗄️ Database Setup

### Option 1: PostgreSQL (Recommended for Production)

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE unipile_connect;
CREATE USER unipile_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE unipile_connect TO unipile_user;
\q

# Update your .env file
DATABASE_URL=postgresql://unipile_user:your_secure_password@localhost/unipile_connect
```

### Option 2: SQLite (Development/Testing)

```bash
# SQLite is included by default
DATABASE_URL=sqlite:///./unipile_connect.db
```

## 🔧 Environment Configuration

Create a production `.env` file:

```env
# Production Environment
ENVIRONMENT=production

# Database Configuration
DATABASE_URL=postgresql://unipile_user:your_secure_password@localhost/unipile_connect

# Unipile Configuration
UNIPILE_API_BASE=https://api8.unipile.com:13816/api/v1
UNIPILE_API_HOST=https://api8.unipile.com:13816
UNIPILE_API_KEY=your_actual_unipile_api_key

# App Configuration
APP_BASE_URL=https://yourdomain.com
SECRET_KEY=your_very_long_random_secret_key_here

# Security Settings
SECURE_COOKIES=true
CORS_ORIGINS=https://yourdomain.com
```

## 🚀 Server Setup

### 1. Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv

# Install system dependencies
sudo apt install nginx supervisor
```

### 2. Application Setup

```bash
# Clone your repository
git clone https://github.com/yourusername/unipile-connect.git
cd unipile-connect

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py
```

### 3. Gunicorn Configuration

Create `/etc/supervisor/conf.d/unipile-connect.conf`:

```ini
[program:unipile-connect]
command=/path/to/your/app/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
directory=/path/to/your/app
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/unipile-connect/gunicorn.log
environment=ENVIRONMENT="production"
```

### 4. Nginx Configuration

Create `/etc/nginx/sites-available/unipile-connect`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Static Files
    location /static/ {
        alias /path/to/your/app/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

### 5. Enable and Start Services

```bash
# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/unipile-connect /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Start Supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start unipile-connect

# Enable services on boot
sudo systemctl enable nginx
sudo systemctl enable supervisor
```

## 🔒 Security Hardening

### 1. Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 2. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 3. Database Security

```bash
# PostgreSQL security
sudo -u postgres psql
ALTER USER unipile_user PASSWORD 'new_secure_password';
REVOKE CONNECT ON DATABASE unipile_connect FROM PUBLIC;
GRANT CONNECT ON DATABASE unipile_connect TO unipile_user;
\q

# Update pg_hba.conf for local connections only
```

## 📊 Monitoring and Logging

### 1. Log Rotation

Create `/etc/logrotate.d/unipile-connect`:

```
/var/log/unipile-connect/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
}
```

### 2. Health Checks

Add to your application:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
```

### 3. Monitoring with Prometheus/Grafana

```bash
# Install monitoring tools
sudo apt install prometheus grafana

# Configure Prometheus to scrape your app metrics
```

## 🔄 Deployment Process

### 1. Automated Deployment Script

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying Unipile Connect..."

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run database migrations (if any)
python init_db.py

# Restart application
sudo supervisorctl restart unipile-connect

echo "✅ Deployment complete!"
```

### 2. CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Deploy to server
        uses: appleboy/ssh-action@v0.1.4
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.KEY }}
          script: |
            cd /path/to/your/app
            ./deploy.sh
```

## 🚨 Backup Strategy

### 1. Database Backups

```bash
# Create backup script
#!/bin/bash
BACKUP_DIR="/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump unipile_connect > $BACKUP_DIR/backup_$DATE.sql

# Keep last 30 days
find $BACKUP_DIR -name "backup_*.sql" -mtime +30 -delete
```

### 2. Application Backups

```bash
# Backup application files
tar -czf /backups/app/app_$DATE.tar.gz /path/to/your/app
```

## 📈 Scaling Considerations

### 1. Load Balancer

```nginx
# Multiple backend servers
upstream unipile_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}
```

### 2. Redis for Session Storage

```python
# Use Redis instead of database for sessions
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
```

### 3. CDN for Static Files

```nginx
# Serve static files from CDN
location /static/ {
    proxy_pass https://your-cdn.com;
}
```

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Errors**

   - Check database service status
   - Verify connection string
   - Check firewall rules

2. **Permission Errors**

   - Ensure proper file ownership
   - Check user permissions

3. **SSL Issues**
   - Verify certificate validity
   - Check Nginx configuration

### Debug Commands

```bash
# Check application status
sudo supervisorctl status unipile-connect

# View logs
sudo tail -f /var/log/unipile-connect/gunicorn.log
sudo tail -f /var/log/nginx/error.log

# Test database connection
python -c "from app.database import engine; print(engine.execute('SELECT 1').scalar())"
```

## 📚 Additional Resources

- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)

---

**Remember**: Always test your deployment in a staging environment first!
