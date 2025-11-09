# วิธีใช้ MongoDB Atlas (ฟรี)

## 1. ไปที่ https://www.mongodb.com/cloud/atlas/register

## 2. สร้างบัญชีและ Cluster ฟรี

## 3. คลิก "Connect" เลือก "Drivers"

## 4. Copy connection string แล้วแทนที่ใน .env:
```
MONGO_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/linebot_register?retryWrites=true&w=majority
```

## 5. แทนที่ username และ password ของคุณ

## 6. รัน server ใหม่:
```bash
python server.py
```

เสร็จแล้ว! MongoDB พร้อมใช้งาน ✅
