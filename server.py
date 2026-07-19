from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import urllib.parse
import os
import time
import random
import string
from datetime import datetime, timedelta
import uuid
import shutil
import email
from io import BytesIO

# ============================================================
# THÔNG TIN MASTER
# ============================================================
MASTER_USERNAME = "nguyenduclam"
MASTER_PASSWORD = "ngduclamcute1201"

# ============================================================
# CẤU HÌNH UPLOAD
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# DATABASE
# ============================================================
DB = {
    "admins": [],
    "keys": [],
    "usageLogs": []
}

# ============================================================
# HÀM TẠO KEY 8 KÝ TỰ
# ============================================================
def generate_key():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))

# ============================================================
# HÀM XỬ LÝ ADMIN
# ============================================================
def find_admin(username):
    for a in DB["admins"]:
        if a["username"] == username:
            return a
    return None

def admin_login_check(username, password, ip):
    admin = find_admin(username)
    if not admin:
        return {"success": False, "error": "Admin not found!"}
    if admin["password"] != password:
        return {"success": False, "error": "Invalid password!"}
    if not admin.get("isActive", True):
        return {"success": False, "error": "Account is locked!"}
    
    registered_ip = admin.get("registered_ip")
    if registered_ip and registered_ip != ip:
        return {
            "success": False, 
            "error": f"IP not allowed! This account is locked to IP: {registered_ip}"
        }
    
    if not registered_ip:
        admin["registered_ip"] = ip
        for i, a in enumerate(DB["admins"]):
            if a["username"] == username:
                DB["admins"][i]["registered_ip"] = ip
                break
    
    admin["last_login"] = datetime.now().isoformat()
    return {"success": True, "admin": admin}

# ============================================================
# HÀM XỬ LÝ MULTIPART FORM DATA (KHÔNG DÙNG CGI)
# ============================================================
def parse_multipart(content_type, body):
    """Parse multipart/form-data manually"""
    if not content_type or not body:
        return None
    
    boundary = content_type.split("boundary=")[-1].strip()
    if not boundary:
        return None
    
    parts = body.split(("--" + boundary).encode())
    result = None
    
    for part in parts:
        if not part.strip() or b"filename=" not in part:
            continue
        
        # Tìm filename
        lines = part.split(b"\r\n")
        filename = None
        file_data = None
        in_headers = True
        data_lines = []
        
        for line in lines:
            if in_headers:
                if line.startswith(b"Content-Disposition:") and b"filename=" in line:
                    filename = line.split(b"filename=")[-1].strip(b'"').decode()
                if not line.strip():
                    in_headers = False
                continue
            else:
                if line.strip():
                    data_lines.append(line)
        
        if filename and data_lines:
            file_data = b"\r\n".join(data_lines)
            result = {"filename": filename, "data": file_data}
            break
    
    return result

# ============================================================
# HÀM XỬ LÝ KEY
# ============================================================
def create_key(admin_username, custom_config, bonus_file=""):
    admin = find_admin(admin_username)
    if not admin:
        return {"success": False, "error": "Admin not found!"}
    if admin["keysUsed"] >= admin["keyQuota"]:
        return {"success": False, "error": "Key quota exceeded!"}
    
    key_code = generate_key()
    
    filename = custom_config.get("filename", "Config.mobileconfig")
    if not filename.endswith(".mobileconfig"):
        filename = "Config.mobileconfig"
    
    payload_display_name = custom_config.get("payloadDisplayName", "Configplist OptiSystem⚡️")
    if not payload_display_name:
        payload_display_name = "Configplist OptiSystem⚡️"
    
    payload_description = custom_config.get("payloadDescription", "DUCLAM.NET")
    if not payload_description:
        payload_description = "DUCLAM.NET"
    
    payload_identifier = custom_config.get("payloadIdentifier", "com.duclam.config")
    if not payload_identifier:
        payload_identifier = "com.duclam.config"
    
    payload_content = custom_config.get("payloadContent", "")
    if not payload_content:
        payload_content = '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.dnsProxy.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.dns</string>
        <key>PayloadDisplayName</key>
        <string>DNS DUCLAM</string>
        <key>DNSSettings</key>
        <dict>
            <key>DNSAddresses</key>
            <array>
                <string>1.1.1.1</string>
                <string>8.8.8.8</string>
            </array>
        </dict>
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.generic.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.info</string>
        <key>PayloadDisplayName</key>
        <string>License Info</string>
        <key>PayloadContent</key>
        <dict>
            <key>Key</key>
            <string>{KEY}</string>
            <key>UDID</key>
            <string>{UDID}</string>
            <key>Admin</key>
            <string>{ADMIN}</string>
            <key>Zalo</key>
            <string>{ZALO}</string>
        </dict>
    </dict>
'''
    
    expires_days = custom_config.get("expiresDays", 365)
    max_devices = custom_config.get("maxDevices", 1)
    
    new_key = {
        "keyCode": key_code,
        "createdBy": admin_username,
        "createdAt": datetime.now().isoformat(),
        "expiresAt": (datetime.now() + timedelta(days=expires_days)).isoformat(),
        "maxDevices": max_devices,
        "usedDevices": [],
        "adminInfo": {"name": admin["displayName"], "zalo": admin["zalo"]},
        "isActive": True,
        "isUsed": False,
        "bonusFile": bonus_file,
        "customConfig": {
            "filename": filename,
            "payloadDisplayName": payload_display_name,
            "payloadDescription": payload_description,
            "payloadIdentifier": payload_identifier,
            "payloadContent": payload_content
        }
    }
    
    DB["keys"].append(new_key)
    admin["keysUsed"] += 1
    return {"success": True, "key": new_key}

def validate_key(key_code):
    key = None
    for k in DB["keys"]:
        if k["keyCode"] == key_code:
            key = k
            break
    
    if not key:
        return {"valid": False, "error": "Key not found!"}
    if not key["isActive"]:
        return {"valid": False, "error": "Key is locked!"}
    if datetime.fromisoformat(key["expiresAt"]) < datetime.now():
        return {"valid": False, "error": "Key expired!"}
    if key.get("isUsed", False):
        return {"valid": False, "error": "Key already used!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"valid": False, "error": "Key reached max devices!"}
    return {"valid": True, "key": key}

def use_key(key_code, udid, ip):
    key = None
    for k in DB["keys"]:
        if k["keyCode"] == key_code:
            key = k
            break
    
    if not key:
        return {"success": False, "error": "Key not found!"}
    if key.get("isUsed", False):
        return {"success": False, "error": "Key already used by another device!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"success": False, "error": "Key reached max devices!"}
    
    for d in key["usedDevices"]:
        if d["udid"] == udid:
            return {"success": False, "error": "UDID already registered!"}
    
    key["usedDevices"].append({
        "udid": udid,
        "ip": ip or "0.0.0.0",
        "usedAt": datetime.now().isoformat()
    })
    
    if key["maxDevices"] <= 1:
        key["isUsed"] = True
    
    return {"success": True}

def delete_key(key_code, admin_username):
    key = None
    for k in DB["keys"]:
        if k["keyCode"] == key_code:
            key = k
            break
    
    if not key:
        return {"success": False, "error": "Key not found!"}
    if key["createdBy"] != admin_username:
        return {"success": False, "error": "You can only delete your own keys!"}
    
    if key.get("bonusFile"):
        try:
            os.remove(os.path.join(UPLOAD_DIR, key["bonusFile"]))
        except:
            pass
    
    DB["keys"] = [k for k in DB["keys"] if k["keyCode"] != key_code]
    admin = find_admin(admin_username)
    if admin:
        admin["keysUsed"] = max(0, admin["keysUsed"] - 1)
    return {"success": True}

# ============================================================
# HÀM TẠO FILE .MOBILECONFIG
# ============================================================
def generate_mobile_config(key_data, udid):
    config = key_data.get("customConfig", {})
    
    display_name = config.get("payloadDisplayName", "Configplist OptiSystem⚡️")
    description = config.get("payloadDescription", "DUCLAM.NET")
    identifier = config.get("payloadIdentifier", "com.duclam.config")
    custom_content = config.get("payloadContent", "")
    
    custom_content = custom_content.replace("{KEY}", key_data["keyCode"])
    custom_content = custom_content.replace("{UDID}", udid)
    custom_content = custom_content.replace("{ADMIN}", key_data["adminInfo"]["name"])
    custom_content = custom_content.replace("{ZALO}", key_data["adminInfo"]["zalo"])
    custom_content = custom_content.replace("{DATE}", datetime.now().strftime("%Y-%m-%d"))
    
    uuid_str = str(uuid.uuid4())
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>{display_name}</string>
    <key>PayloadDescription</key>
    <string>{description}</string>
    <key>PayloadIdentifier</key>
    <string>{identifier}.{udid}</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{uuid_str}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadContent</key>
    <array>
        {custom_content}
    </array>
</dict>
</plist>'''
    return xml

# ============================================================
# HTTP REQUEST HANDLER
# ============================================================
class MyHandler(SimpleHTTPRequestHandler):
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == "/api/validate":
            key = query.get("key", [""])[0]
            result = validate_key(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        if path == "/api/keys":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            admin = find_admin(username)
            if not admin:
                self.send_response(403)
                self.end_headers()
                return
            keys = [k for k in DB["keys"] if k["createdBy"] == username]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "keys": keys,
                "quota": admin["keyQuota"],
                "used": admin["keysUsed"]
            }).encode())
            return
        
        if path == "/api/master-admins":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            if username != MASTER_USERNAME:
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"admins": DB["admins"]}).encode())
            return
        
        if path == "/" or path == "":
            path = "/index.html"
        
        if path.endswith(".py") or path.endswith(".json"):
            self.send_response(403)
            self.end_headers()
            return
        
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # 🔥 XỬ LÝ UPLOAD FILE (KHÔNG DÙNG CGI)
        if path == "/api/upload-bonus":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_response(400)
                self.end_headers()
                return
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            
            result = parse_multipart(content_type, body)
            if not result:
                self.send_response(400)
                self.end_headers()
                return
            
            filename = result["filename"]
            file_data = result["data"]
            
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "filename": filename
            }).encode())
            return
        
        # Download bonus file
        if path.startswith("/api/download-bonus/"):
            filename = path.replace("/api/download-bonus/", "")
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            if not os.path.exists(file_path):
                self.send_response(404)
                self.end_headers()
                return
            
            with open(file_path, "rb") as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
            self.end_headers()
            self.wfile.write(content)
            return
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # Admin Login
        if path == "/api/admin-login":
            username = data.get("username", "")
            password = data.get("password", "")
            ip = self.client_address[0]
            
            result = admin_login_check(username, password, ip)
            if result["success"]:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "username": username,
                    "ip": ip
                }).encode())
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": result["error"]
                }).encode())
            return
        
        # Master Login
        if path == "/api/master-login":
            username = data.get("username", "")
            password = data.get("password", "")
            if username == MASTER_USERNAME and password == MASTER_PASSWORD:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Invalid credentials!"}).encode())
            return
        
        # Create Key
        if path == "/api/create-key":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            admin = find_admin(username)
            if not admin or not admin.get("isActive", True):
                self.send_response(403)
                self.end_headers()
                return
            
            custom_config = {
                "filename": data.get("filename", "Config.mobileconfig"),
                "payloadDisplayName": data.get("payloadDisplayName", "Configplist OptiSystem⚡️"),
                "payloadDescription": data.get("payloadDescription", "DUCLAM.NET"),
                "payloadIdentifier": data.get("payloadIdentifier", "com.duclam.config"),
                "payloadContent": data.get("payloadContent", ""),
                "expiresDays": data.get("expiresDays", 365),
                "maxDevices": data.get("maxDevices", 1)
            }
            
            bonus_file = data.get("bonusFile", "")
            
            result = create_key(username, custom_config, bonus_file)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # Delete Key
        if path == "/api/delete-key":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            
            result = delete_key(data.get("keyCode", ""), username)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # Use Key
        if path == "/api/use-key":
            result = use_key(
                data.get("keyCode", ""),
                data.get("udid", ""),
                self.client_address[0]
            )
            if result["success"]:
                key_data = None
                for k in DB["keys"]:
                    if k["keyCode"] == data.get("keyCode"):
                        key_data = k
                        break
                if key_data:
                    xml = generate_mobile_config(key_data, data.get("udid", ""))
                    filename = key_data.get("customConfig", {}).get("filename", "Config.mobileconfig")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-apple-aspen-config")
                    self.send_header("Content-Disposition", f"attachment; filename={filename}")
                    self.end_headers()
                    self.wfile.write(xml.encode())
                    return
            
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # Master Create Admin
        if path == "/api/master-create-admin":
            master_user = data.get("master_username", "")
            master_pass = data.get("master_password", "")
            if master_user != MASTER_USERNAME or master_pass != MASTER_PASSWORD:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Unauthorized!"}).encode())
                return
            
            username = data.get("username", "").strip()
            if not username:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Username is required!"}).encode())
                return
            
            if find_admin(username):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Username already exists!"}).encode())
                return
            
            new_admin = {
                "username": username,
                "password": data.get("password", "Admin@123"),
                "displayName": data.get("displayName", username),
                "zalo": data.get("zalo", "0879072010"),
                "createdAt": datetime.now().isoformat(),
                "isActive": True,
                "keyQuota": int(data.get("keyQuota", 50)),
                "keysUsed": 0,
                "registered_ip": None
            }
            DB["admins"].append(new_admin)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "admin": new_admin
            }).encode())
            return
        
        # Master Delete Admin
        if path == "/api/master-delete-admin":
            master_user = data.get("master_username", "")
            master_pass = data.get("master_password", "")
            if master_user != MASTER_USERNAME or master_pass != MASTER_PASSWORD:
                self.send_response(401)
                self.end_headers()
                return
            
            username = data.get("username", "")
            DB["admins"] = [a for a in DB["admins"] if a["username"] != username]
            DB["keys"] = [k for k in DB["keys"] if k["createdBy"] != username]
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return
        
        # Master Update Quota
        if path == "/api/master-update-quota":
            master_user = data.get("master_username", "")
            master_pass = data.get("master_password", "")
            if master_user != MASTER_USERNAME or master_pass != MASTER_PASSWORD:
                self.send_response(401)
                self.end_headers()
                return
            
            username = data.get("username", "")
            new_quota = int(data.get("newQuota", 50))
            
            for admin in DB["admins"]:
                if admin["username"] == username:
                    admin["keyQuota"] = new_quota
                    break
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return
        
        self.send_response(404)
        self.end_headers()

# ============================================================
# CHẠY SERVER
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), MyHandler)
    print(f"Server running at http://0.0.0.0:{port}")
    print(f"Master: {MASTER_USERNAME}")
    print("✅ Key format: 8 characters (e.g. A1B2C3D4)")
    print("✅ Each key can only be used once (locked after first use)")
    server.serve_forever()
