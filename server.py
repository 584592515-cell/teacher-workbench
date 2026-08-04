#!/usr/bin/env python3
"""
班主任工作台 - 后端服务
Flask + Socket.IO 实现数据同步
"""

import os
import sys
import json
import socket
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# ============ Config ============
PORT = 5566
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workbench_data.json')
AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workbench_auth.json')

DEFAULT_USER = 'chenqi'
DEFAULT_PASS = '638893'

# ============ Default Data ============
def default_data():
    return {
        "classInfo": {
            "className": "七年级(1)班", "grade": "七年级", "classNum": "1",
            "headTeacher": "", "totalStudents": 45, "maleCount": 23, "femaleCount": 22
        },
        "classSchedule": {
            "periods": ["早读", "第一节", "第二节", "第三节", "第四节", "午休", "第五节", "第六节", "第七节", "第八节"],
            "periodTimes": ["7:30-8:00", "8:10-8:55", "9:05-9:50", "10:10-10:55", "11:05-11:50", "12:00-13:50", "14:00-14:45", "14:55-15:40", "15:50-16:35", "16:45-17:30"],
            "monday": ["语文", "数学", "英语", "历史", "体育", "", "物理", "化学", "自习", "自习"],
            "tuesday": ["英语", "语文", "数学", "政治", "生物", "", "体育", "音乐", "美术", "自习"],
            "wednesday": ["数学", "英语", "语文", "物理", "化学", "", "历史", "地理", "自习", "自习"],
            "thursday": ["语文", "物理", "数学", "英语", "化学", "", "生物", "体育", "政治", "自习"],
            "friday": ["英语", "数学", "语文", "历史", "地理", "", "音乐", "美术", "班会", "自习"]
        },
        "students": [],
        "seating": {"rows": 6, "cols": 8, "seats": {}},
        "attendance": {},
        "grades": {"exams": []},
        "classMeetings": [],
        "parentCommunications": [],
        "behaviorRecords": [],
        "classFees": {"balance": 0, "records": [], "invoices": []},
        "workPlan": {},
        "personalSchedule": {
            "periods": ["早读", "第一节", "第二节", "第三节", "第四节", "午休", "第五节", "第六节", "第七节", "第八节"],
            "periodTimes": ["7:30-8:00", "8:10-8:55", "9:05-9:50", "10:10-10:55", "11:05-11:50", "12:00-13:50", "14:00-14:45", "14:55-15:40", "15:50-16:35", "16:45-17:30"],
            "monday": ["", "", "", "", "", "", "", "", "", ""],
            "tuesday": ["", "", "", "", "", "", "", "", "", ""],
            "wednesday": ["", "", "", "", "", "", "", "", "", ""],
            "thursday": ["", "", "", "", "", "", "", "", "", ""],
            "friday": ["", "", "", "", "", "", "", "", ""]
        },
        "teachingClasses": [],
        "notifications": []
    }

# ============ Deep Merge ============
def deep_merge(target, source):
    """Recursively merge source into target, preserving all data."""
    result = {}
    # Start with target keys
    for key in target:
        result[key] = target[key]
    # Merge source keys
    for key in source:
        if key in result:
            tv = result[key]
            sv = source[key]
            # Both are dicts -> recurse
            if isinstance(tv, dict) and isinstance(sv, dict):
                result[key] = deep_merge(tv, sv)
            # Both are lists
            elif isinstance(tv, list) and isinstance(sv, list):
                # If items are dicts (records), concat unique items by JSON compare
                if sv and isinstance(sv[0], dict):
                    merged = list(tv)
                    for sv_item in sv:
                        exists = False
                        for mv_item in merged:
                            if isinstance(sv_item, dict) and isinstance(mv_item, dict):
                                if sv_item == mv_item:
                                    exists = True
                                    break
                        if not exists:
                            merged.append(sv_item)
                    result[key] = merged
                else:
                    # For simple lists (strings, numbers) — replace with source
                    result[key] = sv
            else:
                # Source wins for primitives and mixed types
                result[key] = sv
        else:
            result[key] = source[key]
    return result

# ============ Storage ============
app_data = None

def load_data():
    global app_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            # Deep merge with defaults to handle any missing fields
            app_data = deep_merge(default_data(), loaded)
        else:
            app_data = default_data()
            save_data()
    except Exception as e:
        print(f"Error loading data: {e}")
        app_data = default_data()

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def load_auth():
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    default = {"username": DEFAULT_USER, "password": DEFAULT_PASS}
    save_auth(default)
    return default

def save_auth(auth):
    try:
        with open(AUTH_FILE, 'w', encoding='utf-8') as f:
            json.dump(auth, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving auth: {e}")

# ============ Flask App ============
app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = 'teacher-workbench-secret-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ============ Auth Routes ============
@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.get_json()
    auth = load_auth()
    if data.get('username') == auth['username'] and data.get('password') == auth['password']:
        return jsonify({"success": True, "token": "logged-in"})
    return jsonify({"success": False, "error": "用户名或密码错误"}), 401

@app.route('/api/auth/update', methods=['POST'])
def api_auth_update():
    data = request.get_json()
    auth = load_auth()
    cur_pass = data.get('currentPassword', '')
    if cur_pass != auth['password']:
        return jsonify({"success": False, "error": "当前密码错误"}), 400
    new_user = data.get('newUsername', '').strip()
    new_pass = data.get('newPassword', '').strip()
    if new_user:
        auth['username'] = new_user
    if new_pass:
        auth['password'] = new_pass
    save_auth(auth)
    return jsonify({"success": True})

@app.route('/api/auth/reset', methods=['POST'])
def api_auth_reset():
    auth = {"username": DEFAULT_USER, "password": DEFAULT_PASS}
    save_auth(auth)
    return jsonify({"success": True})

# ============ Data Routes ============
@app.route('/api/data', methods=['GET'])
def api_get_data():
    return jsonify(app_data)

@app.route('/api/data', methods=['POST'])
def api_save_data():
    """Client explicitly saved — treat incoming data as authoritative, replace server data."""
    global app_data
    new_data = request.get_json()
    if new_data:
        # Client's save is authoritative — replace server data directly
        app_data = new_data
        app_data['_lastModified'] = datetime.now().isoformat()
        save_data()
        # Notify all OTHER clients to pull latest
        socketio.emit('data_changed', {
            'field': 'full',
            'timestamp': app_data['_lastModified']
        }, include_self=False)
    return jsonify({"success": True})

@app.route('/api/data/field/<field>', methods=['PUT'])
def api_update_field(field):
    """Update a specific field in app_data"""
    global app_data
    data = request.get_json()
    if field in app_data or True:  # Allow setting any field
        app_data[field] = data.get('value', data)
        app_data['_lastModified'] = datetime.now().isoformat()
        save_data()
        socketio.emit('data_changed', {
            'field': field,
            'timestamp': app_data['_lastModified']
        }, include_self=False)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Field not found"}), 404

# ============ Serve Static ============
@app.route('/sw.js')
def serve_sw():
    resp = send_from_directory('.', 'sw.js', mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route('/')
def index():
    return send_from_directory('.', 'teacher-workbench.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), path)):
        return send_from_directory('.', path)
    return send_from_directory('.', 'teacher-workbench.html')

# ============ Socket.IO ============
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'status': 'ok'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('request_sync')
def handle_request_sync():
    """Client requests full data sync"""
    emit('full_sync', app_data)

@socketio.on('update_field')
def handle_update_field(data):
    """Real-time field update from client - deep merge for nested objects"""
    global app_data
    field = data.get('field')
    value = data.get('value')
    if field is not None:
        # If both existing and new value are dicts, deep merge
        if field in app_data and isinstance(app_data[field], dict) and isinstance(value, dict):
            app_data[field] = deep_merge(app_data[field], value)
        else:
            app_data[field] = value
        now = datetime.now().isoformat()
        app_data['_lastModified'] = now
        save_data()
        # Broadcast to all other clients
        socketio.emit('field_updated', {
            'field': field,
            'value': value,
            'timestamp': now
        }, include_self=False)

# ============ Get Local IP ============
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

# ============ Main ============
if __name__ == '__main__':
    load_data()
    local_ip = get_local_ip()
    print("=" * 50)
    print("  班主任工作台 - 服务器已启动")
    print("=" * 50)
    print(f"  电脑端访问: http://localhost:{PORT}")
    print(f"  手机端访问: http://{local_ip}:{PORT}")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)
