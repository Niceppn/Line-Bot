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

# Route สำหรับให้บริการรูป profile
@app.route('/uploads/profiles/<path:filename>')
def serve_profile_photo(filename):
    upload_dir = 'uploads/profiles'
    if os.path.exists(os.path.join(upload_dir, filename)):
        return send_from_directory(upload_dir, filename)
    else:
        abort(404)

# API สำหรับลงทะเบียน
@app.route('/api/register', methods=['POST'])
def register():
    try:
        # ตรวจสอบว่าเป็น multipart/form-data หรือ JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # รับข้อมูลจาก form
            data = {
                'deptCode': request.form.get('deptCode'),
                'deptName': request.form.get('deptName'),
                'empCode': request.form.get('empCode'),
                'idCard': request.form.get('idCard'),
                'prefix': request.form.get('prefix'),
                'firstName': request.form.get('firstName'),
                'lastName': request.form.get('lastName'),
                'mobile': request.form.get('mobile'),
                'lineId': request.form.get('lineId'),
                'lineUserId': request.form.get('lineUserId', ''),
                'lineDisplayName': request.form.get('lineDisplayName', '')
            }
            
            # จัดการไฟล์รูปภาพ
            photo_filename = None
            if 'photo' in request.files:
                photo = request.files['photo']
                if photo and photo.filename:
                    # สร้างชื่อไฟล์ใหม่
                    ext = photo.filename.rsplit('.', 1)[1].lower() if '.' in photo.filename else 'jpg'
                    photo_filename = f"profile_{data['empCode']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                    
                    # สร้าง directory สำหรับเก็บรูป
                    upload_dir = 'uploads/profiles'
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # บันทึกไฟล์
                    photo_path = os.path.join(upload_dir, photo_filename)
                    photo.save(photo_path)
                    print(f"📸 Saved profile photo: {photo_filename}")
        else:
            # รับข้อมูลแบบ JSON (backward compatibility)
            data = request.get_json()
            photo_filename = None
        
        # ตรวจสอบข้อมูลที่จำเป็น
        required_fields = ['deptCode', 'deptName', 'empCode', 'idCard', 'prefix', 'firstName', 'lastName', 'mobile', 'lineId']
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
            'idCard': data['idCard'],
            'prefix': data['prefix'],
            'firstName': data['firstName'],
            'lastName': data['lastName'],
            'mobile': data['mobile'],
            'lineId': data['lineId'],
            'lineUserId': data.get('lineUserId', ''),  # LINE User ID
            'lineDisplayName': data.get('lineDisplayName', ''),  # LINE Display Name
            'photoFilename': photo_filename,  # ชื่อไฟล์รูปภาพ
            'createdAt': datetime.now(),
            'status': 'active'
        }
        
        result = collection.insert_one(registration_data)
        
        # ส่ง Flex Message Card กลับไปหาผู้ใช้
        if line_user_id and line_user_id.strip() and LINE_CHANNEL_ACCESS_TOKEN:
            send_registration_card(line_user_id, registration_data)
        
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

def send_registration_card(user_id, registration_data):
    """ส่ง Flex Message Card ยืนยันการลงทะเบียนกลับไปหาผู้ใช้"""
    
    try:
        print(f"📤 Sending registration card to user_id: {user_id}")
        
        # สร้าง Flex Message Card
        full_name = f"{registration_data.get('prefix', '')} {registration_data.get('firstName', '')} {registration_data.get('lastName', '')}"
        
        # แปลงเวลา UTC เป็นเวลาไทย (UTC+7)
        created_utc = registration_data.get('createdAt', datetime.now())
        created_thai = created_utc + timedelta(hours=7)
        created_date = created_thai.strftime('%d/%m/%Y %H:%M')
        
        # URL รูปโปรไฟล์
        photo_url = None
        if registration_data.get('photoFilename'):
            photo_url = f"https://nice-ppn.studio/uploads/profiles/{registration_data.get('photoFilename')}"
        
        # สร้าง Flex Message Content
        bubble_content = {
            "type": "bubble",
            "size": "mega"
        }
        
        # เพิ่มรูปถ้ามี
        if photo_url:
            bubble_content["hero"] = {
                "type": "image",
                "url": photo_url,
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover"
            }
        
        # Header
        bubble_content["header"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ ลงทะเบียนสำเร็จ",
                    "color": "#FFFFFF",
                    "size": "xl",
                    "weight": "bold",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "ยินดีต้อนรับเข้าสู่ระบบ",
                    "color": "#FFFFFF",
                    "size": "sm",
                    "align": "center",
                    "margin": "md"
                }
            ],
            "backgroundColor": "#06C755",
            "paddingAll": "20px"
        }
        
        # Body
        bubble_content["body"] = {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "ข้อมูลการลงทะเบียน",
                                    "size": "lg",
                                    "weight": "bold",
                                    "color": "#FF6B35"
                                }
                            ],
                            "margin": "none",
                            "spacing": "none"
                        },
                        {
                            "type": "separator",
                            "margin": "lg"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "ชื่อ-นามสกุล:",
                                            "size": "sm",
                                            "color": "#8C8C8C",
                                            "flex": 0,
                                            "weight": "bold"
                                        },
                                        {
                                            "type": "text",
                                            "text": full_name,
                                            "size": "sm",
                                            "color": "#111111",
                                            "flex": 0,
                                            "margin": "md",
                                            "wrap": True
                                        }
                                    ],
                                    "spacing": "sm",
                                    "margin": "lg"
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "หน่วยงาน:",
                                            "size": "sm",
                                            "color": "#8C8C8C",
                                            "flex": 0,
                                            "weight": "bold"
                                        },
                                        {
                                            "type": "text",
                                            "text": f"{registration_data.get('deptName', '')} ({registration_data.get('deptCode', '')})",
                                            "size": "sm",
                                            "color": "#111111",
                                            "flex": 0,
                                            "margin": "md",
                                            "wrap": True
                                        }
                                    ],
                                    "spacing": "sm",
                                    "margin": "md"
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "รหัสพนักงาน:",
                                            "size": "sm",
                                            "color": "#8C8C8C",
                                            "flex": 0,
                                            "weight": "bold"
                                        },
                                        {
                                            "type": "text",
                                            "text": registration_data.get('empCode', ''),
                                            "size": "sm",
                                            "color": "#111111",
                                            "flex": 0,
                                            "margin": "md"
                                        }
                                    ],
                                    "spacing": "sm",
                                    "margin": "md"
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "เบอร์โทร:",
                                            "size": "sm",
                                            "color": "#8C8C8C",
                                            "flex": 0,
                                            "weight": "bold"
                                        },
                                        {
                                            "type": "text",
                                            "text": registration_data.get('mobile', ''),
                                            "size": "sm",
                                            "color": "#111111",
                                            "flex": 0,
                                            "margin": "md"
                                        }
                                    ],
                                    "spacing": "sm",
                                    "margin": "md"
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "LINE ID:",
                                            "size": "sm",
                                            "color": "#8C8C8C",
                                            "flex": 0,
                                            "weight": "bold"
                                        },
                                        {
                                            "type": "text",
                                            "text": registration_data.get('lineId', ''),
                                            "size": "sm",
                                            "color": "#111111",
                                            "flex": 0,
                                            "margin": "md"
                                        }
                                    ],
                                    "spacing": "sm",
                                    "margin": "md"
                                }
                            ]
                        },
                        {
                            "type": "separator",
                            "margin": "lg"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"ลงทะเบียนเมื่อ: {created_date}",
                                    "size": "xs",
                                    "color": "#AAAAAA",
                                    "align": "center"
                                }
                            ],
                            "margin": "lg"
                        }
                    ],
                    "spacing": "md",
                    "paddingAll": "20px"
                }
        
        # Footer
        bubble_content["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "บริษัทโอวาทเมท",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "align": "center",
                    "weight": "bold"
                }
            ],
            "paddingAll": "10px"
        }
        
        # สร้าง Flex Message
        flex_message = {
            "type": "flex",
            "altText": "✅ ลงทะเบียนสำเร็จ!",
            "contents": bubble_content
        }
        
        # ส่งข้อความผ่าน LINE Push Message API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        payload = {
            'to': user_id,
            'messages': [flex_message]
        }
        
        print(f"📤 Sending Flex Message to LINE API...")
        
        response = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers=headers,
            json=payload
        )
        
        print(f"📥 LINE API Response: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ LINE API Error: {response.text}")
        else:
            print(f"✅ Registration card sent successfully!")
        
    except Exception as e:
        print(f"❌ Send registration card error: {str(e)}")
        import traceback
        traceback.print_exc()

def send_personal_info(reply_token, user_id):
    """ส่งข้อมูลส่วนตัวกลับไปหาผู้ใช้"""
    
    try:
        print(f"🔍 Searching for user_id: {user_id}")
        
        # ค้นหาข้อมูลจาก lineUserId
        registrations = list(collection.find({'lineUserId': user_id}))
        
        print(f"📊 Found {len(registrations)} registration(s)")
        
        if not registrations:
            # ถ้าไม่พบข้อมูล ส่งข้อความแจ้งเตือน
            message = {
                'type': 'text',
                'text': "❌ ไม่พบข้อมูลการลงทะเบียนของคุณในระบบ\n\nกรุณาลงทะเบียนก่อนใช้งาน"
            }
        else:
            # ส่ง Flex Message Card สำหรับข้อมูลแรก
            reg = registrations[0]
            
            # สร้างข้อมูล
            full_name = f"{reg.get('prefix', '')} {reg.get('firstName', '')} {reg.get('lastName', '')}"
            
            # แปลงเวลา UTC เป็นเวลาไทย (UTC+7)
            if 'createdAt' in reg:
                created_utc = reg['createdAt']
                created_thai = created_utc + timedelta(hours=7)
                created_date = created_thai.strftime('%d/%m/%Y %H:%M')
            else:
                created_date = '-'
            
            # URL รูปโปรไฟล์
            photo_url = None
            if reg.get('photoFilename'):
                photo_url = f"https://nice-ppn.studio/uploads/profiles/{reg.get('photoFilename')}"
            
            # สร้าง Flex Message Content
            bubble_content = {
                "type": "bubble",
                "size": "mega"
            }
            
            # เพิ่มรูปถ้ามี
            if photo_url:
                bubble_content["hero"] = {
                    "type": "image",
                    "url": photo_url,
                    "size": "full",
                    "aspectRatio": "20:13",
                    "aspectMode": "cover"
                }
            
            # Header
            bubble_content["header"] = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📋 ข้อมูลส่วนตัว",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": "ข้อมูลการลงทะเบียนของคุณ",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "align": "center",
                        "margin": "md"
                    }
                ],
                "backgroundColor": "#FF6B35",
                "paddingAll": "20px"
            }
            
            # Body
            bubble_content["body"] = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "ข้อมูลการลงทะเบียน",
                                "size": "lg",
                                "weight": "bold",
                                "color": "#FF6B35"
                            }
                        ],
                        "margin": "none",
                        "spacing": "none"
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "ชื่อ-นามสกุล:",
                                        "size": "sm",
                                        "color": "#8C8C8C",
                                        "flex": 0,
                                        "weight": "bold"
                                    },
                                    {
                                        "type": "text",
                                        "text": full_name,
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 0,
                                        "margin": "md",
                                        "wrap": True
                                    }
                                ],
                                "spacing": "sm",
                                "margin": "lg"
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "หน่วยงาน:",
                                        "size": "sm",
                                        "color": "#8C8C8C",
                                        "flex": 0,
                                        "weight": "bold"
                                    },
                                    {
                                        "type": "text",
                                        "text": f"{reg.get('deptName', '')} ({reg.get('deptCode', '')})",
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 0,
                                        "margin": "md",
                                        "wrap": True
                                    }
                                ],
                                "spacing": "sm",
                                "margin": "md"
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "รหัสพนักงาน:",
                                        "size": "sm",
                                        "color": "#8C8C8C",
                                        "flex": 0,
                                        "weight": "bold"
                                    },
                                    {
                                        "type": "text",
                                        "text": reg.get('empCode', ''),
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 0,
                                        "margin": "md"
                                    }
                                ],
                                "spacing": "sm",
                                "margin": "md"
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "เบอร์โทร:",
                                        "size": "sm",
                                        "color": "#8C8C8C",
                                        "flex": 0,
                                        "weight": "bold"
                                    },
                                    {
                                        "type": "text",
                                        "text": reg.get('mobile', ''),
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 0,
                                        "margin": "md"
                                    }
                                ],
                                "spacing": "sm",
                                "margin": "md"
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "LINE ID:",
                                        "size": "sm",
                                        "color": "#8C8C8C",
                                        "flex": 0,
                                        "weight": "bold"
                                    },
                                    {
                                        "type": "text",
                                        "text": reg.get('lineId', ''),
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 0,
                                        "margin": "md"
                                    }
                                ],
                                "spacing": "sm",
                                "margin": "md"
                            }
                        ]
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"ลงทะเบียนเมื่อ: {created_date}",
                                "size": "xs",
                                "color": "#AAAAAA",
                                "align": "center"
                            }
                        ],
                        "margin": "lg"
                    }
                ],
                "spacing": "md",
                "paddingAll": "20px"
            }
            
            # Footer
            bubble_content["footer"] = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "บริษัทโอวาทเมท",
                        "size": "xs",
                        "color": "#AAAAAA",
                        "align": "center",
                        "weight": "bold"
                    }
                ],
                "paddingAll": "10px"
            }
            
            message = {
                "type": "flex",
                "altText": "📋 ข้อมูลส่วนตัว",
                "contents": bubble_content
            }
        
        print(f"💬 Sending message...")
        
        # ส่งข้อความกลับผ่าน LINE Reply API
        if LINE_CHANNEL_ACCESS_TOKEN:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
            }
            
            payload = {
                'replyToken': reply_token,
                'messages': [message]
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
