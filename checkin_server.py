#!/usr/bin/env python3
"""
Check-In Server for LINE Bot HRM System
Handles photo uploads and location check-ins with LINE integration
"""

import http.server
import socketserver
import json
import os
from datetime import datetime
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import urllib.parse
from http import HTTPStatus
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Server Configuration
PORT = 3001
UPLOAD_DIR = "uploads"
CHECKIN_DATA_FILE = "checkin_records.json"

# LINE Bot credentials
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', "EHs9UYuvVMpF+asLjjaeXNr0ogBn1odOS0ehdVvHdrdFHTB6oAdh0C4y3escock9iu/VVYquwoCZRBtSgg/3+Nl9jEu8XIbUhObqkjoRiyCZc45s51PjGUt8bX9dX+Ca02ZZdBYy1TRndwrS4RzxdQdB04t89/1O/w1cDnyilFU=")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://niceppn:XCFyloY5PT1DSfOb@cluster0.ljo0j.mongodb.net/linebot_register?retryWrites=true&w=majority')
try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client['linebot_register']
    registrations_collection = db['registrations']
    checkins_collection = db['checkins']
    print("✅ Connected to MongoDB successfully")
except Exception as e:
    print(f"⚠️ MongoDB connection failed: {e}")
    mongo_client = None
    db = None
    registrations_collection = None
    checkins_collection = None


# Create necessary directories
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
    print(f"📂 Created upload directory: {UPLOAD_DIR}")

def get_employee_by_line_user_id(line_user_id):
    """Get employee data from MongoDB by LINE User ID"""
    if not registrations_collection:
        print("⚠️ MongoDB not connected, cannot lookup employee")
        return None
    
    try:
        employee = registrations_collection.find_one({"lineUserId": line_user_id})
        if employee:
            print(f"✅ Found employee: {employee.get('firstName')} {employee.get('lastName')}")
            return employee
        else:
            print(f"⚠️ No employee found for LINE User ID: {line_user_id}")
            return None
    except Exception as e:
        print(f"❌ Error looking up employee: {e}")
        return None

def load_checkin_records():
    """Load check-in records from JSON file"""
    if os.path.exists(CHECKIN_DATA_FILE):
        try:
            with open(CHECKIN_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading check-in records: {e}")
            return []
    return []

def save_checkin_record(record):
    """Save check-in record to JSON file"""
    try:
        records = load_checkin_records()
        records.append(record)
        
        with open(CHECKIN_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved check-in record for {record.get('employeeName', 'Unknown')}")
        return True
    except Exception as e:
        print(f"Error saving check-in record: {e}")
        return False

def add_watermark_to_image(image_data, latitude, longitude, address, timestamp):
    """Add watermark with GPS coordinates and timestamp to image"""
    try:
        # Open image
        img = Image.open(io.BytesIO(image_data))
        
        # Create drawing context
        draw = ImageDraw.Draw(img)
        
        # Try to use a better font, fallback to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
            small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Format timestamp
        thai_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime("%d/%m/%Y %H:%M:%S")
        
        # Watermark text
        watermark_lines = [
            f"📍 GPS: {latitude:.6f}, {longitude:.6f}",
            f"🕐 {thai_time}",
            f"📌 {address[:50]}..."  # Truncate long addresses
        ]
        
        # Position watermark at bottom
        width, height = img.size
        y_position = height - 120
        
        # Draw semi-transparent background
        for i, line in enumerate(watermark_lines):
            # Draw black background for text
            bbox = draw.textbbox((10, y_position + i * 35), line, font=small_font)
            draw.rectangle(bbox, fill=(0, 0, 0, 180))
            # Draw white text
            draw.text((10, y_position + i * 35), line, fill=(255, 255, 255), font=small_font)
        
        # Save to bytes
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=90)
        output.seek(0)
        
        return output.read()
    
    except Exception as e:
        print(f"Error adding watermark: {e}")
        return image_data  # Return original if watermarking fails

def send_line_message(user_id, messages):
    """Send message to LINE user"""
    if not LINE_CHANNEL_ACCESS_TOKEN or not user_id:
        print("⚠️ Missing LINE token or user ID")
        return False
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    data = {
        'to': user_id,
        'messages': messages
    }
    
    try:
        response = requests.post(LINE_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            print(f"✅ Message sent successfully to {user_id}")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending LINE message: {e}")
        return False

class CheckInHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for check-in system"""
    
    def do_GET(self):
        """Handle GET requests"""
        
        # Serve uploaded images
        if self.path.startswith('/uploads/'):
            file_path = self.path[1:]  # Remove leading slash
            if os.path.exists(file_path) and file_path.startswith('uploads/'):
                self.send_response(200)
                
                if file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                    self.send_header('Content-Type', 'image/jpeg')
                elif file_path.endswith('.png'):
                    self.send_header('Content-Type', 'image/png')
                
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
        
        # Get all check-in records
        elif self.path == '/api/checkins':
            try:
                records = load_checkin_records()
                
                response = {
                    "success": True,
                    "message": "ดึงข้อมูลเช็คอินสำเร็จ",
                    "count": len(records),
                    "records": records
                }
                
                self.send_json_response(200, response)
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        
        # Get today's check-ins
        elif self.path == '/api/checkins/today':
            try:
                records = load_checkin_records()
                today = datetime.now().strftime("%Y-%m-%d")
                
                today_records = [r for r in records if r.get('date') == today]
                
                response = {
                    "success": True,
                    "message": f"ข้อมูลเช็คอินวันนี้ ({today})",
                    "date": today,
                    "count": len(today_records),
                    "records": today_records
                }
                
                self.send_json_response(200, response)
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        
        # Get check-ins by employee
        elif self.path.startswith('/api/checkins/employee/'):
            try:
                employee_code = self.path.split('/')[-1]
                records = load_checkin_records()
                
                employee_records = [r for r in records if r.get('employeeCode') == employee_code]
                
                response = {
                    "success": True,
                    "message": f"ข้อมูลเช็คอินของพนักงาน {employee_code}",
                    "employeeCode": employee_code,
                    "count": len(employee_records),
                    "records": employee_records
                }
                
                self.send_json_response(200, response)
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        
        # Health check endpoint
        elif self.path == '/api/health':
            response = {
                "status": "OK",
                "message": "Check-In Server is running",
                "timestamp": datetime.now().isoformat(),
                "upload_dir": os.path.abspath(UPLOAD_DIR),
                "total_checkins": len(load_checkin_records())
            }
            self.send_json_response(200, response)
        
        else:
            # Default 404
            self.send_json_response(404, {"error": "Endpoint not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        
        # Handle photo upload with location
        if self.path == '/api/upload-photo':
            try:
                content_type = self.headers.get('Content-Type', '')
                
                if 'multipart/form-data' in content_type:
                    # Parse multipart form data
                    boundary = content_type.split('boundary=')[1].encode()
                    content_length = int(self.headers['Content-Length'])
                    body = self.rfile.read(content_length)
                    
                    # Extract image and metadata
                    parts = body.split(b'--' + boundary)
                    
                    image_data = None
                    latitude = None
                    longitude = None
                    address = "ไม่ระบุที่อยู่"
                    timestamp = datetime.now().isoformat()
                    
                    for part in parts:
                        if b'Content-Disposition' in part:
                            if b'name="image"' in part:
                                # Extract image data
                                image_start = part.find(b'\r\n\r\n') + 4
                                image_end = part.rfind(b'\r\n')
                                image_data = part[image_start:image_end]
                            
                            elif b'name="latitude"' in part:
                                value_start = part.find(b'\r\n\r\n') + 4
                                value_end = part.rfind(b'\r\n')
                                latitude = float(part[value_start:value_end].decode())
                            
                            elif b'name="longitude"' in part:
                                value_start = part.find(b'\r\n\r\n') + 4
                                value_end = part.rfind(b'\r\n')
                                longitude = float(part[value_start:value_end].decode())
                            
                            elif b'name="address"' in part:
                                value_start = part.find(b'\r\n\r\n') + 4
                                value_end = part.rfind(b'\r\n')
                                address = part[value_start:value_end].decode('utf-8')
                            
                            elif b'name="timestamp"' in part:
                                value_start = part.find(b'\r\n\r\n') + 4
                                value_end = part.rfind(b'\r\n')
                                timestamp = part[value_start:value_end].decode()
                    
                    if not image_data or latitude is None or longitude is None:
                        raise ValueError("Missing required fields: image, latitude, or longitude")
                    
                    # Add watermark to image
                    watermarked_image = add_watermark_to_image(
                        image_data, latitude, longitude, address, timestamp
                    )
                    
                    # Save image with timestamp
                    filename = f"checkin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    filepath = os.path.join(UPLOAD_DIR, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(watermarked_image)
                    
                    print(f"📸 Photo saved: {filename}")
                    
                    # Generate public URL (adjust domain as needed)
                    # TODO: Change this to your actual domain
                    image_url = f"https://nice-ppn.studio/uploads/{filename}"
                    
                    response = {
                        "success": True,
                        "message": "อัปโหลดรูปภาพสำเร็จ",
                        "imageUrl": image_url,
                        "filename": filename,
                        "latitude": latitude,
                        "longitude": longitude,
                        "address": address,
                        "timestamp": timestamp
                    }
                    
                    self.send_json_response(200, response)
                else:
                    raise ValueError("Invalid Content-Type, expected multipart/form-data")
                
            except Exception as e:
                print(f"❌ Upload photo error: {e}")
                self.send_json_response(500, {"success": False, "error": str(e)})
        
        # Handle location data from LIFF app
        elif self.path == '/api/location-from-liff':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                print(f"📍 Location from LIFF: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                user_id = data.get('userId')
                display_name = data.get('displayName', 'ผู้ใช้')
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                address = data.get('address', 'ไม่ระบุที่อยู่')
                has_photo = data.get('hasPhoto', False)
                accuracy = data.get('accuracy', 0)
                timestamp = data.get('timestamp', datetime.now().isoformat())
                
                # Get current time in Thai format
                thai_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                date_only = datetime.now().strftime("%Y-%m-%d")
                
                # Find employee by LINE user ID from MongoDB
                employee = get_employee_by_line_user_id(user_id)
                
                # Prepare check-in record
                checkin_record = {
                    "timestamp": timestamp,
                    "date": date_only,
                    "thaiTime": thai_time,
                    "lineUserId": user_id,
                    "displayName": display_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "address": address,
                    "accuracy": accuracy,
                    "hasPhoto": has_photo,
                    "source": data.get('source', 'liff-gps')
                }
                
                if not employee:
                    print(f"⚠️ Employee not found for LINE user ID: {user_id}")
                    
                    checkin_record.update({
                        "employeeCode": None,
                        "employeeName": display_name,
                        "department": None,
                        "position": None,
                        "status": "unregistered"
                    })
                    
                    success_message = f"⚠️ เช็คอินสำเร็จ แต่ยังไม่ได้ลงทะเบียนพนักงาน!\n\n"
                    success_message += f"👤 ชื่อ: {display_name}\n"
                    success_message += f"📍 ตำแหน่ง: {address}\n"
                    success_message += f"🕐 เวลา: {thai_time}\n"
                    success_message += f"📷 รูปถ่าย: {'✅ มี' if has_photo else '❌ ไม่มี'}\n"
                    success_message += f"🎯 GPS: {latitude:.6f}, {longitude:.6f}\n"
                    success_message += f"📡 ความแม่นยำ: {accuracy:.0f} เมตร\n\n"
                    success_message += f"📝 กรุณาติดต่อ HR เพื่อลงทะเบียน"
                else:
                    # Extract employee data from MongoDB
                    employee_code = employee.get('empCode', 'N/A')
                    employee_name = f"{employee.get('prefix', '')} {employee.get('firstName', '')} {employee.get('lastName', '')}".strip()
                    department = employee.get('deptName', 'N/A')
                    position = 'พนักงาน'  # MongoDB schema ไม่มี position field
                    
                    checkin_record.update({
                        "employeeCode": employee_code,
                        "employeeName": employee_name,
                        "department": department,
                        "position": position,
                        "status": "registered"
                    })
                    
                    # Create success message
                    success_message = f"✅ เช็คอินสำเร็จ!\n\n"
                    success_message += f"👤 ชื่อ: {employee_name}\n"
                    success_message += f"🆔 รหัสพนักงาน: {employee_code}\n"
                    success_message += f"🏢 แผนก: {department}\n"
                    success_message += f"💼 ตำแหน่ง: {position}\n"
                    success_message += f"📍 สถานที่: {address}\n"
                    success_message += f"🕐 เวลา: {thai_time}\n"
                    success_message += f"📷 รูปถ่าย: {'✅ มี' if has_photo else '❌ ไม่มี'}\n"
                    success_message += f"🎯 GPS: {latitude:.6f}, {longitude:.6f}\n"
                    success_message += f"📡 ความแม่นยำ: {accuracy:.0f} เมตร\n"
                    success_message += f"💾 บันทึกข้อมูล: ✅ สำเร็จ"
                
                # Save check-in record
                save_checkin_record(checkin_record)
                
                # Prepare LINE messages
                messages = [{"type": "text", "text": success_message}]
                
                # If has photo, try to find and send it
                if has_photo:
                    try:
                        photo_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.jpg')]
                        if photo_files:
                            latest_photo = max(photo_files, key=lambda x: os.path.getctime(os.path.join(UPLOAD_DIR, x)))
                            # TODO: Change this to your actual domain
                            photo_url = f"https://nice-ppn.studio/uploads/{latest_photo}"
                            
                            messages.insert(0, {
                                "type": "image",
                                "originalContentUrl": photo_url,
                                "previewImageUrl": photo_url
                            })
                            print(f"📸 Adding photo to message: {photo_url}")
                    except Exception as photo_error:
                        print(f"⚠️ Error adding photo to message: {photo_error}")
                
                # Send message to user
                send_result = send_line_message(user_id, messages)
                if send_result:
                    print(f"✅ Confirmation message sent to {display_name}")
                else:
                    print(f"⚠️ Failed to send confirmation message to {display_name}")
                
                # Return success response
                response = {
                    "success": True,
                    "message": "บันทึกการเช็คอินสำเร็จ",
                    "record": checkin_record
                }
                
                self.send_json_response(200, response)
                
            except Exception as e:
                print(f"❌ Location API error: {e}")
                import traceback
                traceback.print_exc()
                self.send_json_response(500, {"success": False, "error": str(e)})
        
        else:
            self.send_json_response(404, {"error": "Endpoint not found"})
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def send_json_response(self, status_code, data):
        """Helper method to send JSON responses"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to customize log format"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def main():
    """Start the check-in server"""
    print("=" * 60)
    print("🚀 Check-In Server for LINE Bot HRM System")
    print("=" * 60)
    
    with socketserver.TCPServer(("", PORT), CheckInHandler) as httpd:
        print(f"\n📡 Server running at http://localhost:{PORT}/")
        print(f"\n📋 Available API Endpoints:")
        print(f"   GET  /api/health              - Health check")
        print(f"   GET  /api/checkins            - Get all check-ins")
        print(f"   GET  /api/checkins/today      - Get today's check-ins")
        print(f"   GET  /api/checkins/employee/{{id}} - Get check-ins by employee")
        print(f"   POST /api/upload-photo        - Upload photo with GPS")
        print(f"   POST /api/location-from-liff  - Receive location from LIFF")
        print(f"   GET  /uploads/{{filename}}    - Serve uploaded images")
        
        print(f"\n💾 Storage:")
        print(f"   📂 Upload directory: {os.path.abspath(UPLOAD_DIR)}")
        print(f"   📄 Records file: {os.path.abspath(CHECKIN_DATA_FILE)}")
        print(f"   📊 Total records: {len(load_checkin_records())}")
        
        print(f"\n� Database:")
        if registrations_collection:
            employee_count = registrations_collection.count_documents({})
            print(f"   👥 Registered Employees: {employee_count}")
            # Show first 3 employees
            employees = list(registrations_collection.find().limit(3))
            for emp in employees:
                name = f"{emp.get('prefix', '')} {emp.get('firstName', '')} {emp.get('lastName', '')}".strip()
                emp_code = emp.get('empCode', 'N/A')
                dept = emp.get('deptName', 'N/A')
                print(f"   - {emp_code}: {name} ({dept})")
        else:
            print(f"   ⚠️ MongoDB not connected")
        
        print(f"\n✅ Server is ready!")
        print(f"🔗 Access from: http://localhost:{PORT}/api/health")
        print("\nPress Ctrl+C to stop the server\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down server...")
            print("✅ Server stopped gracefully")

if __name__ == "__main__":
    main()
