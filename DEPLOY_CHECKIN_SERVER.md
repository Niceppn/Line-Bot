# 🚀 Deploy Check-In Server to DigitalOcean

คู่มือการ deploy check-in server ขึ้น server DigitalOcean (nice-ppn.studio)

## 📋 ข้อมูล Server

- **Domain**: nice-ppn.studio
- **IP**: 146.190.82.178
- **Main Server**: Port 8000 (Gunicorn)
- **Check-in Server**: Port 3001 (Python HTTP Server)
- **Web Server**: Nginx (Reverse Proxy)

---

## 📦 Step 1: Upload Files to Server

จาก local machine, upload ไฟล์ที่จำเป็น:

```bash
cd /Users/Macbook/LineBotRegister

# Upload checkin server และ dependencies
scp checkin_server.py root@146.190.82.178:/var/www/linebot/
scp requirements_checkin.txt root@146.190.82.178:/var/www/linebot/

# หรือใช้ git (แนะนำ)
# บน local: git add . && git commit -m "Add checkin server" && git push
# บน server: cd /var/www/linebot && git pull
```

---

## 🔧 Step 2: SSH เข้า Server และติดตั้ง Dependencies

```bash
# SSH เข้า server
ssh root@146.190.82.178

# ไปที่ directory
cd /var/www/linebot

# ติดตั้ง Python packages
pip3 install Pillow requests

# หรือใช้ requirements file
pip3 install -r requirements_checkin.txt

# สร้าง directory สำหรับ uploads
mkdir -p uploads
chmod 755 uploads
```

---

## ⚙️ Step 3: สร้าง Supervisor Configuration

สร้างไฟล์ config สำหรับ check-in server:

```bash
sudo nano /etc/supervisor/conf.d/checkin-server.conf
```

วาง config นี้:

```ini
[program:checkin-server]
directory=/var/www/linebot
command=/usr/bin/python3 /var/www/linebot/checkin_server.py
user=www-data
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=10
redirect_stderr=true
stdout_logfile=/var/www/linebot/logs/checkin-server.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=/var/www/linebot/logs/checkin-server-error.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=PATH="/usr/bin",LANG="en_US.UTF-8"
```

บันทึกและออก (`Ctrl+O`, `Enter`, `Ctrl+X`)

---

## 🌐 Step 4: แก้ไข Nginx Configuration

แก้ไข Nginx config:

```bash
sudo nano /etc/nginx/sites-available/linebot
```

แก้ไขเป็น:

```nginx
server {
    server_name nice-ppn.studio www.nice-ppn.studio;

    # Main LINE Bot Application (Gunicorn on port 8000)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Line-Signature $http_x_line_signature;
    }

    # Check-in Server API (Python HTTP Server on port 3001)
    location /checkin-api/ {
        proxy_pass http://127.0.0.1:3001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # สำหรับอัปโหลดรูปภาพ
        client_max_body_size 10M;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }

    # Serve uploaded images directly
    location /uploads/ {
        alias /var/www/linebot/uploads/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Access-Control-Allow-Origin "*";
    }

    # SSL Configuration (managed by Certbot)
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/nice-ppn.studio/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nice-ppn.studio/privkey.pem;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name nice-ppn.studio www.nice-ppn.studio;
    return 301 https://$server_name$request_uri;
}
```

บันทึกและออก

---

## ✅ Step 5: Start Services

```bash
# อัปเดต Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Start checkin-server
sudo supervisorctl start checkin-server

# ตรวจสอบสถานะ
sudo supervisorctl status

# ควรเห็น:
# checkin-server                   RUNNING   pid 12345, uptime 0:00:05
# linebot                          RUNNING   pid 67890, uptime 1:23:45

# ทดสอบ Nginx config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## 🧪 Step 6: ทดสอบการทำงาน

### 1. ทดสอบ Health Check

```bash
# จาก server
curl http://localhost:3001/api/health

# จากภายนอก
curl https://nice-ppn.studio/checkin-api/health
```

ควรได้:
```json
{
  "status": "OK",
  "message": "Check-In Server is running",
  "timestamp": "2025-11-11T10:30:00",
  "upload_dir": "/var/www/linebot/uploads",
  "total_checkins": 0
}
```

### 2. ทดสอบ API อื่นๆ

```bash
# ดูข้อมูลเช็คอินทั้งหมด
curl https://nice-ppn.studio/checkin-api/checkins

# ดูเช็คอินวันนี้
curl https://nice-ppn.studio/checkin-api/checkins/today
```

---

## 📍 API Endpoints ที่ใช้งานได้

| Endpoint | Method | URL | Description |
|----------|--------|-----|-------------|
| Health Check | GET | `https://nice-ppn.studio/checkin-api/health` | ตรวจสอบสถานะ server |
| All Check-ins | GET | `https://nice-ppn.studio/checkin-api/checkins` | ดูเช็คอินทั้งหมด |
| Today's Check-ins | GET | `https://nice-ppn.studio/checkin-api/checkins/today` | ดูเช็คอินวันนี้ |
| Employee Check-ins | GET | `https://nice-ppn.studio/checkin-api/checkins/employee/{code}` | เช็คอินของพนักงาน |
| Upload Photo | POST | `https://nice-ppn.studio/checkin-api/upload-photo` | อัปโหลดรูป + GPS |
| Location from LIFF | POST | `https://nice-ppn.studio/checkin-api/location-from-liff` | รับข้อมูลจาก LIFF |
| View Image | GET | `https://nice-ppn.studio/uploads/{filename}` | ดูรูปภาพ |

---

## 🔍 Troubleshooting

### ตรวจสอบ Logs

```bash
# Check-in server logs
tail -f /var/www/linebot/logs/checkin-server.log
tail -f /var/www/linebot/logs/checkin-server-error.log

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Supervisor logs
sudo tail -f /var/log/supervisor/supervisord.log
```

### ปัญหาที่พบบ่อย

#### 1. Service ไม่ Start

```bash
# ตรวจสอบสถานะ
sudo supervisorctl status checkin-server

# Restart
sudo supervisorctl restart checkin-server

# ดู error
sudo supervisorctl tail checkin-server stderr
```

#### 2. Port 3001 ถูกใช้งานอยู่

```bash
# หา process ที่ใช้ port 3001
sudo lsof -i :3001

# Kill process (ถ้าจำเป็น)
sudo kill -9 <PID>
```

#### 3. Permission Denied สำหรับ uploads/

```bash
# แก้ไข permissions
sudo chown -R www-data:www-data /var/www/linebot/uploads
sudo chmod -R 755 /var/www/linebot/uploads
```

#### 4. Nginx 502 Bad Gateway

```bash
# ตรวจสอบว่า checkin-server รันอยู่หรือไม่
sudo supervisorctl status checkin-server

# ตรวจสอบว่า port 3001 เปิดอยู่
curl http://localhost:3001/api/health

# Restart ทั้งหมด
sudo supervisorctl restart checkin-server
sudo systemctl reload nginx
```

#### 5. Upload รูปไม่ได้

```bash
# ตรวจสอบว่าติดตั้ง Pillow แล้ว
pip3 list | grep Pillow

# ติดตั้งใหม่
pip3 install --upgrade Pillow

# ตรวจสอบ client_max_body_size ใน Nginx
sudo nginx -T | grep client_max_body_size
```

---

## 🔄 การ Update Code

เมื่อมีการแก้ไขโค้ด:

```bash
# บน local
git add .
git commit -m "Update checkin server"
git push origin main

# SSH เข้า server
ssh root@146.190.82.178
cd /var/www/linebot

# Pull code ใหม่
git pull origin main

# Restart services
sudo supervisorctl restart checkin-server
sudo supervisorctl restart linebot

# ตรวจสอบว่าทำงาน
sudo supervisorctl status
```

---

## 📊 Monitoring

### ดูสถานะ Real-time

```bash
# Watch supervisor status
watch -n 2 'sudo supervisorctl status'

# Monitor logs
tail -f /var/www/linebot/logs/checkin-server.log | grep -E "ERROR|SUCCESS|Photo|Location"
```

### ตรวจสอบ Disk Space

```bash
# ดูขนาดของ uploads
du -sh /var/www/linebot/uploads

# ดูไฟล์ล่าสุด
ls -lht /var/www/linebot/uploads | head -10
```

---

## 🔐 Security Checklist

- [x] ใช้ HTTPS (SSL certificate)
- [ ] เพิ่ม rate limiting ใน Nginx
- [ ] ตั้ง environment variables สำหรับ LINE token
- [ ] เพิ่ม authentication สำหรับ admin endpoints
- [ ] ตั้ง log rotation
- [ ] Backup checkin_records.json เป็นประจำ

---

## 📝 Next Steps

1. **Database Integration**: เปลี่ยนจาก JSON file เป็น MongoDB
2. **Dashboard**: สร้างหน้า admin สำหรับดูข้อมูลเช็คอิน
3. **Analytics**: เพิ่มระบบวิเคราะห์การเช็คอิน
4. **Notifications**: แจ้งเตือน admin เมื่อมีเช็คอินใหม่
5. **Export**: Export ข้อมูลเป็น Excel/CSV

---

## 🆘 Quick Commands

```bash
# Restart everything
sudo supervisorctl restart all && sudo systemctl reload nginx

# Check all services
sudo supervisorctl status && sudo systemctl status nginx

# View all logs
sudo tail -f /var/www/linebot/logs/*.log

# Clean old uploads (รูปเก่ากว่า 30 วัน)
find /var/www/linebot/uploads -type f -mtime +30 -delete
```

---

**✅ เมื่อทำตามขั้นตอนทั้งหมดแล้ว check-in server จะพร้อมใช้งานที่:**

🌐 **https://nice-ppn.studio/checkin-api/**

📱 **LIFF App จะส่งข้อมูลมาที่ server อัตโนมัติ**

💾 **ข้อมูลจะถูกบันทึกใน `/var/www/linebot/checkin_records.json`**

📸 **รูปภาพจะถูกเก็บใน `/var/www/linebot/uploads/`**
