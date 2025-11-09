# LINE Bot Registration System

ระบบลงทะเบียนผ่าน LINE Bot สำหรับจัดการข้อมูลพนักงาน

## 🚀 Quick Deploy to Server

### ครั้งแรก (First Time Setup)

1. Clone repository บน server:
```bash
cd /var/www
git clone YOUR_REPO_URL linebot
cd linebot
```

2. ตั้งค่า Python environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

3. สร้างไฟล์ .env:
```bash
cp .env.example .env
nano .env
```

4. ตั้งค่า logs directory:
```bash
mkdir -p logs
```

5. ตั้งค่า Supervisor และ Nginx (ตามขั้นตอนใน DEPLOYMENT.md)

### อัพเดทโค้ด (Update Code)

```bash
cd /var/www/linebot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # ถ้ามี dependencies ใหม่
sudo supervisorctl restart linebot
```

## 📁 Project Structure

```
LineBotRegister/
├── server.py              # Main Flask application
├── register-form.html     # Frontend registration form
├── requirements.txt       # Python dependencies
├── gunicorn_config.py     # Gunicorn configuration
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
└── docs/
    ├── LINE_BOT_SETUP.md
    ├── LIFF_SETUP.md
    ├── MONGODB_SETUP.md
    └── DEPLOYMENT.md
```

## 🔧 Environment Variables

สร้างไฟล์ `.env` และใส่ค่าเหล่านี้:

```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
```

## 🛠️ Development

รันในโหมด development:

```bash
source venv/bin/activate
python server.py
```

## 📝 API Endpoints

- `GET /` - Registration form
- `POST /api/register` - Register new user
- `GET /api/registrations` - Get all registrations
- `GET /api/registrations/<emp_code>` - Get specific registration
- `PUT /api/registrations/<emp_code>` - Update registration
- `DELETE /api/registrations/<emp_code>` - Delete registration
- `POST /webhook` - LINE Bot webhook
- `GET /api/health` - Health check

## 🔐 LINE Bot Commands

- พิมพ์ `personal` - ดูข้อมูลส่วนตัว

## 📚 Documentation

- [LINE Bot Setup Guide](docs/LINE_BOT_SETUP.md)
- [LIFF Setup Guide](docs/LIFF_SETUP.md)
- [MongoDB Setup Guide](docs/MONGODB_SETUP.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is private and proprietary.
