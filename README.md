# LINE Bot Registration Server

Server สำหรับจัดการข้อมูลการลงทะเบียนผ่าน LINE Bot พร้อม MongoDB

## 📋 Requirements

- Python 3.8+
- MongoDB (ติดตั้งและรันบนเครื่อง หรือใช้ MongoDB Atlas)

## 🚀 การติดตั้ง

1. **ติดตั้ง Dependencies**
```bash
pip install -r requirements.txt
```

2. **ตั้งค่า MongoDB**
   - ติดตั้ง MongoDB บนเครื่อง หรือ
   - ใช้ MongoDB Atlas (cloud)
   - แก้ไข `MONGO_URI` ใน `.env`

3. **สร้างไฟล์ .env**
```bash
cp .env.example .env
```

4. **แก้ไข .env**
```
MONGO_URI=mongodb://localhost:27017/
```

## ▶️ วิธีรัน Server

```bash
python server.py
```

Server จะรันที่: `http://localhost:5000`

## 📡 API Endpoints

### 1. Health Check
```
GET /api/health
```
ตรวจสอบสถานะ server และ MongoDB

### 2. ลงทะเบียนใหม่
```
POST /api/register
Content-Type: application/json

{
  "deptCode": "001",
  "deptName": "แผนกบริหาร",
  "empCode": "EMP001",
  "prefix": "นาย",
  "firstName": "สมชาย",
  "lastName": "ใจดี",
  "mobile": "0812345678",
  "lineId": "somchai123"
}
```

### 3. ดึงข้อมูลทั้งหมด
```
GET /api/registrations
```

### 4. ดึงข้อมูลตามรหัสพนักงาน
```
GET /api/registrations/<emp_code>
```

### 5. อัพเดทข้อมูล
```
PUT /api/registrations/<emp_code>
Content-Type: application/json

{
  "mobile": "0898765432",
  "lineId": "newlineid"
}
```

### 6. ลบข้อมูล
```
DELETE /api/registrations/<emp_code>
```

## 🗄️ โครงสร้าง MongoDB

**Database:** `linebot_register`  
**Collection:** `registrations`

### ตัวอย่างข้อมูล:
```json
{
  "_id": "ObjectId",
  "deptCode": "001",
  "deptName": "แผนกบริหาร",
  "empCode": "EMP001",
  "prefix": "นาย",
  "firstName": "สมชาย",
  "lastName": "ใจดี",
  "mobile": "0812345678",
  "lineId": "somchai123",
  "createdAt": "2025-11-05T10:30:00",
  "status": "active"
}
```

## 🛠️ การใช้งานกับ HTML Form

แก้ไข JavaScript ใน `register-form.html`:

```javascript
function handleSubmit(event) {
    event.preventDefault();
    
    const formData = {
        deptCode: document.getElementById('deptCode').value,
        deptName: document.getElementById('deptName').value,
        empCode: document.getElementById('empCode').value,
        prefix: document.getElementById('prefix').value,
        firstName: document.getElementById('firstName').value,
        lastName: document.getElementById('lastName').value,
        mobile: document.getElementById('mobile').value,
        lineId: document.getElementById('lineId').value
    };

    fetch('http://localhost:5000/api/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('ลงทะเบียนสำเร็จ!');
            document.getElementById('registerForm').reset();
        } else {
            alert('เกิดข้อผิดพลาด: ' + data.message);
        }
    })
    .catch(error => {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + error);
    });
}
```

## 🔒 Security Notes

- ใช้ environment variables สำหรับข้อมูลที่สำคัญ
- เพิ่ม authentication/authorization ก่อนใช้งานจริง
- ตรวจสอบและ validate ข้อมูลอย่างเข้มงวด
- ใช้ HTTPS ใน production

## 📝 License

MIT License
