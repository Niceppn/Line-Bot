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

# HR System Configuration
ENABLE_HR_VERIFICATION = os.getenv('ENABLE_HR_VERIFICATION', 'false').lower() == 'true'
HR_API_URL = os.getenv('HR_API_URL', 'http://10.10.110.7:3000/employee/search')
HR_API_TIMEOUT = int(os.getenv('HR_API_TIMEOUT', '5'))

# LINE Bot credentials - ใช้ Token เดียวกับระบบลงทะเบียน
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
if not LINE_CHANNEL_ACCESS_TOKEN:
    print("⚠️ Warning: LINE_CHANNEL_ACCESS_TOKEN not found in .env file")
    print("   Messages will not be sent to LINE users")

LINE_API_URL = "https://api.line.me/v2/bot/message/push"

# MongoDB Configuration - ใช้ MONGO_URI เดียวกับระบบลงทะเบียน
MONGODB_URI = os.getenv('MONGO_URI', os.getenv('MONGODB_URI', 'mongodb+srv://niceppn:XCFyloY5PT1DSfOb@cluster0.ljo0j.mongodb.net/linebot_register?retryWrites=true&w=majority'))
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

def verify_employee_code_with_hr_system(employee_code):
    """Verify employee code with HR API system"""
    if not employee_code:
        return None
    
    # Check if HR verification is enabled
    if not ENABLE_HR_VERIFICATION:
        print(f"ℹ️ HR verification is disabled (ENABLE_HR_VERIFICATION=false)")
        return None
    
    try:
        print(f"🔍 Verifying employee code '{employee_code}' with HR system...")
        print(f"   HR API URL: {HR_API_URL}")
        print(f"   Timeout: {HR_API_TIMEOUT}s")
        
        response = requests.post(
            HR_API_URL,
            json={"employeeId": employee_code},
            headers={'Content-Type': 'application/json'},
            timeout=HR_API_TIMEOUT
        )
        
        print(f"   HR API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            hr_data = response.json()
            
            # HR API returns {"employees": [...]} format
            if hr_data and isinstance(hr_data, dict) and 'employees' in hr_data:
                employees_list = hr_data.get('employees', [])
                print(f"   HR API returned {len(employees_list)} employee(s)")
                
                # Filter by employeeId matching our employee_code
                matching_employee = None
                for emp in employees_list:
                    if str(emp.get('employeeId', '')) == str(employee_code):
                        matching_employee = emp
                        break
                
                if matching_employee:
                    print(f"✅ Employee verified in HR system")
                    print(f"   Found: {matching_employee.get('prefix', '')} {matching_employee.get('name', '')} {matching_employee.get('lastName', '')}")
                    return matching_employee
                else:
                    print(f"⚠️ Employee code '{employee_code}' not found in HR system")
                    return None
            else:
                print(f"⚠️ Unexpected HR API response format")
                return None
        else:
            print(f"❌ HR API returned error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"⚠️ HR API timeout ({HR_API_TIMEOUT}s) - continuing without verification")
        return None
    except requests.exceptions.ConnectionError:
        print(f"⚠️ Cannot connect to HR API ({HR_API_URL}) - continuing without verification")
        return None
    except Exception as e:
        print(f"⚠️ Error verifying with HR system: {e}")
        return None

def create_time_record(employee_code, employee_name, dept_code, dept_name, checkin_datetime, shift="", checkin_type="in", line_user_id=None):
    """Create or update time record in HR system"""
    try:
        # Parse datetime
        from datetime import datetime
        dt = datetime.fromisoformat(checkin_datetime.replace('Z', '+00:00'))
        
        # Extract date components
        year = str(dt.year)
        month = str(dt.month)
        day = str(dt.day)
        current_time = f"{dt.hour:02d}.{dt.minute:02d}"
        date_str = f"{year}-{month}-{day}"
        
        checkin_type_text = "เข้างาน" if checkin_type == "in" else "ออกงาน"
        
        # If checking out, get employeeRecordId from MongoDB
        if checkin_type == "out" and line_user_id:
            print(f"🔍 Checking out - looking for today's record in MongoDB...")
            try:
                # Get employee record from MongoDB to find today's employeeRecordId
                if registrations_collection:
                    employee = registrations_collection.find_one({"lineUserId": line_user_id})
                    if employee and 'todayCheckin' in employee:
                        today_checkin = employee.get('todayCheckin', {})
                        saved_date = today_checkin.get('date')
                        record_id = today_checkin.get('employeeRecordId')
                        start_time = today_checkin.get('startTime')
                        
                        print(f"   Saved date: {saved_date}")
                        print(f"   Current date: {date_str}")
                        print(f"   Record ID: {record_id}")
                        print(f"   Start Time: {start_time}")
                        
                        if saved_date == date_str and record_id and start_time:
                            end_time = current_time
                            
                            # Calculate total time (endTime - startTime)
                            try:
                                start_h, start_m = map(int, start_time.split('.'))
                                end_h, end_m = map(int, end_time.split('.'))
                                
                                total_minutes = (end_h * 60 + end_m) - (start_h * 60 + start_m)
                                total_hours = total_minutes / 60
                                total_time = f"{total_hours:.2f}"
                                
                                print(f"   ⏰ Calculated total time: {total_time} hours ({start_time} - {end_time})")
                            except:
                                total_time = ""
                                print(f"   ⚠️ Could not calculate total time")
                            
                            # Prepare UPDATE payload (include startTime to preserve it)
                            update_payload = {
                                "startTime": start_time,
                                "endTime": end_time,
                                "totalTime": total_time
                            }
                            
                            # Use PUT endpoint to UPDATE existing record
                            update_url = f"http://10.10.110.7:3000/timerecord/updatetimerecordemployee/{record_id}"
                            print(f"📝 Updating time record {record_id}...")
                            print(f"   Type: {checkin_type_text}")
                            print(f"   API: {update_url}")
                            print(f"   Date: {date_str}")
                            print(f"   Start Time: {start_time}")
                            print(f"   End Time: {end_time}")
                            print(f"   Total Time: {total_time}")
                            
                            update_response = requests.put(
                                update_url,
                                json=update_payload,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
                            
                            if update_response.status_code == 200:
                                print(f"✅ Time record updated successfully")
                                # Clear today's check-in data after successful check-out
                                registrations_collection.update_one(
                                    {"lineUserId": line_user_id},
                                    {"$unset": {"todayCheckin": ""}}
                                )
                                return record_id
                            else:
                                print(f"⚠️ Update API returned status {update_response.status_code}")
                                print(f"   Response: {update_response.text}")
                                return None
                        else:
                            print(f"   ⚠️ No matching check-in record found for today")
                    else:
                        print(f"   ⚠️ No todayCheckin data found in MongoDB")
                        
            except Exception as e:
                print(f"   ❌ Error looking up check-in record: {str(e)}")
        
        # If check-in or check-out without existing record, create new
        payload = {
            "year": year,
            "employeeId": employee_code,
            "employeeName": employee_name,
            "month": month,
            "employee_record": [
                {
                    "workplaceId": dept_code,
                    "workplaceName": dept_name,
                    "wGroup": "",
                    "date": day,
                    "shift": shift,
                    "startTime": current_time if checkin_type == "in" else "",
                    "endTime": current_time if checkin_type == "out" else "",
                    "totalTime": "",
                    "startOtTime": "",
                    "endOtTime": "",
                    "totalOtTime": ""
                }
            ]
        }
        
        print(f"📝 Creating time record for employee {employee_code}...")
        print(f"   Type: {checkin_type_text}")
        print(f"   API: http://10.10.110.7:3000/timerecord/createtimerecordemployee")
        print(f"   Date: {year}-{month}-{day}")
        print(f"   Start Time: {payload['employee_record'][0]['startTime'] or 'N/A'}")
        print(f"   End Time: {payload['employee_record'][0]['endTime'] or 'N/A'}")
        print(f"   Total Time: {payload['employee_record'][0]['totalTime'] or 'N/A'}")
        
        response = requests.post(
            "http://10.10.110.7:3000/timerecord/createtimerecordemployee",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Time record created successfully")
            # Extract employeeRecordId from response
            response_data = response.json()
            employee_record_id = None
            if response_data and 'result' in response_data:
                records = response_data['result'].get('employee_record', [])
                if records and len(records) > 0:
                    employee_record_id = records[0].get('_id')
                    print(f"   Employee Record ID: {employee_record_id}")
            return employee_record_id
        else:
            print(f"⚠️ Time record API returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error creating time record: {e}")
        return False

def get_employee_by_line_user_id(line_user_id):
    """Get employee data from MongoDB by LINE User ID"""
    if registrations_collection is None:
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

def add_watermark_to_image(image_data, latitude, longitude, address, timestamp, employee_data=None):
    """Add watermark with GPS coordinates and timestamp to image"""
    try:
        # Open image
        img = Image.open(io.BytesIO(image_data))
        
        # Create drawing context
        draw = ImageDraw.Draw(img)
        
        # Try to use a better font, fallback to default
        # Support both Ubuntu and macOS font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu
            "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Ubuntu alternative
        ]
        
        font = None
        small_font = None
        
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 24)
                small_font = ImageFont.truetype(font_path, 18)
                print(f"✅ Using font: {font_path}")
                break
            except:
                continue
        
        if not font:
            print("⚠️ Using default font (watermark may not display correctly)")
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Format timestamp (Thailand time +7)
        from datetime import timedelta
        thai_time_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) + timedelta(hours=7)
        thai_time = thai_time_dt.strftime("%d/%m/%Y %H:%M:%S")
        
        # Prepare watermark text
        watermark_lines = []
        
        # Employee info (if available)
        if employee_data:
            emp_code = employee_data.get('empCode', 'N/A')
            emp_name = f"{employee_data.get('firstName', '')} {employee_data.get('lastName', '')}".strip()
            watermark_lines.append(f"� {emp_code} - {emp_name}")
        
        # Time and GPS
        watermark_lines.append(f"🕐 {thai_time}")
        watermark_lines.append(f"📍 {latitude:.6f}, {longitude:.6f}")
        
        # Address in English (remove Thai characters)
        import re
        # Keep only English characters, numbers, and common symbols
        address_en = re.sub(r'[^\x00-\x7F]+', '', address)
        if address_en.strip():
            watermark_lines.append(f"📌 {address_en[:40]}")
        
        # Position watermark at bottom
        width, height = img.size
        line_height = 30
        padding = 15
        y_position = height - (len(watermark_lines) * line_height + padding * 2)
        
        # Draw watermark with improved style
        for i, line in enumerate(watermark_lines):
            y = y_position + padding + (i * line_height)
            
            # Get text bounding box
            bbox = draw.textbbox((padding, y), line, font=small_font)
            
            # Draw rounded rectangle background (simulate with multiple rectangles)
            bg_padding = 8
            draw.rectangle(
                [bbox[0] - bg_padding, bbox[1] - bg_padding, 
                 bbox[2] + bg_padding, bbox[3] + bg_padding],
                fill=(0, 0, 0, 200)  # Semi-transparent black
            )
            
            # Draw text with shadow effect
            # Shadow
            draw.text((padding + 1, y + 1), line, fill=(0, 0, 0), font=small_font)
            # Main text in white
            draw.text((padding, y), line, fill=(255, 255, 255), font=small_font)
        
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
    print(f"\n{'='*60}")
    print(f"📤 Attempting to send LINE message...")
    print(f"   User ID: {user_id}")
    print(f"   Messages count: {len(messages)}")
    print(f"   Token available: {bool(LINE_CHANNEL_ACCESS_TOKEN)}")
    
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("❌ LINE_CHANNEL_ACCESS_TOKEN is None or empty!")
        print("   Check if .env file exists and contains LINE_CHANNEL_ACCESS_TOKEN")
        return False
    
    if not user_id:
        print("❌ User ID is missing!")
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
        print(f"   Sending to LINE API...")
        response = requests.post(LINE_API_URL, headers=headers, json=data)
        
        print(f"   Response Status: {response.status_code}")
        print(f"   Response Body: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Message sent successfully to {user_id}")
            print(f"{'='*60}\n")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"   Error: {response.text}")
            print(f"{'='*60}\n")
            return False
    except Exception as e:
        print(f"❌ Error sending LINE message: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
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
                shift = data.get('shift', '')  # Get shift from request
                checkin_type = data.get('checkinType', 'in')  # Get checkin type (in/out)
                
                # Get current time in Thai format (UTC+7)
                from datetime import timedelta
                thai_time_dt = datetime.now() + timedelta(hours=7)
                thai_time = thai_time_dt.strftime("%d/%m/%Y %H:%M:%S")
                date_only = thai_time_dt.strftime("%Y-%m-%d")
                
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
                    
                    # Try to verify with HR system if employeeCode was provided in request
                    employee_code_from_request = data.get('employeeCode')
                    hr_data = None
                    hr_verified = False
                    
                    if employee_code_from_request and ENABLE_HR_VERIFICATION:
                        print(f"🔍 Unregistered user provided employeeCode: {employee_code_from_request}")
                        hr_data = verify_employee_code_with_hr_system(employee_code_from_request)
                        hr_verified = hr_data is not None
                    
                    checkin_record.update({
                        "employeeCode": employee_code_from_request,
                        "employeeName": display_name,
                        "department": None,
                        "position": None,
                        "status": "unregistered",
                        "hrSystemVerified": hr_verified,
                        "hrSystemData": hr_data
                    })
                    
                    success_message = f"⚠️ เช็คอินสำเร็จ แต่ยังไม่ได้ลงทะเบียนพนักงาน!\n\n"
                    success_message += f"👤 ชื่อ: {display_name}\n"
                    
                    # Show HR verification status if employeeCode was provided
                    if employee_code_from_request:
                        success_message += f"🆔 รหัสพนักงาน: {employee_code_from_request}\n"
                        if hr_verified:
                            success_message += f"✅ ยืนยันจากระบบ HR: สำเร็จ\n"
                        else:
                            success_message += f"⚠️ ยืนยันจากระบบ HR: ไม่สำเร็จ\n"
                    
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
                    
                    # Verify employee code with HR system
                    hr_data = verify_employee_code_with_hr_system(employee_code)
                    hr_verified = hr_data is not None
                    
                    checkin_record.update({
                        "employeeCode": employee_code,
                        "employeeName": employee_name,
                        "department": department,
                        "position": position,
                        "status": "registered",
                        "hrSystemVerified": hr_verified,
                        "hrSystemData": hr_data
                    })
                    
                    # Create success message
                    success_message = f"✅ เช็คอินสำเร็จ!\n\n"
                    success_message += f"👤 ชื่อ: {employee_name}\n"
                    success_message += f"🆔 รหัสพนักงาน: {employee_code}\n"
                    success_message += f"🏢 แผนก: {department}\n"
                    success_message += f"💼 ตำแหน่ง: {position}\n"
                    
                    # Add HR verification status and details
                    if hr_verified and hr_data:
                        success_message += f"\n✅ ยืนยันจากระบบ HR: สำเร็จ\n"
                        success_message += f"━━━━━━━━━━━━━━━━━━━━\n"
                        success_message += f"📋 ข้อมูลจากระบบ HR:\n"
                        
                        # ข้อมูลส่วนตัว
                        if hr_data.get('prefix') or hr_data.get('name') or hr_data.get('lastName'):
                            hr_name = f"{hr_data.get('prefix', '')} {hr_data.get('name', '')} {hr_data.get('lastName', '')}".strip()
                            success_message += f"  ชื่อ-นามสกุล: {hr_name}\n"
                        if hr_data.get('nickName'):
                            success_message += f"  ชื่อเล่น: {hr_data.get('nickName')}\n"
                        if hr_data.get('position'):
                            success_message += f"  ตำแหน่ง: {hr_data.get('position')}\n"
                        if hr_data.get('department'):
                            success_message += f"  แผนก: {hr_data.get('department')}\n"
                        if hr_data.get('workplace'):
                            success_message += f"  สถานที่ทำงาน: {hr_data.get('workplace')}\n"
                        if hr_data.get('jobtype'):
                            success_message += f"  ประเภทงาน: {hr_data.get('jobtype')}\n"
                        
                        # วันที่เริ่มงาน
                        if hr_data.get('startjob'):
                            success_message += f"  วันเริ่มงาน: {hr_data.get('startjob')}\n"
                        
                        # เงินเดือน
                        if hr_data.get('salary'):
                            success_message += f"  เงินเดือน: {hr_data.get('salary')} บาท\n"
                        
                        # ข้อมูลติดต่อ
                        if hr_data.get('phoneNumber'):
                            success_message += f"  เบอร์โทร: {hr_data.get('phoneNumber')}\n"
                        if hr_data.get('idLine'):
                            success_message += f"  LINE ID: {hr_data.get('idLine')}\n"
                        
                        success_message += f"━━━━━━━━━━━━━━━━━━━━\n"
                    else:
                        success_message += f"\n⚠️ ยืนยันจากระบบ HR: ไม่สำเร็จ\n"
                    
                    success_message += f"\n📍 สถานที่: {address}\n"
                    success_message += f"🕐 เวลา: {thai_time}\n"
                    success_message += f"📷 รูปถ่าย: {'✅ มี' if has_photo else '❌ ไม่มี'}\n"
                    success_message += f"🎯 GPS: {latitude:.6f}, {longitude:.6f}\n"
                    success_message += f"📡 ความแม่นยำ: {accuracy:.0f} เมตร\n"
                    success_message += f"💾 บันทึกข้อมูล: ✅ สำเร็จ"
                    
                    # Create time record in HR system (only for registered employees)
                    if employee:
                        dept_code = employee.get('deptCode', '')
                        employee_record_id = create_time_record(
                            employee_code, employee_name, dept_code, department, 
                            timestamp, shift, checkin_type, user_id
                        )
                        
                        # If check-in and got record ID, save it to MongoDB for later check-out
                        if checkin_type == "in" and employee_record_id and registrations_collection:
                            try:
                                # Parse datetime for date
                                from datetime import datetime as dt
                                check_dt = dt.fromisoformat(timestamp.replace('Z', '+00:00'))
                                date_str = f"{check_dt.year}-{check_dt.month}-{check_dt.day}"
                                start_time = f"{check_dt.hour:02d}.{check_dt.minute:02d}"
                                
                                registrations_collection.update_one(
                                    {"lineUserId": user_id},
                                    {"$set": {
                                        "todayCheckin": {
                                            "date": date_str,
                                            "employeeRecordId": employee_record_id,
                                            "startTime": start_time,
                                            "shift": shift
                                        }
                                    }}
                                )
                                print(f"💾 Saved check-in info to MongoDB for check-out")
                            except Exception as e:
                                print(f"⚠️ Could not save check-in info: {e}")
                
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
        
        print(f"\n🗄️ Database:")
        if registrations_collection is not None:
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
        
        print(f"\n🔧 HR System Integration:")
        print(f"   Enabled: {'✅ Yes' if ENABLE_HR_VERIFICATION else '❌ No (disabled)'}")
        if ENABLE_HR_VERIFICATION:
            print(f"   API URL: {HR_API_URL}")
            print(f"   Timeout: {HR_API_TIMEOUT}s")
        else:
            print(f"   ℹ️ Set ENABLE_HR_VERIFICATION=true in .env to enable")
        
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
