# 🔧 HR System Verification Guide

## ปัญหา: ไม่สามารถเชื่อมต่อ HR API ได้

เนื่องจาก HR API อยู่ที่ `http://10.10.110.7:3000` ซึ่งเป็น **private IP** ที่ server บน DigitalOcean เข้าถึงไม่ได้

---

## ✅ วิธีแก้ไข (เลือก 1 วิธี)

### วิธีที่ 1: ปิดการตรวจสอบ HR ชั่วคราว (แนะนำสำหรับตอนนี้)

แก้ไขไฟล์ `.env` บน server:

```bash
# SSH เข้า server
ssh root@146.190.82.178

# แก้ไข .env
nano /var/www/linebot/.env

# เพิ่มบรรทัดนี้ (หรือเปลี่ยนเป็น false)
ENABLE_HR_VERIFICATION=false
```

บันทึกและ restart:
```bash
sudo supervisorctl restart checkin-server
```

✅ **ผลลัพธ์:** ระบบจะทำงานต่อโดยไม่ตรวจสอบกับ HR API (ยังคงบันทึกข้อมูลเช็คอินได้ปกติ)

---

### วิธีที่ 2: เปิดใช้งาน HR Verification ผ่าน Cloudflare Tunnel

ถ้า HR API อยู่ใน network เดียวกับที่มี Cloudflare Tunnel:

1. **Expose HR API ผ่าน Cloudflare:**
   ```bash
   # บนเครื่องที่มี HR API (10.10.110.7)
   cloudflared tunnel --url http://localhost:3000
   ```

2. **ได้ URL แบบ:** `https://random-name.trycloudflare.com`

3. **อัปเดต .env บน server:**
   ```bash
   ENABLE_HR_VERIFICATION=true
   HR_API_URL=https://random-name.trycloudflare.com/employee/search
   HR_API_TIMEOUT=10
   ```

4. **Restart:**
   ```bash
   sudo supervisorctl restart checkin-server
   ```

---

### วิธีที่ 3: ใช้ Public URL ของ HR API

ถ้า HR API มี public endpoint:

```bash
# แก้ไข .env
nano /var/www/linebot/.env

# เพิ่ม/แก้ไข
ENABLE_HR_VERIFICATION=true
HR_API_URL=https://your-hr-api.yourdomain.com/employee/search
HR_API_TIMEOUT=10
```

Restart:
```bash
sudo supervisorctl restart checkin-server
```

---

### วิธีที่ 4: ตั้งค่า VPN/VPC Peering (Advanced)

เชื่อมต่อ DigitalOcean server กับ internal network ที่มี HR API

---

## 🧪 ทดสอบ

### 1. ทดสอบว่า HR Verification ปิดอยู่:
```bash
tail -50 /var/www/linebot/logs/checkin-server.log
```

ควรเห็น:
```
🔧 HR System Integration:
   Enabled: ❌ No (disabled)
   ℹ️ Set ENABLE_HR_VERIFICATION=true in .env to enable
```

### 2. ทดสอบเช็คอิน:
เมื่อมีการเช็คอิน จะไม่เห็น error เรื่อง HR แล้ว และข้อความจะไม่มีบรรทัด "ยืนยันจากระบบ HR"

---

## 📊 ข้อมูลที่เก็บ

### เมื่อ ENABLE_HR_VERIFICATION=false:
```json
{
  "employeeCode": "EMP001",
  "employeeName": "นาย ทดสอบ ระบบ",
  "hrSystemVerified": false,
  "hrSystemData": null
}
```

### เมื่อ ENABLE_HR_VERIFICATION=true และเชื่อมต่อสำเร็จ:
```json
{
  "employeeCode": "EMP001",
  "employeeName": "นาย ทดสอบ ระบบ",
  "hrSystemVerified": true,
  "hrSystemData": {
    "employeeId": "EMP001",
    "name": "...",
    ...
  }
}
```

---

## 🔄 Deploy Steps

```bash
# 1. บน Local - Push code
cd /Users/Macbook/LineBotRegister
git add .
git commit -m "Add HR verification toggle with environment variables"
git push origin main

# 2. บน Server - Pull และ Update
ssh root@146.190.82.178
cd /var/www/linebot
git pull origin main

# 3. แก้ไข .env (เพิ่มบรรทัดนี้)
nano .env
# เพิ่ม: ENABLE_HR_VERIFICATION=false

# 4. Restart
sudo supervisorctl restart checkin-server

# 5. ตรวจสอบ
tail -50 /var/www/linebot/logs/checkin-server.log
```

---

## ✅ Checklist

- [ ] Pull code ล่าสุด
- [ ] เพิ่ม `ENABLE_HR_VERIFICATION=false` ใน `.env`
- [ ] Restart checkin-server
- [ ] ตรวจสอบ logs ว่าไม่มี HR error แล้ว
- [ ] ทดสอบเช็คอินจริง
- [ ] ตรวจสอบว่า LINE message ส่งสำเร็จ

---

## 🎯 แนะนำ

**ตอนนี้:** ปิด HR verification ไว้ก่อน (`ENABLE_HR_VERIFICATION=false`)

**ในอนาคต:** เมื่อมี public endpoint หรือ VPN พร้อม ค่อยเปิดใช้งานโดย:
1. เปลี่ยน `ENABLE_HR_VERIFICATION=true`
2. ตั้งค่า `HR_API_URL` ที่ถูกต้อง
3. Restart service

ระบบออกแบบให้ทำงานได้ดีในทั้ง 2 กรณี (มีและไม่มี HR verification) 🎉
