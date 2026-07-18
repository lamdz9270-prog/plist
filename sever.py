from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import urllib.parse
import os
import time
import re
from datetime import datetime, timedelta
import uuid

# ============================================================
# 🔒 THÔNG TIN MASTER (CỦA BẠN)
# ============================================================
MASTER_USERNAME = "nguyenduclam"
MASTER_PASSWORD = "ngduclamcute1201"

# ============================================================
# DATABASE
# ============================================================
DB = {
    "admins": [
        {
            "username": "admin_vip",
            "password": "Admin@2026",
            "displayName": "Admin VIP",
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

# ============================================================
# HÀM XỬ LÝ KEY
# ============================================================
def create_key(package, expires_days, max_devices, features, custom_dns, admin_username):
    admin = next((a for a in DB["admins"] if a["username"] == admin_username), None)
    if not admin:
        return {"success": False, "error": "Admin not found!"}
    if admin["keysUsed"] >= admin["keyQuota"]:
        return {"success": False, "error": "Key quota exceeded!"}
    
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
    
    if custom_dns and features.get("reduce_lag"):
        new_key["features"]["customDns"] = custom_dns
    
    DB["keys"].append(new_key)
    admin["keysUsed"] += 1
    return {"success": True, "key": new_key}

def validate_key(key_code):
    key = next((k for k in DB["keys"] if k["keyCode"] == key_code), None)
    if not key:
        return {"valid": False, "error": "Key not found!"}
    if not key["isActive"]:
        return {"valid": False, "error": "Key is locked!"}
    if datetime.fromisoformat(key["expiresAt"]) < datetime.now():
        return {"valid": False, "error": "Key expired!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"valid": False, "error": "Key reached max devices!"}
    return {"valid": True, "key": key}

def use_key(key_code, udid, ip):
    key = next((k for k in DB["keys"] if k["keyCode"] == key_code), None)
    if not key:
        return {"success": False, "error": "Key not found!"}
    if any(d["udid"] == udid for d in key["usedDevices"]):
        return {"success": False, "error": "UDID already registered!"}
    if len(key["usedDevices"]) >= key["maxDevices"]:
        return {"success": False, "error": "Key reached max devices!"}
    
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
    uuid_str = str(uuid.uuid4())
    features = key_data.get("features", {})
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>Configplist OptiSystem⚡️</string>
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

    # 1️⃣ PIN (Battery Optimize)
    if features.get("battery"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.appmanaged</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.battery</string>
        <key>PayloadDisplayName</key>
        <string>🔋 Battery Optimize</string>
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
        <string>🎨 Reduce Motion</string>
        <key>ReduceMotion</key>
        <true/>
    </dict>'''

    # 2️⃣ FPS Boost (Performance)
    if features.get("fps_boost"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.SoftwareUpdate</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.update</string>
        <key>PayloadDisplayName</key>
        <string>⚡ FPS Boost</string>
        <key>AutomaticDownload</key>
        <false/>
        <key>AutomaticAppInstallation</key>
        <false/>
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.performance</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.performance</string>
        <key>PayloadDisplayName</key>
        <string>🚀 Performance Mode</string>
        <key>HighPerformance</key>
        <true/>
    </dict>'''

    # 3️⃣ Reduce Lag (DNS)
    if features.get("reduce_lag"):
        dns_list = features.get("customDns", ["1.1.1.1", "8.8.8.8", "9.9.9.9"])
        xml += f'''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.dnsProxy.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.dns</string>
        <key>PayloadDisplayName</key>
        <string>🌐 DNS Optimizer</string>
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
    </dict>'''

    # 4️⃣ Ad Block
    if features.get("ad_block"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.webcontent-filter</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.adblock</string>
        <key>PayloadDisplayName</key>
        <string>🚫 Ad Blocker</string>
        <key>FilterWhitelist</key>
        <array>
            <string>*.garena.com</string>
            <string>*.freefire.com</string>
        </array>
    </dict>'''

    # 5️⃣ Network Optimize
    if features.get("network_optimize"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.wifi.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.wifi</string>
        <key>PayloadDisplayName</key>
        <string>📶 Wi-Fi 5GHz</string>
        <key>PreferredNetworks</key>
        <array>
            <dict>
                <key>SSID_STR</key>
                <string>DUCLAM_WIFI</string>
                <key>PreferredBand</key>
                <integer>5</integer>
            </dict>
        </array>
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.network</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.network</string>
        <key>PayloadDisplayName</key>
        <string>⚡ Low Latency</string>
        <key>LowLatency</key>
        <true/>
    </dict>'''

    # 6️⃣ RAM Clean
    if features.get("ram_clean"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.generic.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.ram</string>
        <key>PayloadDisplayName</key>
        <string>🧹 RAM Optimizer</string>
        <key>PayloadContent</key>
        <dict>
            <key>Note</key>
            <string>RAM optimization applied system-wide</string>
        </dict>
    </dict>'''

    # 7️⃣ Cache Clean
    if features.get("cache_clean"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.generic.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.cache</string>
        <key>PayloadDisplayName</key>
        <string>🗑️ Cache Cleaner</string>
        <key>PayloadContent</key>
        <dict>
            <key>Note</key>
            <string>Cache cleaned on app launch</string>
        </dict>
    </dict>'''

    # 8️⃣ Head Track (AimLock)
    if features.get("head_track"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.duclam.aimlock</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.aimlock</string>
        <key>PayloadDisplayName</key>
        <string>🎯 Head Track</string>
        <key>PayloadContent</key>
        <string><![CDATA[
<AimLockConfig>
    <Header>
        <StartMarker>--AIMLOCK-SESSION-START--</StartMarker>
        <Version>1.1.0</Version>
        <TimestampFormat>ISO8601</TimestampFormat>
        <Author>Operator</Author>
    </Header>
    <AimLock>
        <Enable>true</Enable>
        <LockZone>center</LockZone>
        <LockStrength value="0.95"/>
        <Smooth value="0.50"/>
        <MaxCorrection value="0.12"/>
        <MinSmooth value="0.20"/>
        <SnapThreshold value="0.03"/>
        <TargetPredict enabled="true" horizonMs="80"/>
        <AutoRelease enabled="true" conditions="targetLost|timeout|manualOverride" timeoutMs="1200"/>
        <Priority>high</Priority>
        <StabilityBoost value="0.90"/>
    </AimLock>
    <Logging>
        <LogLevel>verbose</LogLevel>
        <LogFormat>json</LogFormat>
        <IncludeTimestamps>true</IncludeTimestamps>
        <RecordStartStopEvents>true</RecordStartStopEvents>
        <StartEventTag>AIMLOCK_START</StartEventTag>
        <EndEventTag>AIMLOCK_END</EndEventTag>
        <Heartbeat intervalMs="500"/>
    </Logging>
    <Footer>
        <EndMarker>--AIMLOCK-SESSION-END--</EndMarker>
        <Checksum enabled="true" algorithm="SHA256"/>
        <Summary enabled="true" maxLines="8"/>
    </Footer>
</AimLockConfig>
        ]]></string>
    </dict>'''

    # 9️⃣ Fix Recoil
    if features.get("fix_recoil"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.duclam.recoil</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.recoil</string>
        <key>PayloadDisplayName</key>
        <string>🔫 Fix Recoil</string>
        <key>PayloadContent</key>
        <string><![CDATA[
<RecoilConfig>
    <Enable>true</Enable>
    <Horizontal value="0.15"/>
    <Vertical value="0.20"/>
    <Smoothness value="0.85"/>
</RecoilConfig>
        ]]></string>
    </dict>'''

    # 🔟 Light Scope
    if features.get("light_scope"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.duclam.lightscope</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.lightscope</string>
        <key>PayloadDisplayName</key>
        <string>⚖️ Light Scope</string>
        <key>PayloadContent</key>
        <string><![CDATA[
<LightScopeConfig>
    <Enable>true</Enable>
    <Sensitivity value="0.85"/>
    <AimAssist value="0.70"/>
</LightScopeConfig>
        ]]></string>
    </dict>'''

    # 1️⃣1️⃣ Body Track
    if features.get("body_track"):
        xml += '''
    <dict>
        <key>PayloadType</key>
        <string>com.duclam.bodytrack</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.bodytrack</string>
        <key>PayloadDisplayName</key>
        <string>🎯 Body Track</string>
        <key>PayloadContent</key>
        <string><![CDATA[
<CenterCutSim>
    <Header>
        <StartMarker>--CENTERCUT-SIM-START--</StartMarker>
        <Version>sim-0.1</Version>
        <TimestampFormat>ISO8601</TimestampFormat>
        <Author>Analyst</Author>
    </Header>
    <Meta>
        <Enable>true</Enable>
        <CutRatio value="0.6"/>
        <StabilityBoost enabled="true"/>
    </Meta>
    <Logging>
        <LogLevel>verbose</LogLevel>
        <LogFormat>json</LogFormat>
        <RecordEvents>true</RecordEvents>
        <StartEventTag>CENTERCUT_SIM_START</StartEventTag>
        <EndEventTag>CENTERCUT_SIM_END</EndEventTag>
        <Heartbeat intervalMs="1000"/>
    </Logging>
    <Footer>
        <EndMarker>--CENTERCUT-SIM-END--</EndMarker>
        <Checksum enabled="true" algorithm="SHA256"/>
        <Summary enabled="true" maxLines="8"/>
    </Footer>
</CenterCutSim>
        ]]></string>
    </dict>'''

    # 1️⃣2️⃣ User Info
    xml += f'''
    <dict>
        <key>PayloadType</key>
        <string>com.apple.generic.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.info</string>
        <key>PayloadDisplayName</key>
        <string>ℹ️ License Info</string>
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
    
    # File cần bảo vệ (tên khó đoán)
    PROTECTED_FILES = [
        'z9x8c7v6b5n4.html',  # admin.html
        'm3k2j1h0g9f8.html',  # master.html
        'admin.js',
        'master.js'
    ]
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        # ===== BẢO VỆ FILE ADMIN =====
        for protected in self.PROTECTED_FILES:
            if path.endswith(protected):
                self.send_response(403)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <head><title>403 Forbidden</title></head>
                <body style="text-align:center;font-family:sans-serif;padding:50px;background:#0a0a12;color:#e0e0e0;">
                    <h1>🚫 403 Forbidden</h1>
                    <p>Access denied. Please use the main interface.</p>
                    <p><a href="/" style="color:#7b61ff;text-decoration:none;">← Back to home</a></p>
                </body>
                </html>
                """)
                return
        
        # ===== API VALIDATE KEY =====
        if path == "/api/validate":
            key = query.get("key", [""])[0]
            result = validate_key(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # ===== API GET KEYS (ADMIN) =====
        if path == "/api/keys":
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
            self.wfile.write(json.dumps({
                "keys": keys,
                "quota": admin["keyQuota"],
                "used": admin["keysUsed"]
            }).encode())
            return
        
        # ===== PHỤC VỤ FILE THƯỜNG =====
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
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        # ===== API CREATE KEY =====
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
        
        # ===== API USE KEY =====
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
                    self.send_header("Content-Disposition", f"attachment; filename=Configplist OptiSystem⚡️.mobileconfig")
                    self.end_headers()
                    self.wfile.write(xml.encode())
                    return
            
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return
        
        # ===== API ADMIN LOGIN =====
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
                self.wfile.write(json.dumps({"success": False, "error": "Invalid credentials!"}).encode())
            return
        
        # ===== API MASTER LOGIN =====
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
        
        # ===== API MASTER GET ADMINS =====
        if path == "/api/master-admins":
            username = data.get("username", "")
            password = data.get("password", "")
            if username == MASTER_USERNAME and password == MASTER_PASSWORD:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"admins": DB["admins"]}).encode())
            else:
                self.send_response(401)
                self.end_headers()
            return
        
        # ===== API MASTER CREATE ADMIN =====
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
            
            if any(a["username"] == username for a in DB["admins"]):
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
                "keysUsed": 0
            }
            DB["admins"].append(new_admin)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "admin": new_admin,
                "message": f"✅ Admin {username} created successfully!"
            }).encode())
            return
        
        # ===== API MASTER DELETE ADMIN =====
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
        
        # ===== API MASTER UPDATE QUOTA =====
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
    print(f"🚀 Server running at http://0.0.0.0:{port}")
    print(f"👑 Master: {MASTER_USERNAME}")
    print(f"🔒 Admin: admin_vip / Admin@2026")
    server.serve_forever()
