# 🚀 Deploy Check-In Server (Updated Version)

คู่มือการ deploy check-in server เวอร์ชันใหม่ที่มีการตรวจสอบกับ HR System

## 🆕 อัปเดตใหม่

- ✅ เชื่อมต่อ MongoDB สำหรับข้อมูลพนักงาน
- ✅ ตรวจสอบ employeeCode กับ HR System API
- ✅ บันทึกข้อมูลการยืนยันจาก HR
- ✅ แสดงสถานะการยืนยันใน LINE message

---

## 📋 ข้อกำหนดเบื้องต้น

### 1. Server Information
- **Domain**: nice-ppn.studio
- **IP**: 146.190.82.178
- **Check-in Server Port**: 3001
- **HR System API**: http://10.10.110.7:3000/employee/search

### 2. Environment Variables (.env)
ตรวจสอบว่าไฟล์ `.env` มีตัวแปรเหล่านี้:

```bash
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token

# MongoDB Configuration
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/linebot_register?retryWrites=true&w=majority
```

---

## 🚀 Deploy Steps

### Step 1: เตรียมไฟล์บน Local

```bash
cd /Users/Macbook/LineBotRegister

# ตรวจสอบไฟล์ที่จำเป็น
ls -la checkin_server.py
ls -la requirements_checkin.txt
ls -la .env

# Commit changes to git
git add checkin_server.py requirements_checkin.txt
git commit -m "Update checkin server with HR verification"
git push origin main
```

---

### Step 2: SSH เข้า Server

```bash
ssh root@146.190.82.178
```

---

### Step 3: Pull Code และติดตั้ง Dependencies

```bash
# ไปที่ directory
cd /var/www/linebot

# Pull code ใหม่
git pull origin main

# ติดตั้ง Python packages (เวอร์ชันใหม่)
pip3 install -r requirements_checkin.txt

# ตรวจสอบว่าติดตั้งครบ
pip3 list | grep -E "Pillow|requests|pymongo|python-dotenv"
```

ควรเห็น:
```
Pillow          10.1.0
pymongo         4.6.0
python-dotenv   1.0.0
requests        2.31.0
```

---

### Step 4: ตรวจสอบ Environment Variables

```bash
# ตรวจสอบว่ามีไฟล์ .env
cat /var/www/linebot/.env

# ควรมี:
# LINE_CHANNEL_ACCESS_TOKEN=...
# MONGO_URI=...

# ถ้าไม่มี ให้สร้างใหม่
nano /var/www/linebot/.env
```

---

### Step 5: สร้าง/อัปเดต Supervisor Configuration

```bash
sudo nano /etc/supervisor/conf.d/checkin-server.conf
```

ใส่ config นี้:

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

### Step 6: ตรวจสอบ Network Access

เพื่อให้ server สามารถเรียก HR API ได้:

```bash
# ทดสอบเชื่อมต่อ HR API
curl -X POST http://10.10.110.7:3000/employee/search \
  -H "Content-Type: application/json" \
  -d '{"employeeId": "1001"}'
```

⚠️ **หมายเหตุ**: ถ้า HR API อยู่ใน internal network อาจต้อง:
1. ตั้งค่า VPN/VPC Peering
2. เพิ่ม IP ของ server (146.190.82.178) เข้า whitelist ของ HR system
3. ใช้ reverse proxy หรือ API gateway

---

### Step 7: Restart Services

```bash
# อัปเดต Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Restart checkin-server
sudo supervisorctl restart checkin-server

# ตรวจสอบสถานะ
sudo supervisorctl status

# ควรเห็น:
# checkin-server    RUNNING   pid 12345, uptime 0:00:05
```

---

### Step 8: ตรวจสอบ Logs

```bash
# ดู logs แบบ real-time
tail -f /var/www/linebot/logs/checkin-server.log

# ควรเห็น:
# ✅ Connected to MongoDB successfully
# 📡 Server running at http://localhost:3001/
# 👥 Registered Employees: 5
```

ถ้ามี error:
```bash
# ดู error logs
tail -f /var/www/linebot/logs/checkin-server-error.log
```

---

## 🧪 Testing

### 1. ทดสอบ Health Check

```bash
# จาก server (internal)
curl http://localhost:3001/api/health

# จากภายนอก (public)
curl https://nice-ppn.studio/checkin-api/health
```

ผลลัพธ์ที่ควรได้:
```json
{
  "status": "OK",
  "message": "Check-In Server is running",
  "timestamp": "2025-11-22T10:30:00",
  "upload_dir": "/var/www/linebot/uploads",
  "total_checkins": 0
}
```

---

### 2. ทดสอบการเช็คอินจริง

จาก LIFF App หรือ curl:

```bash
curl -X POST https://nice-ppn.studio/checkin-api/location-from-liff \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "U1234567890abcdef",
    "displayName": "Test User",
    "latitude": 13.736717,
    "longitude": 100.523186,
    "address": "Bangkok, Thailand",
    "hasPhoto": false,
    "accuracy": 20,
    "timestamp": "2025-11-22T10:30:00.000Z",
    "source": "test"
  }'
```

ตรวจสอบ logs ว่ามีการ:
1. ✅ ค้นหาพนักงานจาก MongoDB
2. ✅ เรียก HR API เพื่อยืนยัน employeeCode
3. ✅ บันทึกข้อมูลพร้อม hrSystemVerified
4. ✅ ส่ง LINE message กลับไปหาผู้ใช้

---

## 🔍 Troubleshooting

### ปัญหา 1: MongoDB Connection Failed

```bash
# ตรวจสอบ MONGO_URI
cat /var/www/linebot/.env | grep MONGO_URI

# ทดสอบเชื่อมต่อ MongoDB
python3 -c "
from pymongo import MongoClient
uri = 'your_mongo_uri_here'
client = MongoClient(uri)
print('Connected:', client.list_database_names())
"
```

**วิธีแก้:**
- ตรวจสอบ username/password
- เพิ่ม IP ของ server ใน MongoDB Atlas IP Whitelist
- ตรวจสอบ network connectivity

---

### ปัญหา 2: HR API Connection Timeout

ใน logs จะเห็น:
```
⚠️ HR API timeout - continuing without verification
```

**วิธีแก้:**

```bash
# ตรวจสอบว่าเชื่อมต่อ HR API ได้หรือไม่
curl -X POST http://10.10.110.7:3000/employee/search \
  -H "Content-Type: application/json" \
  -d '{"employeeId": "1001"}' \
  --max-time 5
```

ถ้าไม่ได้:
1. ตรวจสอบ network/firewall
2. ใช้ VPN หรือ private network
3. ปรับ timeout ใน code (ตอนนี้คือ 5 วินาที)

---

### ปัญหา 3: LINE Message ไม่ส่ง

ใน logs จะเห็น:
```
❌ Failed to send message: 401
```

**วิธีแก้:**
```bash
# ตรวจสอบ LINE_CHANNEL_ACCESS_TOKEN
cat /var/www/linebot/.env | grep LINE_CHANNEL_ACCESS_TOKEN

# ทดสอบ token
curl -X POST https://api.line.me/v2/bot/message/push \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "U1234567890abcdef",
    "messages": [{"type": "text", "text": "Test"}]
  }'
```

---

### ปัญหา 4: Permission Denied

```bash
# แก้ไข permissions
sudo chown -R www-data:www-data /var/www/linebot
sudo chmod -R 755 /var/www/linebot
sudo chmod -R 755 /var/www/linebot/uploads
```

---

## 📊 Monitoring & Logs

### ดู Logs แบบต่างๆ

```bash
# Check-in server logs (general)
tail -f /var/www/linebot/logs/checkin-server.log

# Filter เฉพาะข้อมูลสำคัญ
tail -f /var/www/linebot/logs/checkin-server.log | grep -E "Employee|HR|MongoDB|SUCCESS|ERROR"

# ดูเฉพาะการเช็คอิน
tail -f /var/www/linebot/logs/checkin-server.log | grep "📍 Location from LIFF"

# ดูเฉพาะการยืนยัน HR
tail -f /var/www/linebot/logs/checkin-server.log | grep "HR API"
```

### ตรวจสอบข้อมูลเช็คอิน

```bash
# ดูข้อมูลเช็คอินทั้งหมด
cat /var/www/linebot/checkin_records.json | jq .

# นับจำนวนเช็คอิน
cat /var/www/linebot/checkin_records.json | jq '. | length'

# ดูเช็คอินล่าสุด
cat /var/www/linebot/checkin_records.json | jq '.[-1]'

# ดูเฉพาะที่มีการยืนยัน HR
cat /var/www/linebot/checkin_records.json | jq '.[] | select(.hrSystemVerified == true)'
```

---

## 🔄 Update Workflow

เมื่อมีการแก้ไขโค้ดในอนาคต:

```bash
# 1. บน Local
cd /Users/Macbook/LineBotRegister
git add .
git commit -m "Update: describe your changes"
git push origin main

# 2. บน Server
ssh root@146.190.82.178
cd /var/www/linebot
git pull origin main

# 3. Restart (ถ้าจำเป็น)
sudo supervisorctl restart checkin-server

# 4. ตรวจสอบ
sudo supervisorctl status
tail -f /var/www/linebot/logs/checkin-server.log
```

---

## 📈 Performance Tips

### 1. เพิ่ม Index ใน MongoDB

```javascript
// ใน MongoDB shell หรือ Compass
db.registrations.createIndex({ "lineUserId": 1 })
db.checkins.createIndex({ "date": -1 })
db.checkins.createIndex({ "employeeCode": 1 })
```

### 2. Cache HR API Response (Optional)

ถ้า HR API ตอบช้า อาจเพิ่ม caching:
```python
# เพิ่ม in-memory cache (อายุ 5 นาที)
hr_cache = {}
cache_timeout = 300  # seconds
```

### 3. Log Rotation

```bash
# ตั้งค่า log rotation
sudo nano /etc/logrotate.d/checkin-server

# เพิ่ม:
/var/www/linebot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
}
```

---

## 🎯 API Endpoints Summary

| Endpoint | URL | Method | Description |
|----------|-----|--------|-------------|
| Health | `https://nice-ppn.studio/checkin-api/health` | GET | ตรวจสอบสถานะ |
| LIFF Check-in | `https://nice-ppn.studio/checkin-api/location-from-liff` | POST | รับข้อมูลจาก LIFF |
| Upload Photo | `https://nice-ppn.studio/checkin-api/upload-photo` | POST | อัปโหลดรูป + GPS |
| All Check-ins | `https://nice-ppn.studio/checkin-api/checkins` | GET | ดูทั้งหมด |
| Today's | `https://nice-ppn.studio/checkin-api/checkins/today` | GET | ดูวันนี้ |
| By Employee | `https://nice-ppn.studio/checkin-api/checkins/employee/{code}` | GET | ตามรหัส |
| Images | `https://nice-ppn.studio/uploads/{filename}` | GET | ดูรูปภาพ |

---

## ✅ Checklist

- [ ] Pull code ล่าสุดจาก git
- [ ] ติดตั้ง dependencies (Pillow, requests, pymongo, python-dotenv)
- [ ] ตั้งค่า .env (LINE_CHANNEL_ACCESS_TOKEN, MONGO_URI)
- [ ] สร้าง supervisor config
- [ ] ตรวจสอบ network access ไป HR API (10.10.110.7:3000)
- [ ] Restart checkin-server
- [ ] ทดสอบ health check
- [ ] ทดสอบเช็คอินจริง
- [ ] ตรวจสอบ LINE message ส่งสำเร็จ
- [ ] ตรวจสอบ HR verification ทำงาน
- [ ] ตรวจสอบข้อมูลบันทึกใน checkin_records.json

---

## 🆘 Quick Commands

```bash
# ดูสถานะทุกอย่าง
sudo supervisorctl status && curl -s http://localhost:3001/api/health | jq .

# Restart everything
sudo supervisorctl restart checkin-server && sleep 2 && sudo supervisorctl status

# ดู logs แบบ live
tail -f /var/www/linebot/logs/checkin-server.log | grep --line-buffered -E "✅|❌|⚠️|📍|🔍"

# ทดสอบ MongoDB connection
python3 -c "from pymongo import MongoClient; import os; from dotenv import load_dotenv; load_dotenv(); print('MongoDB OK' if MongoClient(os.getenv('MONGO_URI')).list_database_names() else 'Failed')"

# นับจำนวน employees ใน MongoDB
python3 -c "from pymongo import MongoClient; import os; from dotenv import load_dotenv; load_dotenv(); db = MongoClient(os.getenv('MONGO_URI'))['linebot_register']; print(f'Employees: {db.registrations.count_documents({})}')"
```

---

## 📞 Support

หากพบปัญหา:
1. ตรวจสอบ logs: `/var/www/linebot/logs/checkin-server.log`
2. ตรวจสอบสถานะ: `sudo supervisorctl status`
3. ทดสอบ API: `curl http://localhost:3001/api/health`
4. ตรวจสอบ MongoDB connection
5. ตรวจสอบ HR API connectivity

---

**✨ เมื่อ deploy สำเร็จ ระบบจะ:**

1. ✅ รับข้อมูลเช็คอินจาก LIFF App
2. ✅ ตรวจสอบพนักงานจาก MongoDB
3. ✅ ยืนยัน employeeCode กับ HR System
4. ✅ บันทึกข้อมูลพร้อมสถานะการยืนยัน
5. ✅ ส่ง LINE message แจ้งผลกลับ
6. ✅ เก็บรูปภาพพร้อม watermark

🎉 **Happy Deploying!**
