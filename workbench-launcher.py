# -*- coding: utf-8 -*-
"""班主任工作台 - Windows 桌面启动器（带后端服务）"""
import os
import sys
import json
import socket
import threading
import time
from datetime import datetime
import webview

# When frozen (running as .exe), PyInstaller extracts data files to sys._MEIPASS (read-only)
# Data files must be stored in a writable location
if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
    USER_DATA_DIR = os.path.join(os.path.expanduser('~'), '.teacher-workbench')
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    USER_DATA_DIR = APP_DIR

# Ensure data directory exists
os.makedirs(USER_DATA_DIR, exist_ok=True)

PORT = 5566
HTML_PATH = os.path.join(APP_DIR, 'teacher-workbench.html')
DATA_FILE = os.path.join(USER_DATA_DIR, 'workbench_data.json')
AUTH_FILE = os.path.join(USER_DATA_DIR, 'workbench_auth.json')

DEFAULT_USER = 'chenqi'
DEFAULT_PASS = '638893'


def deep_merge(target, source):
    """Recursively merge source into target, preserving all data."""
    result = {}
    for key in target:
        result[key] = target[key]
    for key in source:
        if key in result:
            tv = result[key]
            sv = source[key]
            if isinstance(tv, dict) and isinstance(sv, dict):
                result[key] = deep_merge(tv, sv)
            elif isinstance(tv, list) and isinstance(sv, list):
                # If items are dicts (records), merge by ID or by text
                if sv and isinstance(sv[0], dict):
                    # ID-based merge if items have 'id' field
                    if 'id' in sv[0] and sv[0]['id'] is not None:
                        merged = list(sv)  # start with source items
                        tv_ids = {item.get('id') for item in merged if isinstance(item, dict) and item.get('id')}
                        for tv_item in tv:
                            if isinstance(tv_item, dict) and tv_item.get('id') and tv_item['id'] not in tv_ids:
                                merged.append(tv_item)
                        result[key] = merged
                    elif 'text' in sv[0]:
                        # Text-based merge for workPlan-style items
                        merged = list(sv)
                        sv_texts = {item.get('text', '') for item in merged if isinstance(item, dict)}
                        for tv_item in tv:
                            if isinstance(tv_item, dict) and tv_item.get('text', '') not in sv_texts:
                                merged.append(tv_item)
                        result[key] = merged
                    else:
                        # Full comparison fallback
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
                    # Simple lists (strings, numbers) — source is authoritative
                    result[key] = sv
            else:
                result[key] = sv
        else:
            result[key] = source[key]
    return result


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
            "friday": ["", "", "", "", "", "", "", "", "", ""]
        },
        "teachingClasses": [],
        "notifications": []
    }


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'


def run_server():
    """Run the Flask server in a thread."""
    try:
        from flask import Flask, request, jsonify, send_from_directory
        from flask_cors import CORS
        from flask_socketio import SocketIO

        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'teacher-workbench-secret-2024'
        CORS(app)
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

        # Load persisted data
        app_data = None

        def load_data():
            nonlocal app_data
            try:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                    app_data = deep_merge(default_data(), loaded)
                else:
                    app_data = default_data()
                    save_data_file()
            except:
                app_data = default_data()
                save_data_file()

        def save_data_file():
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
            return {"username": DEFAULT_USER, "password": DEFAULT_PASS}

        def save_auth_file(auth):
            try:
                with open(AUTH_FILE, 'w', encoding='utf-8') as f:
                    json.dump(auth, f, ensure_ascii=False, indent=2)
            except:
                pass

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
            save_auth_file(auth)
            return jsonify({"success": True})

        @app.route('/api/auth/reset', methods=['POST'])
        def api_auth_reset():
            auth = {"username": DEFAULT_USER, "password": DEFAULT_PASS}
            save_auth_file(auth)
            return jsonify({"success": True})

        @app.route('/api/data', methods=['GET'])
        def api_get_data():
            return jsonify(app_data)

        @app.route('/api/data', methods=['POST'])
        def api_save_data():
            """Client explicitly saved — treat incoming data as authoritative, replace server data."""
            nonlocal app_data
            new_data = request.get_json()
            if new_data:
                # Client's save is authoritative — replace server data directly
                app_data = new_data
                app_data['_lastModified'] = datetime.now().isoformat()
                save_data_file()
                socketio.emit('data_changed', {
                    'field': 'full',
                    'timestamp': app_data['_lastModified']
                }, include_self=False)
            return jsonify({"success": True})

        @app.route('/sw.js')
        def serve_sw():
            resp = send_from_directory(APP_DIR, 'sw.js', mimetype='application/javascript')
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            resp.headers['Service-Worker-Allowed'] = '/'
            return resp

        @app.route('/')
        def index():
            return send_from_directory(APP_DIR, 'teacher-workbench.html')

        @app.route('/<path:path>')
        def serve_static(path):
            filepath = os.path.join(APP_DIR, path)
            if os.path.exists(filepath):
                return send_from_directory(APP_DIR, path)
            return send_from_directory(APP_DIR, 'teacher-workbench.html')

        @app.route('/health')
        def health():
            return jsonify({"ok": True, "status": "running"})

        @socketio.on('connect')
        def handle_connect():
            print(f"Client connected: {request.sid}")

        @socketio.on('request_sync')
        def handle_request_sync():
            socketio.emit('full_sync', app_data)

        @socketio.on('update_field')
        def handle_update_field(data):
            nonlocal app_data
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
                save_data_file()
                socketio.emit('field_updated', {
                    'field': field, 'value': value
                }, include_self=False)

        load_data()
        local_ip = get_local_ip()
        print("=" * 50)
        print("  班主任工作台 - 服务器已启动")
        print(f"  电脑端访问: http://localhost:{PORT}")
        print(f"  手机端访问: http://{local_ip}:{PORT}")
        print("=" * 50)
        socketio.run(app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)

    except Exception as e:
        print(f"Server error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # ---- Start Node.js cloud server (port 5000) for data sync ----
    cloud_port = 5000
    cloud_server_process = None
    cloud_server_dir = os.path.join(APP_DIR, 'cloud-server')
    node_candidates = [
        os.path.join(os.path.dirname(sys.executable), 'node.exe'),
        os.path.join(os.path.expanduser('~'), '.workbuddy', 'binaries', 'node', 'versions', '22.22.2', 'node.exe'),
        'node',
    ]
    
    for node_path in node_candidates:
        server_js = os.path.join(cloud_server_dir, 'server.js')
        if os.path.exists(server_js):
            try:
                import subprocess as sp
                cloud_server_process = sp.Popen(
                    [node_path, server_js],
                    cwd=cloud_server_dir,
                    stdout=sp.DEVNULL, stderr=sp.DEVNULL,
                    creationflags=sp.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                print(f"Cloud server starting on port {cloud_port} (node: {node_path})")
                break
            except Exception as e:
                print(f"Failed to start cloud server with {node_path}: {e}")
                cloud_server_process = None
    
    # ---- Start Flask server (port 5566) for webview ----
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for servers to be ready
    print("Waiting for servers to start...")
    import urllib.request
    url = f'http://localhost:{PORT}'
    cloud_url = f'http://localhost:{cloud_port}'
    max_retries = 30
    server_ready = False
    cloud_ready = False
    for i in range(max_retries):
        try:
            time.sleep(0.5)
            if not server_ready:
                resp = urllib.request.urlopen(f'{url}/health', timeout=1)
                if resp.getcode() == 200:
                    server_ready = True
                    print(f"  Flask server ready: {url}")
            if not cloud_ready and cloud_server_process:
                resp = urllib.request.urlopen(f'{cloud_url}/api/health', timeout=1)
                if resp.getcode() == 200:
                    cloud_ready = True
                    print(f"  Cloud server ready: {cloud_url}")
            if server_ready and (cloud_ready or not cloud_server_process):
                break
        except:
            pass
        if i % 5 == 4:
            print(f"  Waiting... ({i+1}/{max_retries})")

    if not server_ready:
        print("WARNING: Flask server did not start in time, attempting to open anyway...")
    if cloud_server_process and not cloud_ready:
        print("WARNING: Cloud server not available, data sync will use local Flask")

    local_ip = get_local_ip()
    print(f"Opening webview at {url}")
    print(f"Phone access: http://{local_ip}:{PORT}")

    window = webview.create_window(
        title='班主任工作台',
        url=url,
        width=1280,
        height=860,
        min_size=(1024, 680),
        resizable=True,
        text_select=True,
        easy_drag=False,
    )

    webview.start()
    
    # Cleanup: stop cloud server when app closes
    if cloud_server_process:
        try:
            cloud_server_process.terminate()
            cloud_server_process.wait(timeout=5)
            print("Cloud server stopped")
        except:
            try:
                cloud_server_process.kill()
            except:
                pass
