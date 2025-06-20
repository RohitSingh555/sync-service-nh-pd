# 🚀 FastAPI Deployment with Gunicorn & Nginx (Ubuntu)

This project uses FastAPI, served by Gunicorn + UvicornWorker, behind an Nginx reverse proxy.

---

## 🛠️ Setup

```bash
# Install dependencies
sudo apt update
sudo apt install python3-venv python3-pip nginx -y

# Clone project and set up virtual environment
cd /root/fastapi-app/sync-service
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

---

## 🔥 Gunicorn + systemd

Create the systemd service:

```ini
# /etc/systemd/system/fastapi.service
[Unit]
Description=FastAPI with Gunicorn
After=network.target

[Service]
User=root
WorkingDirectory=/root/fastapi-app/sync-service
ExecStart=/root/fastapi-app/sync-service/env/bin/gunicorn -k uvicorn.workers.UvicornWorker src.main:app --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fastapi
sudo systemctl start fastapi
sudo systemctl status fastapi
```

---

## 🌐 Nginx Reverse Proxy

Create a config file:

```nginx
# /etc/nginx/sites-available/fastapi
server {
    listen 80;
    server_name your_server_ip_or_domain;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🔍 Logs & Debugging

```bash
# View app logs
sudo journalctl -u fastapi.service -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check if app is live
curl http://127.0.0.1:8000
curl http://your_public_ip
```

---

## 🔐 (Optional) HTTPS via Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## ✅ Firewall & System Check

```bash
# Allow HTTP through firewall
sudo ufw allow 80

# Check ports
sudo lsof -i -P -n | grep LISTEN

# Clean disk/logs
sudo apt autoremove -y && sudo apt autoclean -y
sudo journalctl --vacuum-time=7d
df -h
```

---
