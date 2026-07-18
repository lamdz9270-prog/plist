from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import urllib.parse
import os
import time
import re
from datetime import datetime, timedelta

# ============================================================
# DATABASE (Lưu trong memory, mất khi restart)
# ============================================================
DB = {
    "admins": [
        {
            "username": "admin1",
            "password": "admin123",
            "displayName": "Quản Trị Viên 1",
            "zalo": "0879072010",
            "createdAt": datetime.now().isoformat(),
            "isActive": True,
            "keyQuota": 50,
            "keysUsed": 0
        }
    ],
    "keys": [],
    "usageLogs": []
}

MASTER_PASSWORD = "master123"
ADMIN_PASSWORD = "admin123"

# ============================================================
# HÀM XỬ LÝ KEY
# ============================================================
def create_key(package, expires_days, max_devices, features, custom_dns, admin_username):
    admin = next((a for a in DB["admins"] if a["username"] == admin_username), None)
    if not admin:
        return {"success": False, "error": "Admin không tồn tại!"}
    if admin["keysUsed"] >= admin["keyQuota"]:
        return {"success": False, "error": "Hết quota tạo key!"}
    
    prefix = package.upper()[:3]
    hash_code = hex(int(time.time() * 1000))[2:8].upper()
    key_code = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{hash_code}-{str(int(time.time()) % 900 + 100)}"
    
    new_key = {
        "keyCode": key_code,
        "package": package,
        "createdBy": admin_username,
        "createdAt": datetime.now().isoformat(),
        "expiresAt": (datetime.now() + timedelta(days=expires_days)).isoformat(),
        "maxDevices": max_devices,
        "usedDevices": [],
        "features": features,
        "adminInfo": {"name": admin["displayName"], "zalo": admin["zalo"]},
        "isActive": True
    }
    
    if custom_dns and features.get("reduceLag"):
        new_key["features"]["customDns"] = custom_dns
    
    DB["keys"].append(new_key)
    admin["keysUsed"] += 1
    return {"success": True, "key": new_key}

def validate_key(key_code):
    key = next((k for k in DB["keys"] if k["keyCode"] == key_code), None)
    if not key:
        return {"valid": False, "error": "Key không tồn tại!"}
    if not key["isActive"]:
        return {"valid": False, "error": "Key đã bị khóa!"}
    if datetime.fromisoformat(key["expiresAt"]) < datetime.now():
        return {"valid": False, "error": "Key đã hết hạn!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"valid": False, "error": "Key đã hết số lượng thiết bị!"}
    return {"valid": True, "key": key}

def use_key(key_code, udid, ip):
    key = next((k for k in DB["keys"] if k["keyCode"] == key_code), None)
    if not key:
        return {"success": False, "error": "Key không tồn tại!"}
    if any(d["udid"] == udid for d in key["usedDevices"]):
        return {"success": False, "error": "UDID này đã được đăng ký!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"success": False, "error": "Key đã hết số lượng thiết bị!"}
    
    key["usedDevices"].append({
        "udid": udid,
        "ip": ip or "0.0.0.0",
        "usedAt": datetime.now().isoformat()
    })
    return {"success": True}

# ============================================================
# HÀM TẠO FILE .MOBILECONFIG
# ============================================================
def generate_mobile_config(key_data, udid):
    import uuid
    uuid_str = str(uuid.uuid4())
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>Configuration Centre 🧩</string>
    <key>PayloadDescription</key>
    <string>DUCLAM.NET - {key_data["adminInfo"]["name"]} | Zalo: {key_data["adminInfo"]["zalo"]}</string>
    <key>PayloadIdentifier</key>
    <string>com.duclam.config.{udid}</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{uuid_str}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadExpiration</key>
    <date>{key_data["expiresAt"].replace('Z', '')}Z</date>
    <key>PayloadContent</key>
    <array>'''
    
    # 1. Tối ưu pin
    if key_data["features"].get("batteryOptimize"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.appmanaged</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.battery</string>
        <key>PayloadDisplayName</key>
        <string>Tối ưu pin</string>
        <key>PayloadContent</key>
        <dict>
            <key>BackgroundAppRefresh</key>
            <false/>
        </dict>
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.accessibility</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.reduce</string>
        <key>PayloadDisplayName</key>
        <string>Giảm hiệu ứng</string>
        <key>ReduceMotion</key>
        <true/>
    </dict>'''
    
    # 2. Tối ưu máy
    if key_data["features"].get("performance"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.SoftwareUpdate</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.update</string>
        <key>PayloadDisplayName</key>
        <string>Tắt tự động cập nhật</string>
        <key>AutomaticDownload</key>
        <false/>
        <key>AutomaticAppInstallation</key>
        <false/>
    </dict>'''
    
    # 3. Giảm lag (DNS)
    if key_data["features"].get("reduceLag"):
        dns_list = key_data["features"].get("customDns", ["1.1.1.1", "8.8.8.8"])
        xml += f'''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.dnsProxy.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.dns</string>
        <key>PayloadDisplayName</key>
        <string>DNS nhanh</string>
        <key>DNSSettings</key>
        <dict>
            <key>DNSAddresses</key>
            <array>'''
        for d in dns_list:
            xml += f'''
                <string>{d.strip()}</string>'''
        xml += '''
            </array>
        </dict>
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.webcontent-filter</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.adblock</string>
        <key>PayloadDisplayName</key>
        <string>Chặn quảng cáo</string>
        <key>FilterWhitelist</key>
        <array>
            <string>*.garena.com</string>
            <string>*.freefire.com</string>
        </array>
    </dict>'''
    
    # 4. Proxy
    if key_data["features"].get("proxy"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.webcontent-filter</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.proxy</string>
        <key>PayloadDisplayName</key>
        <string>Proxy DUCLAM</string>
        <key>HTTPProxy</key>
        <dict>
            <key>HTTPProxy</key>
            <string>proxy.duclam.net:8080</string>
            <key>HTTPSProxy</key>
            <string>proxy.duclam.net:8080</string>
        </dict>
    </dict>'''
    
    # 5. Thông tin user
    xml += f'''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.generic.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.info</string>
        <key>PayloadDisplayName</key>
        <string>Thông tin VIP</string>
        <key>PayloadContent</key>
        <dict>
            <key>UDID</key>
            <string>{udid}</string>
            <key>Key</key>
            <string>{key_data["keyCode"]}</string>
            <key>Admin</key>
            <string>{key_data["adminInfo"]["name"]}</string>
            <key>Zalo</key>
            <string>{key_data["adminInfo"]["zalo"]}</string>
            <key>Expires</key>
            <string>{key_data["expiresAt"].split('T')[0]}</string>
        </dict>
    </dict>'''
    
    xml += '''
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
        
        # API: Validate key
        if path == "/api/validate":
            key = query.get("key", [""])[0]
            result = validate_key(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # API: Get key list (admin)
        if path == "/api/keys":
            # Check auth via header
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            admin = next((a for a in DB["admins"] if a["username"] == username), None)
            if not admin:
                self.send_response(403)
                self.end_headers()
                return
            keys = [k for k in DB["keys"] if k["createdBy"] == username]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"keys": keys, "quota": admin["keyQuota"], "used": admin["keysUsed"]}).encode())
            return
        
        # Serve static files
        if path == "/" or path == "":
            path = "/index.html"
        elif path == "/admin":
            path = "/admin.html"
        elif path == "/master":
            path = "/master.html"
        
        # Security: block access to sensitive files
        if path.endswith(".py") or path.endswith(".json"):
            self.send_response(403)
            self.end_headers()
            return
        
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # API: Create key (admin)
        if path == "/api/create-key":
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                return
            username = auth.replace("Bearer ", "")
            admin = next((a for a in DB["admins"] if a["username"] == username), None)
            if not admin or not admin["isActive"]:
                self.send_response(403)
                self.end_headers()
                return
            
            result = create_key(
                data.get("package", "vip"),
                data.get("expiresDays", 365),
                data.get("maxDevices", 1),
                data.get("features", {}),
                data.get("customDns", []),
                username
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # API: Use key (user download)
        if path == "/api/use-key":
            result = use_key(
                data.get("keyCode", ""),
                data.get("udid", ""),
                self.client_address[0]
            )
            if result["success"]:
                key_data = next((k for k in DB["keys"] if k["keyCode"] == data.get("keyCode")), None)
                if key_data:
                    xml = generate_mobile_config(key_data, data.get("udid", ""))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-apple-aspen-config")
                    self.send_header("Content-Disposition", f"attachment; filename=Config_{data.get('udid', '')[:8]}.mobileconfig")
                    self.end_headers()
                    self.wfile.write(xml.encode())
                    return
            
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # API: Admin login
        if path == "/api/admin-login":
            username = data.get("username", "")
            password = data.get("password", "")
            admin = next((a for a in DB["admins"] if a["username"] == username and a["password"] == password), None)
            if admin and admin["isActive"]:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "username": username}).encode())
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Sai thông tin đăng nhập!"}).encode())
            return
        
        # API: Master login
        if path == "/api/master-login":
            password = data.get("password", "")
            if password == MASTER_PASSWORD:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Sai mật khẩu master!"}).encode())
            return
        
        self.send_response(404)
        self.end_headers()

# ============================================================
# CHẠY SERVER
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), MyHandler)
    print(f"🚀 Server chạy tại http://0.0.0.0:{port}")
    server.serve_forever()
