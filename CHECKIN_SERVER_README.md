# Check-In Server - LINE Bot HRM System

ระบบเซิร์ฟเวอร์สำหรับจัดการการเช็คอิน พร้อมรองรับการอัปโหลดรูปภาพและตำแหน่ง GPS

## ✨ Features

- ✅ รับข้อมูล GPS และที่อยู่จาก LIFF App
- 📸 รองรับการอัปโหลดรูปภาพพร้อม Watermark (GPS + เวลา)
- 💾 บันทึกข้อมูลการเช็คอินลง JSON file
- 📤 ส่งข้อความยืนยันกลับไปที่ LINE
- 🔍 ค้นหาข้อมูลพนักงานจาก LINE User ID
- 📊 API สำหรับดึงข้อมูลการเช็คอิน

## 📋 Requirements

```bash
pip install -r requirements_checkin.txt
```

หรือติดตั้งแบบ manual:
```bash
pip install Pillow requests
```

## 🚀 การใช้งาน

### 1. เริ่มต้น Server

```bash
python3 checkin_server.py
```

Server จะรันที่ `http://localhost:3001`

### 2. API Endpoints

#### GET Endpoints

- **Health Check**
  ```
  GET /api/health
  ```
  ตรวจสอบสถานะของ server

- **ดึงข้อมูลเช็คอินทั้งหมด**
  ```
  GET /api/checkins
  ```

- **ดึงข้อมูลเช็คอินวันนี้**
  ```
  GET /api/checkins/today
  ```

- **ดึงข้อมูลเช็คอินของพนักงาน**
  ```
  GET /api/checkins/employee/{employeeCode}
  ```
  ตัวอย่าง: `/api/checkins/employee/EMP001`

- **ดูรูปภาพที่อัปโหลด**
  ```
  GET /uploads/{filename}
  ```

#### POST Endpoints

- **อัปโหลดรูปภาพพร้อม GPS**
  ```
  POST /api/upload-photo
  Content-Type: multipart/form-data
  
  Fields:
  - image: file (รูปภาพ)
  - latitude: float (ละติจูด)
  - longitude: float (ลองจิจูด)
  - address: string (ที่อยู่)
  - timestamp: string (ISO format)
  ```

- **รับข้อมูลจาก LIFF App**
  ```
  POST /api/location-from-liff
  Content-Type: application/json
  
  Body:
  {
    "userId": "LINE_USER_ID",
    "displayName": "ชื่อผู้ใช้",
    "latitude": 13.123456,
    "longitude": 100.123456,
    "address": "ที่อยู่",
    "accuracy": 10.5,
    "timestamp": "2025-11-11T10:30:00Z",
    "hasPhoto": true,
    "source": "liff-gps-photo"
  }
  ```

## 📁 File Structure

```
LineBotRegister/
├── checkin_server.py           # Main server file
├── requirements_checkin.txt    # Python dependencies
├── uploads/                    # Uploaded photos (auto-created)
├── checkin_records.json        # Check-in data (auto-created)
└── CHECKIN_SERVER_README.md    # This file
```

## 🔧 Configuration

### LINE Bot Credentials

แก้ไขใน `checkin_server.py`:

```python
LINE_CHANNEL_ACCESS_TOKEN = "YOUR_LINE_CHANNEL_ACCESS_TOKEN"
```

### Mock Employee Database

เพิ่มข้อมูลพนักงานใน `MOCK_EMPLOYEES`:

```python
MOCK_EMPLOYEES = [
    {
        "employeeCode": "EMP001",
        "name": "ชื่อพนักงาน",
        "lineUserId": "LINE_USER_ID",
        "department": "แผนก",
        "position": "ตำแหน่ง",
        "status": "active"
    }
]
```

### Domain URL

แก้ URL สำหรับเข้าถึงรูปภาพ:

```python
# ในฟังก์ชัน upload-photo
image_url = f"https://YOUR_DOMAIN.com/uploads/{filename}"

# ในฟังก์ชัน location-from-liff
photo_url = f"https://YOUR_DOMAIN.com/uploads/{latest_photo}"
```

## 📊 ข้อมูลที่บันทึก

แต่ละการเช็คอินจะบันทึก:

```json
{
  "timestamp": "2025-11-11T10:30:00Z",
  "date": "2025-11-11",
  "thaiTime": "11/11/2025 10:30:00",
  "lineUserId": "U8a372...",
  "displayName": "Nice Phutana",
  "employeeCode": "EMP001",
  "employeeName": "Nice Phutana",
  "department": "IT",
  "position": "Developer",
  "latitude": 13.123456,
  "longitude": 100.123456,
  "address": "เทศบาลนครนครปฐม",
  "accuracy": 10.5,
  "hasPhoto": true,
  "source": "liff-gps-photo",
  "status": "registered"
}
```

## 🖼️ Watermark

รูปภาพที่อัปโหลดจะถูกเพิ่ม watermark อัตโนมัติ ประกอบด้วย:
- 📍 พิกัด GPS (ละติจูด, ลองจิจูด)
- 🕐 วันเวลาที่เช็คอิน
- 📌 ที่อยู่

## 🔗 Integration กับ LIFF App

### ใน `checkin.html` ให้เปลี่ยน URL:

```javascript
// Upload photo
const response = await fetch('https://YOUR_DOMAIN.com/api/upload-photo', {
  method: 'POST',
  body: formData
});

// Send location data
await fetch('https://YOUR_DOMAIN.com/api/location-from-liff', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
```

## 📱 การทดสอบ

### 1. ทดสอบ Health Check

```bash
curl http://localhost:3001/api/health
```

### 2. ทดสอบดึงข้อมูลเช็คอิน

```bash
curl http://localhost:3001/api/checkins
```

### 3. ทดสอบส่งข้อมูลเช็คอิน

```bash
curl -X POST http://localhost:3001/api/location-from-liff \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "U8a372477a988ebe17888a7ea3794b2c7",
    "displayName": "Test User",
    "latitude": 13.8180,
    "longitude": 100.0365,
    "address": "เทศบาลนครนครปฐม",
    "accuracy": 10,
    "timestamp": "2025-11-11T10:30:00Z",
    "hasPhoto": false
  }'
```

## 🔐 Security Notes

⚠️ สิ่งที่ควรทำก่อนใช้งานจริง:

1. **แยก LINE_CHANNEL_ACCESS_TOKEN ออกไปเป็น environment variable**
   ```python
   import os
   LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
   ```

2. **ใช้ HTTPS เท่านั้น** (ไม่ใช้ HTTP สำหรับ production)

3. **เพิ่ม Authentication** สำหรับ API endpoints

4. **Validate input data** ให้ดีก่อนบันทึก

5. **ใช้ Database จริง** แทน JSON file (เช่น MongoDB)

## 🚀 Deploy to Production

### วิธีที่ 1: รันบน Server ด้วย Gunicorn

ไม่แนะนำสำหรับ HTTP server แบบนี้ ควรใช้วิธีที่ 2

### วิธีที่ 2: รัน Background Service

สร้าง systemd service:

```bash
sudo nano /etc/systemd/system/checkin-server.service
```

```ini
[Unit]
Description=LINE Bot Check-In Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/linebot
ExecStart=/usr/bin/python3 /var/www/linebot/checkin_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable และ start:
```bash
sudo systemctl enable checkin-server
sudo systemctl start checkin-server
sudo systemctl status checkin-server
```

### วิธีที่ 3: ใช้ Nginx Reverse Proxy

```nginx
# ใน nginx config
location /checkin/ {
    proxy_pass http://localhost:3001/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 📝 TODO / Improvements

- [ ] เชื่อมต่อ MongoDB แทน JSON file
- [ ] เพิ่ม Authentication สำหรับ API
- [ ] Logging ที่ดีกว่า (ใช้ logging module)
- [ ] Error handling ที่ครอบคลุมมากขึ้น
- [ ] Rate limiting
- [ ] Image compression และ resize
- [ ] Support multiple image formats
- [ ] Dashboard สำหรับดูข้อมูลเช็คอิน
- [ ] Export ข้อมูลเป็น CSV/Excel

## 📞 Support

หากพบปัญหาหรือต้องการความช่วยเหลือ:
- ตรวจสอบ console logs
- ดู `checkin_records.json` สำหรับข้อมูลที่บันทึก
- ตรวจสอบไฟล์ใน folder `uploads/`

---

💡 **Tip**: ใช้ `tail -f` เพื่อดู logs real-time:
```bash
python3 checkin_server.py 2>&1 | tee checkin_server.log
```
