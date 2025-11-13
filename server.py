from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import certifi
import hashlib
import hmac
import base64
import requests

# โหลด environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # เปิดใช้งาน CORS สำหรับการเชื่อมต่อจาก frontend

# เชื่อมต่อ MongoDB
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    raise ValueError("⚠️ กรุณาตั้งค่า MONGO_URI ในไฟล์ .env")

# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')

# เชื่อมต่อ MongoDB ด้วย SSL certificate verification
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['linebot_register']  # ชื่อ database
collection = db['registrations']  # ชื่อ collection

# Route สำหรับให้บริการ HTML file
@app.route('/')
def index():
    return send_from_directory('.', 'register-form.html')

# Route สำหรับให้บริการไฟล์ static (รูปภาพ)
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# API สำหรับลงทะเบียน
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # ตรวจสอบข้อมูลที่จำเป็น
        required_fields = ['deptCode', 'deptName', 'empCode', 'prefix', 'firstName', 'lastName', 'mobile', 'lineId']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'กรุณากรอก {field}'
                }), 400
        
        # ตรวจสอบว่ารหัสพนักงานซ้ำหรือไม่
        existing_emp = collection.find_one({'empCode': data['empCode']})
        if existing_emp:
            return jsonify({
                'success': False,
                'message': 'รหัสพนักงานนี้ถูกลงทะเบียนแล้ว'
            }), 400
        
        # ตรวจสอบว่า LINE User ID ซ้ำหรือไม่ (ถ้ามีการส่งมา)
        line_user_id = data.get('lineUserId', '')
        if line_user_id and line_user_id.strip():
            existing_line = collection.find_one({'lineUserId': line_user_id})
            if existing_line:
                return jsonify({
                    'success': False,
                    'message': 'บัญชี LINE นี้ถูกลงทะเบียนแล้ว'
                }), 400
        
        # เพิ่มข้อมูลเข้า MongoDB
        registration_data = {
            'deptCode': data['deptCode'],
            'deptName': data['deptName'],
            'empCode': data['empCode'],
            'prefix': data['prefix'],
            'firstName': data['firstName'],
            'lastName': data['lastName'],
            'mobile': data['mobile'],
            'lineId': data['lineId'],
            'lineUserId': data.get('lineUserId', ''),  # LINE User ID
            'lineDisplayName': data.get('lineDisplayName', ''),  # LINE Display Name
            'createdAt': datetime.now(),
            'status': 'active'
        }
        
        result = collection.insert_one(registration_data)
        
        return jsonify({
            'success': True,
            'message': 'ลงทะเบียนสำเร็จ',
            'id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }), 500

# API สำหรับดึงข้อมูลทั้งหมด
@app.route('/api/registrations', methods=['GET'])
def get_registrations():
    try:
        registrations = list(collection.find())
        # แปลง ObjectId เป็น string
        for reg in registrations:
            reg['_id'] = str(reg['_id'])
            if 'createdAt' in reg:
                reg['createdAt'] = reg['createdAt'].isoformat()
        
        return jsonify({
            'success': True,
            'data': registrations,
            'count': len(registrations)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }), 500

# API สำหรับดึงข้อมูลตาม ID
@app.route('/api/registrations/<emp_code>', methods=['GET'])
def get_registration(emp_code):
    try:
        registration = collection.find_one({'empCode': emp_code})
        
        if not registration:
            return jsonify({
                'success': False,
                'message': 'ไม่พบข้อมูล'
            }), 404
        
        # แปลง ObjectId เป็น string
        registration['_id'] = str(registration['_id'])
        if 'createdAt' in registration:
            registration['createdAt'] = registration['createdAt'].isoformat()
        
        return jsonify({
            'success': True,
            'data': registration
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }), 500

# API สำหรับอัพเดทข้อมูล
@app.route('/api/registrations/<emp_code>', methods=['PUT'])
def update_registration(emp_code):
    try:
        data = request.get_json()
        
        # ลบฟิลด์ที่ไม่ต้องการอัพเดท
        data.pop('_id', None)
        data.pop('empCode', None)
        data.pop('createdAt', None)
        
        data['updatedAt'] = datetime.now()
        
        result = collection.update_one(
            {'empCode': emp_code},
            {'$set': data}
        )
        
        if result.modified_count == 0:
            return jsonify({
                'success': False,
                'message': 'ไม่พบข้อมูลหรือข้อมูลไม่เปลี่ยนแปลง'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'อัพเดทข้อมูลสำเร็จ'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }), 500

# API สำหรับลบข้อมูล
@app.route('/api/registrations/<emp_code>', methods=['DELETE'])
def delete_registration(emp_code):
    try:
        result = collection.delete_one({'empCode': emp_code})
        
        if result.deleted_count == 0:
            return jsonify({
                'success': False,
                'message': 'ไม่พบข้อมูล'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'ลบข้อมูลสำเร็จ'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        }), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # ทดสอบการเชื่อมต่อ MongoDB
        client.server_info()
        return jsonify({
            'success': True,
            'message': 'Server is running',
            'mongodb': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Server is running but MongoDB connection failed',
            'error': str(e)
        }), 500

# LINE Bot Webhook - รับข้อความจาก LINE
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # ตรวจสอบ signature
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)
        
        print("=" * 50)
        print("🔔 Webhook received!")
        print(f"📝 Body: {body}")
        print("=" * 50)
        
        if LINE_CHANNEL_SECRET:
            hash_result = hmac.new(
                LINE_CHANNEL_SECRET.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).digest()
            signature_check = base64.b64encode(hash_result).decode('utf-8')
            
            if signature != signature_check:
                print("❌ Invalid signature!")
                return jsonify({'error': 'Invalid signature'}), 403
        
        # แปลง JSON
        events = request.get_json()
        
        if 'events' not in events:
            print("⚠️ No events in payload")
            return jsonify({'status': 'ok'}), 200
        
        print(f"📦 Events count: {len(events['events'])}")
        
        for event in events['events']:
            print(f"📨 Event type: {event.get('type')}")
            
            if event['type'] == 'message' and event['message']['type'] == 'text':
                user_id = event['source']['userId']
                text = event['message']['text'].strip().lower()
                
                print(f"👤 User ID: {user_id}")
                print(f"💬 Message: {text}")
                
                # ตรวจสอบคำว่า "personal"
                if text == 'personal':
                    print("✅ Matched 'personal' command!")
                    reply_token = event['replyToken']
                    send_personal_info(reply_token, user_id)
                else:
                    print(f"⚠️ Text '{text}' does not match 'personal'")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def send_personal_info(reply_token, user_id):
    """ส่งข้อมูลส่วนตัวกลับไปหาผู้ใช้"""
    
    try:
        print(f"🔍 Searching for user_id: {user_id}")
        
        # ค้นหาข้อมูลจาก lineUserId
        registrations = list(collection.find({'lineUserId': user_id}))
        
        print(f"📊 Found {len(registrations)} registration(s)")
        
        if not registrations:
            message_text = "❌ ไม่พบข้อมูลการลงทะเบียนของคุณในระบบ\n\nกรุณาลงทะเบียนก่อนใช้งาน"
        else:
            # สร้างข้อความแสดงข้อมูล
            message_text = f"ข้อมูลการลงทะเบียนของคุณ\n"
            for idx, reg in enumerate(registrations, 1):
                message_text += f"ชื่อ: {reg.get('prefix', '')} {reg.get('firstName', '')} {reg.get('lastName', '')}\n"
                message_text += f"หน่วยงาน: {reg.get('deptName', '')} ({reg.get('deptCode', '')})\n"
                message_text += f"รหัสพนักงาน: {reg.get('empCode', '')}\n"
                message_text += f"เบอร์: {reg.get('mobile', '')}\n"
                message_text += f"LINE: {reg.get('lineId', '')}\n"
                
                if 'createdAt' in reg:
                    # แปลงเวลา UTC เป็นเวลาไทย (UTC+7)
                    created_utc = reg['createdAt']
                    created_thai = created_utc + timedelta(hours=7)
                    created_date = created_thai.strftime('%d/%m/%Y %H:%M')
                    message_text += f"ลงทะเบียนเมื่อ: {created_date}"
                
                if idx < len(registrations):
                    message_text += "\n" + "─" * 23 + "\n\n"
        
        print(f"💬 Message to send: {message_text[:100]}...")
        
        # ส่งข้อความกลับผ่าน LINE Reply API
        if LINE_CHANNEL_ACCESS_TOKEN:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
            }
            
            payload = {
                'replyToken': reply_token,
                'messages': [{
                    'type': 'text',
                    'text': message_text
                }]
            }
            
            print(f"📤 Sending to LINE API...")
            
            response = requests.post(
                'https://api.line.me/v2/bot/message/reply',
                headers=headers,
                json=payload
            )
            
            print(f"📥 LINE API Response: {response.status_code}")
            print(f"📄 Response body: {response.text}")
            
            if response.status_code != 200:
                print(f"❌ LINE API Error: {response.text}")
        else:
            print("⚠️ LINE_CHANNEL_ACCESS_TOKEN is not set!")
        
    except Exception as e:
        print(f"❌ Send personal info error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("🚀 Server starting...")
    print(f"📊 MongoDB URI: {MONGO_URI}")
    print(f"📁 Database: linebot_register")
    print(f"📦 Collection: registrations")
    print("🌐 Server running on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
