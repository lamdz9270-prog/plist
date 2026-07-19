from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import urllib.parse
import os
import time
import random
import string
from datetime import datetime, timedelta
import uuid
import cgi
import shutil

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
    if admin
