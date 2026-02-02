from flask import Flask, render_template, jsonify, request, Response, send_file
import os, sys, subprocess, time, threading, queue, re, json, signal, psutil, base64, io
from datetime import datetime

app = Flask(__name__)

# قائمة لتخزين المخرجات
output_buffer = []
output_lock = threading.Lock()
MAX_BUFFER_SIZE = 1000

# تخزين عمليات scrcpy
scrcpy_processes = {}

# === INDEX.HTML ===

@app.route("/")
def select():
    return render_template("selector.html")

@app.route("/v3")
def index():
    return render_template("index_v3.html")

@app.route("/v2")
def index_v2():
    return render_template("index.html")

# === APIs ===

@app.route("/api/send_command", methods=["POST"])
def send_command():
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({"error": "No command provided"}), 400
        
        command = data['command']
        
        if not command.strip().startswith("adb"):
            return jsonify({"error": "Only ADB commands are allowed"}), 400
        
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            with output_lock:
                output_buffer.append(f"[{timestamp}] $ {command}")
                if len(output_buffer) > MAX_BUFFER_SIZE:
                    output_buffer.pop(0)
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output_lines = []
            
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        with output_lock:
                            output_buffer.append(f"[{timestamp}] {line}")
                            if len(output_buffer) > MAX_BUFFER_SIZE:
                                output_buffer.pop(0)
                        output_lines.append(line)
            
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        with output_lock:
                            output_buffer.append(f"[{timestamp}] ERROR: {line}")
                            if len(output_buffer) > MAX_BUFFER_SIZE:
                                output_buffer.pop(0)
                        output_lines.append(f"ERROR: {line}")
            
            return jsonify({
                "success": True,
                "output": output_lines,
                "return_code": result.returncode
            })
            
        except subprocess.TimeoutExpired:
            with output_lock:
                output_buffer.append(f"[{timestamp}] ERROR: Command timed out after 30 seconds")
                if len(output_buffer) > MAX_BUFFER_SIZE:
                    output_buffer.pop(0)
            
            return jsonify({
                "success": False,
                "error": "Command timed out after 30 seconds"
            }), 408
            
        except Exception as e:
            with output_lock:
                output_buffer.append(f"[{timestamp}] ERROR: {str(e)}")
                if len(output_buffer) > MAX_BUFFER_SIZE:
                    output_buffer.pop(0)
            
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/output", methods=["GET"])
def output():
    try:
        with output_lock:
            recent_output = output_buffer[-100:] if len(output_buffer) > 100 else output_buffer
            return jsonify({
                "success": True,
                "output": recent_output,
                "total_lines": len(output_buffer)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clear_output", methods=["POST"])
def clear_output():
    try:
        with output_lock:
            output_buffer.clear()
        return jsonify({"success": True, "message": "Output cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/devices", methods=["GET"])
def get_devices():
    try:
        result = subprocess.run(
            "adb devices",
            shell=True,
            capture_output=True,
            text=True
        )
        
        devices = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines[1:]:
            if line.strip() and 'device' in line:
                device_id = line.split('\t')[0]
                devices.append(device_id)
        
        return jsonify({
            "success": True,
            "devices": devices,
            "total": len(devices)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/device_info", methods=["GET"])
def get_device_info():
    try:
        device_id = request.args.get('device')
        
        if not device_id:
            devices_result = subprocess.run(
                "adb devices -l",
                shell=True,
                capture_output=True,
                text=True
            )
            
            lines = devices_result.stdout.strip().split('\n')
            if len(lines) < 2:
                return jsonify({"error": "No devices connected"}), 404
            
            device_id = lines[1].split('\t')[0]
        
        info = {}
        commands = {
            "model": f"adb -s {device_id} shell getprop ro.product.model",
            "android_version": f"adb -s {device_id} shell getprop ro.build.version.release",
            "brand": f"adb -s {device_id} shell getprop ro.product.brand",
            "manufacturer": f"adb -s {device_id} shell getprop ro.product.manufacturer",
            "device": f"adb -s {device_id} shell getprop ro.product.device",
            "serial": f"adb -s {device_id} get-serialno",
            "battery": f"adb -s {device_id} shell dumpsys battery",
            "cpu": f"adb -s {device_id} shell getprop ro.hardware",
            "ram": f"adb -s {device_id} shell cat /proc/meminfo",
            "storage": f"adb -s {device_id} shell df /data",
        }
        
        for key, cmd in commands.items():
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if key == "battery":
                    # معالجة خاصة لبيانات البطارية
                    lines = result.stdout.split('\n')
                    battery_info = {}
                    for line in lines:
                        if 'level:' in line:
                            battery_info['level'] = line.split(':')[1].strip() + '%'
                        elif 'temperature:' in line:
                            temp_value = int(line.split(':')[1].strip()) // 10
                            battery_info['temp'] = f"{temp_value}°C"
                        elif 'health:' in line:
                            battery_info['health'] = line.split(':')[1].strip()
                        elif 'status:' in line:
                            battery_info['status'] = line.split(':')[1].strip()
                    info[key] = battery_info if battery_info else {"level": "N/A", "temp": "N/A", "status": "N/A"}
                elif key == "ram":
                    # معالجة الذاكرة
                    lines = result.stdout.split('\n')
                    ram_info = {}
                    for line in lines:
                        if line.startswith('MemTotal:'):
                            total_kb = int(line.split()[1])
                            ram_info['total'] = f"{total_kb // 1024} MB"
                        elif line.startswith('MemAvailable:'):
                            available_kb = int(line.split()[1])
                            ram_info['available'] = f"{available_kb // 1024} MB"
                    info[key] = ram_info if ram_info else {"total": "N/A", "available": "N/A"}
                elif key == "storage":
                    # معالجة التخزين
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 4:
                            total = int(parts[1]) // 1024
                            used = int(parts[2]) // 1024
                            available = int(parts[3]) // 1024
                            info[key] = {
                                "total": f"{total} MB",
                                "used": f"{used} MB",
                                "available": f"{available} MB"
                            }
                        else:
                            info[key] = {"total": "N/A", "used": "N/A", "available": "N/A"}
                    else:
                        info[key] = {"total": "N/A", "used": "N/A", "available": "N/A"}
                else:
                    info[key] = result.stdout.strip()
            except:
                info[key] = "Unknown"
                info[key] = "Unknown"
        
        return jsonify({
            "success": True,
            "device_id": device_id,
            "info": info
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Scrcpy APIs ===

@app.route("/api/scrcpy/start", methods=["POST"])
def start_scrcpy():
    try:
        data = request.get_json()
        device_id = data.get('device')
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        # إيقاف أي عملية scrcpy سابقة لنفس الجهاز
        if device_id in scrcpy_processes:
            try:
                scrcpy_processes[device_id].terminate()
                time.sleep(1)
            except:
                pass
        
        # بدء scrcpy
        cmd = f'scrcpy -s {device_id} --stay-awake --show-touches'
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            scrcpy_processes[device_id] = {
                'process': process,
                'start_time': time.time()
            }
            
            return jsonify({
                "success": True,
                "message": f"Scrcpy started for device {device_id}",
                "device": device_id
            })
        
        except Exception as e:
            return jsonify({
                "error": f"Failed to start scrcpy: {str(e)}. Make sure scrcpy is installed."
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scrcpy/stop", methods=["POST"])
def stop_scrcpy():
    try:
        data = request.get_json()
        device_id = data.get('device')
        
        if device_id in scrcpy_processes:
            try:
                process = scrcpy_processes[device_id]['process']
                process.terminate()
                time.sleep(0.5)
                
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
                
                del scrcpy_processes[device_id]
                
                return jsonify({
                    "success": True,
                    "message": f"Scrcpy stopped for device {device_id}"
                })
            except Exception as e:
                return jsonify({"error": f"Error stopping scrcpy: {str(e)}"}), 500
        
        return jsonify({"error": "No scrcpy session found for this device"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scrcpy/status", methods=["GET"])
def scrcpy_status():
    try:
        device_id = request.args.get('device')
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        is_running = False
        duration = 0
        
        if device_id in scrcpy_processes:
            process = scrcpy_processes[device_id]['process']
            if process.poll() is None:  # Process is still running
                is_running = True
                duration = int(time.time() - scrcpy_processes[device_id]['start_time'])
        
        return jsonify({
            "success": True,
            "device": device_id,
            "running": is_running,
            "duration": duration
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/control", methods=["POST"])
def device_control():
    try:
        data = request.get_json()
        device_id = data.get('device')
        action = data.get('action')
        
        if not device_id or not action:
            return jsonify({"error": "Device ID and action are required"}), 400
        
        # خريطة الأوامر (للأزرار السريعة بدون scrcpy)
        commands = {
            'power': f'adb -s {device_id} shell input keyevent 26',
            'home': f'adb -s {device_id} shell input keyevent 3',
            'back': f'adb -s {device_id} shell input keyevent 4',
            'volume_up': f'adb -s {device_id} shell input keyevent 24',
            'volume_down': f'adb -s {device_id} shell input keyevent 25',
            'menu': f'adb -s {device_id} shell input keyevent 82',
            'recents': f'adb -s {device_id} shell input keyevent 187',
        }
        
        if action in commands:
            cmd = commands[action]
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return jsonify({
                    "success": True,
                    "message": f"Action {action} executed successfully"
                })
            else:
                return jsonify({
                    "error": f"Failed to execute {action}: {result.stderr}"
                }), 500
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/screen/status", methods=["GET"])
def screen_status():
    device_id = request.args.get('device')
    
    if device_id in scrcpy_processes:
        process_info = scrcpy_processes[device_id]
        return jsonify({
            "success": True,
            "running": True,
            "device": device_id,
            "duration": int(time.time() - process_info['start_time'])
        })
    
    return jsonify({
        "success": True,
        "running": False,
        "device": device_id
    })

# === Advanced Features APIs ===

@app.route("/api/files/push", methods=["POST"])
def push_file():
    """نقل ملف من الكمبيوتر إلى الجهاز"""
    try:
        import tempfile
        device_id = request.form.get('device')
        file = request.files.get('file')
        destination = request.form.get('destination', '/sdcard/')
        
        if not device_id or not file:
            return jsonify({"error": "Device and file are required"}), 400
        
        # حفظ الملف مؤقتاً (يعمل على Windows و Linux)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        # نقل الملف إلى الجهاز
        cmd = f'adb -s {device_id} push "{temp_path}" "{destination}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # حذف الملف المؤقت
        try:
            os.remove(temp_path)
        except:
            pass
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"File {file.filename} pushed successfully"
            })
        else:
            return jsonify({"error": result.stderr or "Failed to push file"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/files/pull", methods=["POST"])
def pull_file():
    """نقل ملف من الجهاز إلى الكمبيوتر"""
    try:
        device_id = request.get_json().get('device')
        file_path = request.get_json().get('path')
        
        if not device_id or not file_path:
            return jsonify({"error": "Device and path are required"}), 400
        
        # إنشاء مسار محلي
        filename = file_path.split('/')[-1]
        local_path = f"/tmp/{filename}"
        
        # سحب الملف
        cmd = f"adb -s {device_id} pull {file_path} {local_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(local_path):
            return send_file(local_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({"error": "Failed to pull file"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/apps/install", methods=["POST"])
def install_app():
    """تثبيت تطبيق APK"""
    try:
        device_id = request.form.get('device')
        apk_file = request.files.get('apk')
        
        if not device_id or not apk_file:
            return jsonify({"error": "Device and APK file are required"}), 400
        
        temp_path = f"/tmp/{apk_file.filename}"
        apk_file.save(temp_path)
        
        cmd = f"adb -s {device_id} install -r {temp_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        os.remove(temp_path)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"App installed successfully",
                "output": result.stdout
            })
        else:
            return jsonify({
                "error": "Installation failed",
                "output": result.stderr
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/apps/list", methods=["GET"])
def list_apps():
    """عرض قائمة التطبيقات المثبتة"""
    try:
        device_id = request.args.get('device')
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        cmd = f"adb -s {device_id} shell pm list packages"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        packages = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('package:'):
                packages.append(line.replace('package:', ''))
        
        return jsonify({
            "success": True,
            "apps": packages,
            "total": len(packages)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/apps/uninstall", methods=["POST"])
def uninstall_app():
    """إلغاء تثبيت تطبيق"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        package_name = data.get('package')
        
        if not device_id or not package_name:
            return jsonify({"error": "Device and package name are required"}), 400
        
        cmd = f"adb -s {device_id} uninstall {package_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"App {package_name} uninstalled"
            })
        else:
            return jsonify({
                "error": result.stderr
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/apps/launch", methods=["POST"])
def launch_app():
    """تشغيل تطبيق"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        package_name = data.get('package')
        
        if not device_id or not package_name:
            return jsonify({"error": "Device and package name are required"}), 400
        
        cmd = f"adb -s {device_id} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"App {package_name} launched"
            })
        else:
            return jsonify({
                "error": result.stderr
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/reboot", methods=["POST"])
def reboot_device():
    """إعادة تشغيل الجهاز"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        mode = data.get('mode', 'system')  # system, recovery, bootloader
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        if mode == 'recovery':
            cmd = f"adb -s {device_id} reboot recovery"
        elif mode == 'bootloader':
            cmd = f"adb -s {device_id} reboot bootloader"
        else:
            cmd = f"adb -s {device_id} reboot"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"Device rebooting to {mode}"
            })
        else:
            return jsonify({"error": result.stderr}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/logcat", methods=["GET"])
def get_logcat():
    """الحصول على السجلات"""
    try:
        device_id = request.args.get('device')
        lines_count = request.args.get('lines', 100, type=int)
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        cmd = f"adb -s {device_id} logcat -d -v brief | head -n {lines_count}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        logs = result.stdout.split('\n')
        
        return jsonify({
            "success": True,
            "logs": [log for log in logs if log.strip()],
            "total": len(logs)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/clear_cache", methods=["POST"])
def clear_cache():
    """مسح الذاكرة المؤقتة"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        package_name = data.get('package')
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        if package_name:
            cmd = f"adb -s {device_id} shell pm clear {package_name}"
        else:
            cmd = f"adb -s {device_id} shell rm -rf /data/cache/*"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Cache cleared successfully"
            })
        else:
            return jsonify({"error": result.stderr}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/permissions", methods=["GET"])
def get_permissions():
    """الحصول على الأذونات المثبتة"""
    try:
        device_id = request.args.get('device')
        package_name = request.args.get('package')
        
        if not device_id or not package_name:
            return jsonify({"error": "Device and package are required"}), 400
        
        cmd = f"adb -s {device_id} shell dumpsys package {package_name} | grep -A 20 'requested permissions'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        permissions = []
        for line in result.stdout.split('\n'):
            if 'android.permission' in line:
                permissions.append(line.strip())
        
        return jsonify({
            "success": True,
            "permissions": permissions,
            "package": package_name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/wifi", methods=["POST"])
def manage_wifi():
    """التحكم بـ WiFi"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        action = data.get('action')  # on, off, list
        ssid = data.get('ssid')
        password = data.get('password')
        
        if not device_id or not action:
            return jsonify({"error": "Device and action are required"}), 400
        
        if action == 'on':
            cmd = f"adb -s {device_id} shell svc wifi enable"
        elif action == 'off':
            cmd = f"adb -s {device_id} shell svc wifi disable"
        elif action == 'list':
            cmd = f"adb -s {device_id} shell cmd wifi list-networks"
        else:
            return jsonify({"error": "Unknown action"}), 400
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        return jsonify({
            "success": True,
            "output": result.stdout
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/screenshot", methods=["POST"])
def system_screenshot():
    """التقاط لقطة شاشة"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        timestamp = int(time.time())
        filename = f"screenshot_{device_id}_{timestamp}.png"
        
        # التقاط لقطة
        cmd = f"adb -s {device_id} shell screencap -p /sdcard/screenshot.png"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            # سحب الصورة
            pull_cmd = f"adb -s {device_id} pull /sdcard/screenshot.png /tmp/{filename}"
            subprocess.run(pull_cmd, shell=True, capture_output=True, text=True)
            
            # قراءة وتحويل إلى base64
            if os.path.exists(f"/tmp/{filename}"):
                with open(f"/tmp/{filename}", "rb") as f:
                    image_data = f.read()
                
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                # تنظيف
                subprocess.run(f"adb -s {device_id} shell rm /sdcard/screenshot.png", shell=True)
                os.remove(f"/tmp/{filename}")
                
                return jsonify({
                    "success": True,
                    "image": image_base64,
                    "filename": filename
                })
        
        return jsonify({"error": "Failed to take screenshot"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/text", methods=["POST"])
def send_text():
    """إرسال نص إلى الجهاز"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        text = data.get('text')
        
        if not device_id or not text:
            return jsonify({"error": "Device and text are required"}), 400
        
        # تجنب الأحرف الخاصة
        safe_text = text.replace(' ', '%s').replace('"', '\\"')
        cmd = f"adb -s {device_id} shell input text {safe_text}"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Text sent"
            })
        else:
            return jsonify({"error": result.stderr}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/shell", methods=["POST"])
def shell_command():
    """تنفيذ أمر shell مباشر"""
    try:
        data = request.get_json()
        device_id = data.get('device')
        cmd_text = data.get('command')
        
        if not device_id or not cmd_text:
            return jsonify({"error": "Device and command are required"}), 400
        
        cmd = f"adb -s {device_id} shell {cmd_text}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        return jsonify({
            "success": True,
            "output": result.stdout,
            "error": result.stderr if result.stderr else None
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    try:
        subprocess.run(["adb", "--version"], capture_output=True, text=True)
        print("✓ ADB is installed and ready")
    except:
        print("✗ ADB is not installed or not in PATH")
    
    try:
        subprocess.run(["scrcpy", "--version"], capture_output=True, text=True)
        print("✓ Scrcpy is installed and ready")
    except:
        print("⚠ Scrcpy is not installed. Please install it from: https://github.com/Genymobile/scrcpy")
    
    # استخدام متغير البيئة PORT (للـ Railway و Heroku)
    port = int(os.environ.get('PORT', 5555))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Server starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)