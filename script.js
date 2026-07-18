// ============================================================
// SCRIPT.JS - DATABASE & LOGIC CHUNG
// ============================================================

const MASTER_PASSWORD = 'master123';
const ADMIN_PASSWORD = 'admin123';

// ============================================================
// DATABASE
// ============================================================
function initDB() {
    if (!localStorage.getItem('config_db')) {
        const defaultData = {
            admins: [
                {
                    username: 'admin1',
                    password: ADMIN_PASSWORD,
                    displayName: 'Quản Trị Viên 1',
                    zalo: '0879072010',
                    createdAt: new Date().toISOString(),
                    isActive: true,
                    keyQuota: 50,
                    keysUsed: 0
                }
            ],
            keys: [],
            usageLogs: [],
            blockedIPs: [],
            blockedUDIDs: []
        };
        localStorage.setItem('config_db', JSON.stringify(defaultData));
    }
    return JSON.parse(localStorage.getItem('config_db'));
}

function saveDB(data) {
    localStorage.setItem('config_db', JSON.stringify(data));
}

function loadDB() {
    return JSON.parse(localStorage.getItem('config_db'));
}

// ============================================================
// HÀM TẠO KEY
// ============================================================
function createKey(packageName, expiresDays, maxDevices, features, customDns, adminUsername) {
    const data = loadDB();
    const admin = data.admins.find(a => a.username === adminUsername);
    if (!admin) return { success: false, error: 'Admin không tồn tại!' };
    if (admin.keysUsed >= admin.keyQuota) {
        return { success: false, error: 'Bạn đã hết quota tạo key!' };
    }

    const prefix = packageName.toUpperCase().substring(0, 3);
    const hash = Math.random().toString(36).substring(2, 10).toUpperCase();
    const keyCode = prefix + '-' + Date.now().toString().substring(0, 8) + '-' + hash + '-' + String(Math.floor(Math.random() * 900) + 100);

    const newKey = {
        keyCode: keyCode,
        package: packageName,
        createdBy: adminUsername,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + expiresDays * 24 * 60 * 60 * 1000).toISOString(),
        maxDevices: maxDevices || 1,
        usedDevices: [],
        features: features || {},
        adminInfo: {
            name: admin.displayName,
            zalo: admin.zalo
        },
        isActive: true
    };

    if (customDns && customDns.length > 0 && features.dns) {
        newKey.features.customDns = customDns;
    }

    data.keys.push(newKey);
    admin.keysUsed++;
    saveDB(data);
    return { success: true, key: newKey };
}

function findKey(keyCode) {
    const data = loadDB();
    return data.keys.find(k => k.keyCode === keyCode);
}

function validateKey(keyCode) {
    const data = loadDB();
    const key = data.keys.find(k => k.keyCode === keyCode);
    if (!key) return { valid: false, error: '❌ Key không tồn tại!' };
    if (!key.isActive) return { valid: false, error: '❌ Key đã bị khóa!' };
    if (new Date(key.expiresAt) < new Date()) return { valid: false, error: '❌ Key đã hết hạn!' };
    if (key.usedDevices.length >= key.maxDevices) {
        return { valid: false, error: '❌ Key đã hết số lượng thiết bị!' };
    }
    return { valid: true, key: key };
}

function useKey(keyCode, udid, ip) {
    const data = loadDB();
    const key = data.keys.find(k => k.keyCode === keyCode);
    if (!key) return { success: false, error: 'Key không tồn tại!' };
    if (key.usedDevices.find(d => d.udid === udid)) {
        return { success: false, error: 'UDID này đã được đăng ký!' };
    }
    if (key.usedDevices.length >= key.maxDevices) {
        return { success: false, error: 'Key đã hết số lượng thiết bị!' };
    }

    key.usedDevices.push({
        udid: udid,
        ip: ip || '0.0.0.0',
        usedAt: new Date().toISOString()
    });
    saveDB(data);
    return { success: true };
}

function deleteKey(keyCode) {
    const data = loadDB();
    const keyIndex = data.keys.findIndex(k => k.keyCode === keyCode);
    if (keyIndex > -1) {
        const key = data.keys[keyIndex];
        const admin = data.admins.find(a => a.username === key.createdBy);
        if (admin) admin.keysUsed--;
        data.keys.splice(keyIndex, 1);
        saveDB(data);
        return true;
    }
    return false;
}

function createAdmin(username, password, displayName, zalo, keyQuota) {
    const data = loadDB();
    if (data.admins.find(a => a.username === username)) {
        return { success: false, error: 'Tên đăng nhập đã tồn tại!' };
    }
    const newAdmin = {
        username: username,
        password: password,
        displayName: displayName || username,
        zalo: zalo || '0879072010',
        createdAt: new Date().toISOString(),
        isActive: true,
        keyQuota: keyQuota || 50,
        keysUsed: 0
    };
    data.admins.push(newAdmin);
    saveDB(data);
    return { success: true, admin: newAdmin };
}

function deleteAdmin(username) {
    const data = loadDB();
    data.admins = data.admins.filter(a => a.username !== username);
    saveDB(data);
}

function updateAdminQuota(username, newQuota) {
    const data = loadDB();
    const admin = data.admins.find(a => a.username === username);
    if (admin) {
        admin.keyQuota = newQuota;
        saveDB(data);
        return true;
    }
    return false;
}

// ============================================================
// 🚀 HÀM TẠO FILE .MOBILECONFIG - TỰ ĐỘNG GHÉP CODE
// ============================================================
function generateMobileConfig(keyData, udid) {
    const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });

    // ===== PHẦN ĐẦU FILE =====
    let xml = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>Configuration Centre 🧩</string>
    <key>PayloadDescription</key>
    <string>DUCLAM.NET - ${keyData.adminInfo.name} | Zalo: ${keyData.adminInfo.zalo}</string>
    <key>PayloadIdentifier</key>
    <string>com.duclam.config.${udid}</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>${uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadExpiration</key>
    <date>${new Date(keyData.expiresAt).toISOString().replace('Z', '')}Z</date>
    <key>PayloadContent</key>
    <array>`;

    // ============================================================
    // 1️⃣ TỐI ƯU PIN (Battery Optimize)
    // ============================================================
    if (keyData.features.batteryOptimize) {
        xml += `
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
    </dict>`;
    }

    // ============================================================
    // 2️⃣ TỐI ƯU MÁY (Performance)
    // ============================================================
    if (keyData.features.performance) {
        xml += `
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
    </dict>
    <dict>
        <key>PayloadType</key>
        <string>com.apple.performance</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.performance</string>
        <key>PayloadDisplayName</key>
        <string>Tối ưu hiệu năng</string>
        <key>HighPerformance</key>
        <true/>
    </dict>`;
    }

    // ============================================================
    // 3️⃣ GIẢM LAG (DNS nhanh + chặn QC)
    // ============================================================
    if (keyData.features.reduceLag) {
        const dnsList = keyData.features.customDns || ['1.1.1.1', '8.8.8.8', '9.9.9.9'];
        xml += `
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
            <array>`;
        dnsList.forEach(d => {
            xml += `
                <string>${d.trim()}</string>`;
        });
        xml += `
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
    </dict>`;
    }

    // ============================================================
    // 4️⃣ CHỐNG GIẬT (Wi-Fi 5GHz + Low Latency)
    // ============================================================
    if (keyData.features.antiLag) {
        xml += `
    <dict>
        <key>PayloadType</key>
        <string>com.apple.wifi.managed</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.wifi</string>
        <key>PayloadDisplayName</key>
        <string>Wi-Fi 5GHz ưu tiên</string>
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
        <string>Độ trễ thấp</string>
        <key>LowLatency</key>
        <true/>
    </dict>`;
    }

    // ============================================================
    // 5️⃣ TĂNG TỐC MẠNG (Proxy)
    // ============================================================
    if (keyData.features.proxy) {
        xml += `
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
    </dict>`;
    }

    // ============================================================
    // 6️⃣ DNS CƠ BẢN (Nếu bật DNS mà không có reduceLag)
    // ============================================================
    if (keyData.features.dns && !keyData.features.reduceLag) {
        const dnsList = keyData.features.customDns || ['1.1.1.1', '8.8.8.8'];
        xml += `
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
            <array>`;
        dnsList.forEach(d => {
            xml += `
                <string>${d.trim()}</string>`;
        });
        xml += `
            </array>
        </dict>
    </dict>`;
    }

    // ============================================================
    // 7️⃣ CHỨNG CHỈ (Certificate)
    // ============================================================
    if (keyData.features.certificate) {
        const cert = localStorage.getItem('duclam_cert') || `MIIDXTCCAkGgAwIBAgIJAK...`;
        xml += `
    <dict>
        <key>PayloadType</key>
        <string>com.apple.security.pkcs1</string>
        <key>PayloadIdentifier</key>
        <string>com.duclam.cert</string>
        <key>PayloadDisplayName</key>
        <string>Chứng chỉ DUCLAM</string>
        <key>PayloadContent</key>
        <string>
${cert}
        </string>
    </dict>`;
    }

    // ============================================================
    // 8️⃣ THÔNG TIN USER (Custom)
    // ============================================================
    xml += `
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
            <string>${udid}</string>
            <key>Key</key>
            <string>${keyData.keyCode}</string>
            <key>Admin</key>
            <string>${keyData.adminInfo.name}</string>
            <key>Zalo</key>
            <string>${keyData.adminInfo.zalo}</string>
            <key>Expires</key>
            <string>${new Date(keyData.expiresAt).toLocaleDateString('vi-VN')}</string>
        </dict>
    </dict>`;

    // ===== KẾT THÚC FILE =====
    xml += `
</array>
</dict>
</plist>`;

    return xml;
}

// ============================================================
// KHỞI TẠO
// ============================================================
initDB();
