#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PythonSocketTester — serial + WebSocket GUI (tkinter).

Single-file distribution: no cpgTuner_simple / instinct_mini_header required.

Run:  python PythonSocketTester.py   (conda env with tk recommended)

pip: pyserial, websocket-client

Optional runtime JSON (auto-created): minimal_tester_ws_history.json
Someone may also use ardSerial.py elsewhere on the robot stack; this script does not import it.
"""

import base64
import json
import os
import re
import struct
import threading
import time

import serial.tools.list_ports
import websocket
from tkinter import *
from tkinter import messagebox, ttk

_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _sanitize_ipv4_address(text):
    """Extract first IPv4 from device/UI strings."""
    if not text:
        return ""
    m = _RE_IPV4.search(str(text).strip())
    return m.group(0) if m else ""


class WebSocketClient:
    """OpenCatEsp32-style JSON WebSocket command channel (from cpgTuner_simple, inlined)."""

    def __init__(self, ip_address, port=81):
        self.ip_address = ip_address
        self.port = port
        self.ws = None
        self.is_connected = False
        self.url = f"ws://{ip_address}:{port}"
        self.last_heartbeat = 0
        self.heartbeat_interval = 5
        self.heartbeat_timeout = 20
        self.max_retries = 0
        self.retry_delay = 0.2
        self.connection_timeout = 3
        self.health_check_interval = 10
        self.last_health_check = 0
        self.last_activity = 0
        self.auto_reconnect = True
        self.reconnect_attempts = 0
        self.heartbeat_paused = False

    def connect(self):
        try:
            if self.ws:
                self.ws.close()
                self.ws = None
            self.ws = websocket.create_connection(
                self.url,
                timeout=self.connection_timeout,
                header={"User-Agent": "PythonSocketTester/1.0"},
            )
            self.is_connected = True
            self.last_heartbeat = time.time()
            self.last_activity = time.time()
            self.reconnect_attempts = 0
            self.auto_reconnect = True
            print(f"✅ WebSocket connected: {self.url}")
            return True
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            self.is_connected = False
            if self.auto_reconnect and self.max_retries > 0:
                self.handle_reconnect()
            return False

    def send_heartbeat(self):
        if not self.is_connected or not self.ws or self.heartbeat_paused:
            return False
        try:
            current_time = time.time()
            if current_time - self.last_heartbeat >= self.heartbeat_interval:
                self.ws.send(json.dumps({"type": "heartbeat", "timestamp": int(current_time * 1000)}))
                self.last_heartbeat = current_time
                return True
        except Exception as e:
            print(f"Heartbeat send failed: {e}")
            self.disconnect()
            return False
        return False

    def handle_reconnect(self):
        if self.max_retries <= 0:
            return
        if self.reconnect_attempts < self.max_retries:
            self.reconnect_attempts += 1
            delay = self.retry_delay * (2 ** (self.reconnect_attempts - 1))
            print(f"🔄 Retrying WebSocket in {delay}s (attempt {self.reconnect_attempts}/{self.max_retries})...")
            time.sleep(delay)
            self.connect()
        else:
            print(f"❌ Max WebSocket retries ({self.max_retries}) exceeded, giving up")

    def get_command_timeout(self, command):
        if command.startswith("b64:Q") or (command.startswith("B ") and len(command.split(" ")) > 10):
            return 120
        if (
            any(
                keyword in command
                for keyword in [
                    "acrobatic_moves",
                    "high_difficulty_action",
                    "complex_sequence",
                    "clap",
                    "kclap",
                    "pee",
                    "kpee",
                    "hunt",
                    "khunt",
                ]
            )
            or command.startswith("b64:S")
            or (command.startswith("b64:") and len(command) > 100)
        ):
            return 30
        return 5

    def send_command(self, command):
        if not self.is_connected or not self.ws:
            if not self.connect():
                return False
        timeout_seconds = self.get_command_timeout(command)
        was_heartbeat_active = not self.heartbeat_paused
        if timeout_seconds > 20 and was_heartbeat_active:
            self.heartbeat_paused = True
            print(f"Heartbeat check paused (command timeout {timeout_seconds}s)")
        try:
            if not self.heartbeat_paused:
                self.send_heartbeat()
            task_id = str(int(time.time() * 1000))
            json_message = json.dumps(
                {
                    "type": "command",
                    "taskId": task_id,
                    "commands": [command],
                    "timestamp": int(time.time() * 1000),
                }
            )
            self.ws.send(json_message)
            self.last_activity = time.time()
            print(f"WebSocket TX: {json_message}")
            self.ws.settimeout(3)
            max_attempts = 1
            for attempt in range(max_attempts):
                try:
                    response = self.ws.recv()
                    self.last_activity = time.time()
                    print(f"WebSocket RX: {response}")
                    try:
                        response_data = json.loads(response)
                        response_type = response_data.get("type")
                        response_task_id = response_data.get("taskId", "unknown")
                        if response_type == "response":
                            status = response_data.get("status")
                            if response_task_id != task_id:
                                print(f"📋 Skipping stale response (taskId: {response_task_id}, expected: {task_id})")
                                continue
                            if status == "completed" and "results" in response_data:
                                results = response_data["results"]
                                if results and len(results) > 0:
                                    combined_result = "\n".join(results)
                                    print(f"✅ Command result received (taskId: {task_id})")
                                    if was_heartbeat_active and self.heartbeat_paused:
                                        self.heartbeat_paused = False
                                        print("Heartbeat check resumed")
                                    return {"success": True, "results": combined_result}
                                if was_heartbeat_active and self.heartbeat_paused:
                                    self.heartbeat_paused = False
                                    print("Heartbeat check resumed")
                                    return True
                            if status == "error":
                                if was_heartbeat_active and self.heartbeat_paused:
                                    self.heartbeat_paused = False
                                    print("Heartbeat check resumed")
                                return False
                            if status == "running":
                                print(f"📋 Task {response_task_id} status: running, waiting...")
                                continue
                            print(f"📋 Task {response_task_id} status: {status}, waiting...")
                            continue
                        if response_type in ["connected", "heartbeat"]:
                            print(f"Got {response_type} message, still waiting for command result...")
                            continue
                    except json.JSONDecodeError:
                        pass
                except websocket.WebSocketTimeoutException:
                    print(f"WebSocket recv timeout (attempt {attempt + 1}/{max_attempts})")
                    continue
            print(f"⚠️ Response wait timeout (taskId: {task_id}), no complete result")
            if was_heartbeat_active and self.heartbeat_paused:
                self.heartbeat_paused = False
                print("Heartbeat check resumed")
            return True
        except websocket.WebSocketTimeoutException:
            print("WebSocket response timed out")
            if was_heartbeat_active and self.heartbeat_paused:
                self.heartbeat_paused = False
                print("Heartbeat check resumed")
            return False
        except Exception as e:
            print(f"WebSocket send failed: {e}")
            self.is_connected = False
            if was_heartbeat_active and self.heartbeat_paused:
                self.heartbeat_paused = False
                print("Heartbeat check resumed")
            return False

    def disconnect(self):
        self.auto_reconnect = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.is_connected = False
        print("WebSocket disconnected")


class SimpleSerial:
    def __init__(self, port, baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.main_engine = None
        self.is_connected = False
        try:
            import serial as pyserial_mod

            self.main_engine = pyserial_mod.Serial(port, baudrate, timeout=timeout)
            if self.main_engine.is_open:
                self.is_connected = True
                print(f"Serial connected: {port}")
        except Exception as e:
            print(f"Serial open failed: {e}")
            self.is_connected = False

    def write(self, data):
        if self.main_engine and self.is_connected:
            try:
                if not self.main_engine.is_open:
                    print("❌ Serial port closed")
                    self.is_connected = False
                    return
                if isinstance(data, str):
                    data = data.encode("utf-8")
                self.main_engine.write(data)
            except Exception as e:
                print(f"❌ Serial write failed: {e}")
                self.is_connected = False
                raise e

    def read_response(self, timeout=0.5):
        if not self.main_engine or not self.is_connected:
            return ""
        end_time = time.time() + timeout
        response = ""
        while time.time() < end_time:
            try:
                if self.main_engine.in_waiting > 0:
                    data = self.main_engine.read(self.main_engine.in_waiting)
                    response += data.decode("utf-8", errors="ignore")
            except Exception as e:
                error_msg = str(e)
                if "Device not configured" in error_msg or "Errno 6" in error_msg:
                    print(f"❌ Serial read failed (device disconnected): {e}")
                    self.is_connected = False
                break
            time.sleep(0.01)
        return response.strip()

    def close(self):
        if self.main_engine and self.is_connected:
            self.main_engine.close()
            self.is_connected = False


def send_command(serial_obj, command, tuner_instance=None):
    """Send text command via serial (+newline); optional fallback via tuner WebSocket."""
    if serial_obj and serial_obj.is_connected:
        try:
            serial_obj.write(command + "\n")
            print(f"Serial TX: {command}")
            if tuner_instance and hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(command, "send")
            response = serial_obj.read_response()
            if response:
                print(f"Serial RX: {response}")
                if tuner_instance and hasattr(tuner_instance, "add_serial_info"):
                    tuner_instance.add_serial_info(response, "receive")
            return response
        except Exception as e:
            print(f"❌ Serial send failed: {e}")
            if tuner_instance and hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(f"Serial error: {e}", "error")
            error_msg = str(e)
            if "Device not configured" in error_msg or "Errno 6" in error_msg:
                print("🔌 Device disconnected during serial TX")
                if tuner_instance and hasattr(tuner_instance, "root") and hasattr(
                    tuner_instance, "on_device_disconnected"
                ):
                    tuner_instance.root.after(0, tuner_instance.on_device_disconnected)
            print("Serial failed; trying WebSocket...")
    if tuner_instance and getattr(tuner_instance, "websocket_connected", False):
        result = tuner_instance.send_websocket_command(command)
        if result:
            if isinstance(result, dict) and "results" in result:
                return result["results"]
            return "WebSocket command OK"
        print("WebSocket send failed")
    print("No connection available (serial or WebSocket)")
    return ""


def send_K_skill_data(
    flat_list,
    tuner_instance=None,
    instinct_cpp_label=None,
    instinct_log_fragment=True,
):
    """
    Send K-prefixed skill bytes: serial binary first, then WebSocket b64 (b64:...).
    Compatible with OpenCat ardSerial serialWriteNumToByte 'K' framing.
    """
    if not flat_list or len(flat_list) < 4:
        return False
    var = []
    for x in flat_list:
        v = int(round(float(x)))
        if v > 127:
            v = 127
        elif v < -128:
            v = -128
        var.append(v)
    if instinct_log_fragment and tuner_instance and hasattr(
        tuner_instance, "_print_instinct_h_skill_fragment"
    ):
        log_label = instinct_cpp_label
        if log_label is None:
            ac = getattr(tuner_instance, "_active_skill", None)
            if isinstance(ac, dict) and ac.get("name"):
                log_label = ac["name"]
        tuner_instance._print_instinct_h_skill_fragment(log_label, var, name_is_c_ready=False)
    try:
        payload = b"K" + struct.pack("b" * len(var), *var) + b"~"
    except Exception as e:
        if tuner_instance and hasattr(tuner_instance, "add_serial_info"):
            tuner_instance.add_serial_info(f"K pack error: {e}", "error")
        return False
    delay_between_slice = 0.001

    def _send_serial_binary():
        if not tuner_instance or not getattr(tuner_instance, "serial_obj", None):
            return False
        serial_obj = tuner_instance.serial_obj
        if not (serial_obj.is_connected and serial_obj.main_engine):
            return False
        try:
            slice_size = 20
            offset = 0
            while offset < len(payload):
                chunk = payload[offset : offset + slice_size]
                serial_obj.write(chunk)
                offset += slice_size
                time.sleep(delay_between_slice)
            if hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(
                    f"K skill data sent via serial ({len(var)} values)", "info"
                )
            return True
        except Exception as e:
            if hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(f"K serial send error: {e}", "error")
            return False

    def _send_ws_b64():
        if not tuner_instance or not getattr(tuner_instance, "websocket_connected", False):
            return False
        try:
            k_cmd = "b64:" + base64.b64encode(payload).decode("ascii")
            result = tuner_instance.send_websocket_command(k_cmd)
            if result and hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(
                    f"K skill data sent via WebSocket ({len(var)} values)", "info"
                )
            return bool(result)
        except Exception as e:
            if hasattr(tuner_instance, "add_serial_info"):
                tuner_instance.add_serial_info(f"K WebSocket send error: {e}", "error")
            return False

    if _send_serial_binary():
        return True
    if _send_ws_b64():
        return True
    return False


os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

_RE_LINE_INTS = re.compile(r"-?\d+")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WS_HISTORY_PATH = os.path.join(_SCRIPT_DIR, "minimal_tester_ws_history.json")
_WS_HISTORY_MAX = 5

_CMD_INPUT_HISTORY_MAX = 200

_LANG_CHOICES = (
    ("en", "🇺🇸 English"),
    ("zh", "🇨🇳 中文"),
)

I18N = {
    "en": {
        "title": "Python WebSocket Tester",
        "lang_menu": "Language",
        "serial": "Serial:",
        "refresh": "Refresh",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "wifi_ssid": "WiFi SSID:",
        "password": "Password:",
        "btn_wifi": "WiFi connect",
        "btn_get_ip": "Get IP",
        "ws_host": "IP:",
        "port": "Port:",
        "ws_connect": "WS connect",
        "ws_disconnect": "WS disconnect",
        "monitor_title": "Serial monitor",
        "send_line": "Send line",
        "send_k_skill": "Send K skill",
        "e_no_port": "No port selected",
        "e_serial_open": "Failed to open",
        "w_no_host": "Enter a valid IPv4 or host:port",
        "w_bad_port": "Invalid port",
        "w_send_first": "Connect serial or WebSocket first",
        "k_need_conn": "Connect serial or WebSocket first",
        "k_fail": "send_K_skill_data failed",
        "e_wifi_ssid": "Enter WiFi SSID",
        "e_serial_first": "Connect serial first",
        "err_wifi_ip": "Could not get IP. Check SSID/password.",
        "warn_no_ip": "No IP; device may not be on WiFi.",
        "title_success": "Success",
        "title_hint": "Notice",
        "title_error": "Error",
        "title_warn": "Warning",
        "msg_wifi_ok_ws": "WiFi ready; WebSocket connected.\nIP / host: {ip}",
        "msg_wifi_ok_no_ws": "WiFi ready; IP: {ip}\nWebSocket auto-connect failed. Check port or tap WS connect.",
        "msg_ip_ok_ws": "Device IP / host: {ip}\nWebSocket connected.",
        "msg_ip_no_ws": "Device IP / host: {ip}\nWebSocket failed; try WS connect.",
        "ws_send_fail": "Send failed",
        "ws_conn_fail": "WebSocket connection failed",
        "test_section": "Quick test",
        "btn_kup": "Stand (kup)",
        "btn_ksit": "Sit (ksit)",
        "btn_rest": "Rest (d)",
        "btn_buzzer": "Buzzer",
        "btn_head": "Head (m)",
    },
    "zh": {
        "title": "Python WebSocket 测试器",
        "lang_menu": "语言",
        "serial": "串口:",
        "refresh": "刷新",
        "connect": "连接",
        "disconnect": "断开",
        "wifi_ssid": "WiFi SSID:",
        "password": "密码:",
        "btn_wifi": "连接WiFi",
        "btn_get_ip": "获取IP",
        "ws_host": "IP 地址：",
        "port": "端口:",
        "ws_connect": "WS 连接",
        "ws_disconnect": "WS 断开",
        "monitor_title": "串口监视器",
        "send_line": "发送行",
        "send_k_skill": "发送 K 技能",
        "e_no_port": "未选择串口",
        "e_serial_open": "无法打开",
        "w_no_host": "请输入有效 IPv4 或 IP:端口",
        "w_bad_port": "端口无效",
        "w_send_first": "请先连接串口或 WebSocket",
        "k_need_conn": "请先连接串口或 WebSocket",
        "k_fail": "send_K_skill_data 失败",
        "e_wifi_ssid": "请输入 WiFi 名称 (SSID)",
        "e_serial_first": "请先连接串口",
        "err_wifi_ip": "无法获取 IP，请检查 SSID 与密码。",
        "warn_no_ip": "未获取到 IP，设备可能未连接 WiFi。",
        "title_success": "成功",
        "title_hint": "提示",
        "title_error": "错误",
        "title_warn": "警告",
        "msg_wifi_ok_ws": "WiFi 已就绪，WebSocket 已连接。\nIP / 主机: {ip}",
        "msg_wifi_ok_no_ws": "WiFi 已就绪，IP: {ip}\nWebSocket 自动连接未成功，请检查端口或点击「WS 连接」。",
        "msg_ip_ok_ws": "设备 IP / 主机: {ip}\nWebSocket 已连接。",
        "msg_ip_no_ws": "设备 IP / 主机: {ip}\nWebSocket 失败，请尝试「WS 连接」。",
        "ws_send_fail": "发送失败",
        "ws_conn_fail": "WebSocket 连接失败",
        "test_section": "快速测试",
        "btn_kup": "起立 kup",
        "btn_ksit": "坐下 ksit",
        "btn_rest": "休息 d",
        "btn_buzzer": "蜂鸣器",
        "btn_head": "动头 m",
    },
}


# --- Instinct_Mini.h style arrays (see Instinct_Mini.h) ----------------------------
# const int8_t minimal_test_K[] PROGMEM = {
#     -5, 0, 0, 1,
#     1, 2, 3,
#     ... 5 frames x 20 ...
# };
DEFAULT_K_SKILL_DATA = [
    -5, 0, 0, 1,
    1, 2, 3,
    0, -20, -60, 0, 0, 0, 0, 0, 35, 30, 120, 105, 75, 60, -40, -30, 4, 2, 0, 0,
    35, -5, -60, 0, 0, 0, 0, 0, -99, 30, 125, 95, 40, 75, -45, -30, 10, 0, 0, 0,
    40, 0, -35, 0, 0, 0, 0, 0, -90, 30, 125, 95, 62, 75, -45, -30, 10, 0, 0, 0,
    0, 0, -45, 0, -5, -5, 20, 20, 45, 45, 105, 105, 45, 45, -45, -45, 8, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 30, 30, 30, 30, 30, 30, 30, 30, 5, 0, 0, 0,
]


def _load_ws_mru():
    try:
        with open(_WS_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[:_WS_HISTORY_MAX]
        if isinstance(data, dict) and "mru" in data:
            return list(data["mru"])[:_WS_HISTORY_MAX]
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return []


def _save_ws_mru(items):
    try:
        with open(_WS_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump({"mru": items}, f, indent=0)
    except OSError:
        pass


def list_serial_ports_filtered():
    """USB serial ports for UI; exclude cu.usbmodem-style devices per project preference."""
    out = []
    for p in serial.tools.list_ports.comports():
        dev = p.device
        low = dev.lower()
        if "usbmodem" in low:
            continue
        if "wchusbserial" in low or "usbserial" in low:
            out.append(dev)
    return sorted(set(out))


class MinimalTesterApp:
    def __init__(self):
        self.root = Tk()
        self.lang = "en"

        self.serial_obj = None
        self.is_connected = False
        self.websocket_clients = {}
        self.websocket_client = None
        self.websocket_connected = False
        self.device_ip = ""
        self.wifi_connected = False

        self.monitor_thread = None
        self.monitor_running = False

        self._ws_mru = _load_ws_mru()
        self._cmd_history = []
        self._cmd_hist_pos = None

        self._geom_w = 820
        self._geom_h = 700
        self.root.geometry(f"{self._geom_w}x{self._geom_h}")
        self.root.minsize(640, 480)

        self._build_ui()
        self.refresh_ports()
        self._apply_mru_to_combo()
        self._center_window()
        self.apply_language()

    def t(self, key, **fmt):
        s = I18N.get(self.lang, I18N["en"]).get(key) or I18N["en"].get(key, key)
        if fmt:
            try:
                return s.format(**fmt)
            except Exception:
                return s
        return s

    def apply_language(self):
        self.root.title(self.t("title"))
        for code, lab in _LANG_CHOICES:
            if code == self.lang:
                self.lang_select_var.set(lab)
                break
        self._w["lang_lbl"].config(text=self.t("lang_menu"))
        self._w["serial_lbl"].config(text=self.t("serial"))
        self.refresh_btn.config(text=self.t("refresh"))
        self.serial_btn.config(text=self.t("disconnect") if self.is_connected else self.t("connect"))
        self._w["wifi_ssid_lbl"].config(text=self.t("wifi_ssid"))
        self._w["pwd_lbl"].config(text=self.t("password"))
        self.wifi_btn.config(text=self.t("btn_wifi"))
        self.getip_btn.config(text=self.t("btn_get_ip"))
        self._w["ws_host_lbl"].config(text=self.t("ws_host"))
        self._w["port_lbl"].config(text=self.t("port"))
        self.ws_connect_btn.config(text=self.t("ws_connect"))
        self.ws_disconnect_btn.config(text=self.t("ws_disconnect"))
        self.test_lf.config(text=self.t("test_section"))
        self._w["mon_title"].config(text=self.t("monitor_title"))
        self.send_line_btn.config(text=self.t("send_line"))
        for key in self._test_btn_keys:
            self._test_buttons[key].config(text=self.t(key))
        self.send_k_test_btn.config(text=self.t("send_k_skill"))

    def set_lang(self, lang):
        if lang not in ("en", "zh"):
            return
        self.lang = lang
        self.apply_language()

    def _on_lang_combo_selected(self, _event=None):
        sel = self.lang_select_var.get()
        for code, lab in _LANG_CHOICES:
            if lab == sel:
                if self.lang != code:
                    self.lang = code
                    self.apply_language()
                return

    @staticmethod
    def _bind_press_effect(btn):
        def _down(_):
            btn.config(relief=SUNKEN)

        def _up(_):
            btn.config(relief=RAISED)

        btn.bind("<ButtonPress-1>", _down, add="+")
        btn.bind("<ButtonRelease-1>", _up, add="+")

    def _center_window(self):
        self.root.update_idletasks()
        w = self._geom_w
        h = self._geom_h
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        self._w = {}
        header = ttk.Frame(self.root, padding=(6, 4))
        header.pack(fill=X)
        ttk.Frame(header).pack(side=LEFT, fill=X, expand=True)
        lang_box = ttk.Frame(header)
        lang_box.pack(side=RIGHT, padx=(0, 4))
        self._w["lang_lbl"] = ttk.Label(lang_box, text="Language")
        self._w["lang_lbl"].pack(side=LEFT, padx=(0, 6))
        self.lang_select_var = StringVar(value=_LANG_CHOICES[0][1])
        self.lang_combo = ttk.Combobox(
            lang_box,
            textvariable=self.lang_select_var,
            values=[lab for _c, lab in _LANG_CHOICES],
            state="readonly",
            width=11,
        )
        self.lang_combo.pack(side=LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_combo_selected)

        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=X)

        serial_row = ttk.Frame(top)
        serial_row.pack(fill=X)
        self._w["serial_lbl"] = ttk.Label(serial_row, text="Serial:")
        self._w["serial_lbl"].pack(side=LEFT, padx=(0, 4))
        self.port_var = StringVar()
        self.port_combo = ttk.Combobox(serial_row, textvariable=self.port_var, width=28, state="readonly")
        self.port_combo.pack(side=LEFT, padx=(0, 8))
        self.refresh_btn = ttk.Button(serial_row, text="Refresh", command=self.refresh_ports, width=8)
        self.refresh_btn.pack(side=LEFT, padx=4)
        self.serial_btn = ttk.Button(serial_row, text="Connect", command=self.toggle_serial, width=10)
        self.serial_btn.pack(side=LEFT, padx=4)

        wifi_row = ttk.Frame(top)
        wifi_row.pack(fill=X, pady=(8, 0))
        self._w["wifi_ssid_lbl"] = ttk.Label(wifi_row, text="WiFi SSID:")
        self._w["wifi_ssid_lbl"].pack(side=LEFT, padx=(0, 4))
        self.wifi_ssid_var = StringVar()
        ttk.Entry(wifi_row, textvariable=self.wifi_ssid_var, width=16).pack(side=LEFT, padx=(0, 10))
        self._w["pwd_lbl"] = ttk.Label(wifi_row, text="Password:")
        self._w["pwd_lbl"].pack(side=LEFT, padx=(0, 4))
        self.wifi_password_var = StringVar()
        ttk.Entry(wifi_row, textvariable=self.wifi_password_var, width=14, show="*").pack(
            side=LEFT, padx=(0, 10)
        )
        self.wifi_btn = ttk.Button(wifi_row, text="WiFi connect", command=self.connect_wifi, width=10)
        self.wifi_btn.pack(side=LEFT, padx=4)
        self.getip_btn = ttk.Button(wifi_row, text="Get IP", command=self.get_device_ip_action, width=10)
        self.getip_btn.pack(side=LEFT, padx=4)

        ws_row = ttk.Frame(top)
        ws_row.pack(fill=X, pady=(6, 0))
        self._w["ws_host_lbl"] = ttk.Label(ws_row, text="Host:")
        self._w["ws_host_lbl"].pack(side=LEFT, padx=(0, 4))
        self.ip_var = StringVar()
        self.ip_combo = ttk.Combobox(ws_row, textvariable=self.ip_var, width=26, values=[])
        self.ip_combo.pack(side=LEFT, padx=(0, 8))
        self.ip_combo.bind("<<ComboboxSelected>>", self._on_ws_host_selected)
        self._w["port_lbl"] = ttk.Label(ws_row, text="Port:")
        self._w["port_lbl"].pack(side=LEFT, padx=(0, 4))
        self.ws_port_var = StringVar(value="81")
        ttk.Entry(ws_row, textvariable=self.ws_port_var, width=6).pack(side=LEFT, padx=(0, 12))
        self.ws_connect_btn = ttk.Button(ws_row, text="WS connect", command=self.connect_ws, width=12)
        self.ws_connect_btn.pack(side=LEFT, padx=4)
        self.ws_disconnect_btn = ttk.Button(ws_row, text="WS disconnect", command=self.disconnect_ws, width=12)
        self.ws_disconnect_btn.pack(side=LEFT, padx=4)

        self.test_lf = ttk.LabelFrame(top, padding=6, text="")
        self.test_lf.pack(fill=X, pady=(8, 0))
        test_inner = Frame(self.test_lf)
        test_inner.pack(fill=X)
        self._test_buttons = {}
        self._test_btn_keys = (
            "btn_kup",
            "btn_ksit",
            "btn_rest",
            "btn_buzzer",
            "btn_head",
        )
        _cmd_map = {
            "btn_kup": "kup",
            "btn_ksit": "ksit",
            "btn_rest": "d",
            "btn_buzzer": "b 20 4 22 4 27 4 22 4",
            "btn_head": "m0 -90 0 90 0 0",
        }
        for key in self._test_btn_keys:
            b = Button(
                test_inner,
                text=key,
                font=("Arial", 10),
                width=14,
                relief=RAISED,
                borderwidth=2,
                command=lambda c=_cmd_map[key]: self.send_preset_line(c),
            )
            self._bind_press_effect(b)
            b.pack(side=LEFT, padx=3, pady=2)
            self._test_buttons[key] = b
        self.send_k_test_btn = Button(
            test_inner,
            text="Send K skill",
            font=("Arial", 10, "bold"),
            width=16,
            relief=RAISED,
            borderwidth=2,
            command=self.send_k_skill,
        )
        self._bind_press_effect(self.send_k_test_btn)
        self.send_k_test_btn.pack(side=LEFT, padx=(12, 3), pady=2)

        mid = ttk.Frame(self.root, padding=(6, 0))
        mid.pack(fill=BOTH, expand=True)
        self._w["mon_title"] = ttk.Label(mid, text="Serial monitor")
        self._w["mon_title"].pack(anchor=W)
        self.monitor = Text(mid, height=22, wrap=WORD, state=DISABLED, font=("Menlo", 11))
        self.monitor.pack(fill=BOTH, expand=True, pady=(2, 6))

        bot = ttk.Frame(self.root, padding=6)
        bot.pack(fill=X)
        self.cmd_var = StringVar()
        self.cmd_entry = ttk.Entry(bot, textvariable=self.cmd_var)
        self.cmd_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        self.cmd_entry.bind("<Return>", self._on_cmd_return)
        self.cmd_entry.bind("<Up>", self._on_cmd_hist_up)
        self.cmd_entry.bind("<Down>", self._on_cmd_hist_down)
        self.send_line_btn = ttk.Button(bot, text="Send line", command=self.send_user_line, width=12)
        self.send_line_btn.pack(side=LEFT, padx=2)

    def _send_line_impl(self, line):
        line = line.rstrip()
        if not line:
            return
        if self.serial_obj and self.serial_obj.is_connected:
            try:
                self.serial_obj.write(line + "\n")
                self.add_serial_info(line, "send")
            except Exception as e:
                messagebox.showerror(self.t("title_error"), str(e), parent=self.root)
            return
        if self.websocket_connected:
            ok = self.send_websocket_command(line)
            if ok:
                self.add_serial_info(line, "send")
            else:
                messagebox.showwarning(
                    self.t("title_warn"),
                    self.t("ws_send_fail"),
                    parent=self.root,
                )
            return
        messagebox.showwarning(
            self.t("title_warn"),
            self.t("w_send_first"),
            parent=self.root,
        )

    def send_preset_line(self, line):
        self._send_line_impl(line)

    def _apply_mru_to_combo(self):
        self.ip_combo["values"] = tuple(self._ws_mru)
        if self._ws_mru and not self.ip_var.get().strip():
            self.ip_var.set(self._ws_mru[0])

    def _parse_ws_endpoint(self, raw):
        """Parse 'host' or 'host:port' into (ipv4, port)."""
        try:
            pdef = int(self.ws_port_var.get().strip() or "81")
        except ValueError:
            pdef = 81
        raw = (raw or "").strip()
        if not raw:
            return "", pdef
        if raw.count(":") == 1:
            host_part, pstr = raw.rsplit(":", 1)
            host_part = host_part.strip()
            try:
                port = int(pstr.strip())
            except ValueError:
                port = pdef
            ip = _sanitize_ipv4_address(host_part)
            if not ip:
                return "", pdef
            return ip, port
        ip = _sanitize_ipv4_address(raw)
        if not ip:
            return "", pdef
        return ip, pdef

    def _mru_push(self, ip, port):
        if not ip:
            return
        entry = f"{ip}:{port}"
        rest = [x for x in self._ws_mru if x != entry]
        self._ws_mru = [entry] + rest[: _WS_HISTORY_MAX - 1]
        self.ip_combo["values"] = tuple(self._ws_mru)
        _save_ws_mru(self._ws_mru)

    def _on_ws_host_selected(self, _event=None):
        raw = self.ip_var.get().strip()
        if ":" in raw:
            _h, p = self._parse_ws_endpoint(raw)
            try:
                self.ws_port_var.set(str(int(p)))
            except (ValueError, TypeError):
                pass

    def _on_cmd_return(self, _event=None):
        self.send_user_line()
        return "break"

    def _cmd_hist_append(self, line):
        line = line.rstrip()
        if not line:
            return
        if self._cmd_history and self._cmd_history[-1] == line:
            return
        self._cmd_history.append(line)
        if len(self._cmd_history) > _CMD_INPUT_HISTORY_MAX:
            self._cmd_history.pop(0)

    def _on_cmd_hist_up(self, _event=None):
        if not self._cmd_history:
            return "break"
        if self._cmd_hist_pos is None:
            self._cmd_hist_pos = len(self._cmd_history) - 1
        elif self._cmd_hist_pos > 0:
            self._cmd_hist_pos -= 1
        self.cmd_var.set(self._cmd_history[self._cmd_hist_pos])
        return "break"

    def _on_cmd_hist_down(self, _event=None):
        if self._cmd_hist_pos is None:
            return "break"
        if self._cmd_hist_pos < len(self._cmd_history) - 1:
            self._cmd_hist_pos += 1
            self.cmd_var.set(self._cmd_history[self._cmd_hist_pos])
        else:
            self._cmd_hist_pos = None
            self.cmd_var.set("")
        return "break"

    def log(self, text, tag="info"):
        def _do():
            self.monitor.config(state=NORMAL)
            self.monitor.insert(END, text + "\n")
            self.monitor.see(END)
            self.monitor.config(state=DISABLED)

        self.root.after(0, _do)

    def refresh_ports(self):
        ports = list_serial_ports_filtered()
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        elif not ports:
            self.port_var.set("")

    def get_device_ip(self):
        """Query device IP over serial (same protocol as cpgTuner_simple)."""
        if not self.is_connected or not self.serial_obj:
            return ""
        try:
            self.serial_obj.write("w\n")
            self.add_serial_info("w", "send")
            response = self.serial_obj.read_response(timeout=2.0)
            if not response:
                self.log("[ip] empty response")
                return ""
            self.add_serial_info(response, "receive")
            for line in response.split("\n"):
                if "IP Address:" in line:
                    ip_part = line.split("IP Address:", 1)[1].strip()
                    ip_part = _sanitize_ipv4_address(ip_part) or (
                        ip_part.split()[0] if ip_part else ""
                    )
                    if ip_part and ip_part != "WiFi未连接":
                        self.device_ip = ip_part
                        return ip_part
                    return ""
            return ""
        except Exception as e:
            self.log(f"[ip] error: {e}", "err")
            return ""

    def send_wifi_config(self, ssid, password):
        if not self.is_connected or not self.serial_obj:
            return False
        command = f"w%{ssid}%{password}"
        send_command(self.serial_obj, command, self)
        self.log("* waiting for WiFi (~5s)…")
        time.sleep(5)
        ip_address = self.get_device_ip()
        if not ip_address:
            return False
        self.device_ip = ip_address
        try:
            p = int(self.ws_port_var.get().strip() or "81")
        except ValueError:
            p = 81
        self.ip_var.set(f"{ip_address}:{p}")
        self._open_websocket_to_ip(host_override=ip_address, port_override=p, interactive=False)
        return True

    def connect_wifi(self):
        ssid = self.wifi_ssid_var.get().strip()
        password = self.wifi_password_var.get().strip()
        if not ssid:
            messagebox.showerror(self.t("title_error"), self.t("e_wifi_ssid"), parent=self.root)
            return
        if not self.is_connected or not self.serial_obj:
            messagebox.showerror(self.t("title_error"), self.t("e_serial_first"), parent=self.root)
            return
        self.log(f"* configuring WiFi: {ssid}")
        try:
            if self.send_wifi_config(ssid, password):
                self.wifi_connected = True
                ip = self.device_ip
                if self.websocket_connected:
                    messagebox.showinfo(
                        self.t("title_success"),
                        self.t("msg_wifi_ok_ws", ip=ip),
                        parent=self.root,
                    )
                else:
                    messagebox.showinfo(
                        self.t("title_hint"),
                        self.t("msg_wifi_ok_no_ws", ip=ip),
                        parent=self.root,
                    )
            else:
                messagebox.showerror(
                    self.t("title_error"),
                    self.t("err_wifi_ip"),
                    parent=self.root,
                )
        except Exception as e:
            messagebox.showerror(self.t("title_error"), str(e), parent=self.root)

    def get_device_ip_action(self):
        if not self.is_connected or not self.serial_obj:
            messagebox.showerror(self.t("title_error"), self.t("e_serial_first"), parent=self.root)
            return
        ip = self.get_device_ip()
        if ip:
            try:
                p = int(self.ws_port_var.get().strip() or "81")
            except ValueError:
                p = 81
            self.ip_var.set(f"{ip}:{p}")
            if self._open_websocket_to_ip(host_override=ip, port_override=p, interactive=False):
                messagebox.showinfo(
                    self.t("title_success"),
                    self.t("msg_ip_ok_ws", ip=ip),
                    parent=self.root,
                )
            else:
                messagebox.showinfo(
                    self.t("title_hint"),
                    self.t("msg_ip_no_ws", ip=ip),
                    parent=self.root,
                )
        else:
            messagebox.showwarning(
                self.t("title_warn"),
                self.t("warn_no_ip"),
                parent=self.root,
            )

    def _open_websocket_to_ip(self, interactive=True, host_override=None, port_override=None):
        if host_override is not None:
            ip = _sanitize_ipv4_address(str(host_override))
            try:
                port = int(port_override if port_override is not None else self.ws_port_var.get() or 81)
            except ValueError:
                port = 81
        else:
            raw = self.ip_var.get().strip()
            ip, port = self._parse_ws_endpoint(raw)
        if not ip:
            if interactive:
                messagebox.showwarning(
                    self.t("title_warn"),
                    self.t("w_no_host"),
                    parent=self.root,
                )
            return False
        try:
            if port_override is None and host_override is None:
                self.ws_port_var.set(str(port))
        except Exception:
            pass
        if ip in self.websocket_clients:
            self.log(f"[ws] already connected {ip}")
            self._mru_push(ip, port)
            return True
        client = WebSocketClient(ip, port)
        if client.connect():
            self.websocket_clients[ip] = client
            if not self.websocket_client:
                self.websocket_client = client
            self.websocket_connected = True
            self.log(f"[ws] connected ws://{ip}:{port}")
            self._mru_push(ip, port)
            self.ip_var.set(f"{ip}:{port}")
            return True
        if interactive:
            messagebox.showerror(
                self.t("title_error"), self.t("ws_conn_fail"), parent=self.root
            )
        return False

    def toggle_serial(self):
        if self.is_connected:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        path = self.port_var.get().strip()
        if not path:
            messagebox.showwarning(self.t("title_warn"), self.t("e_no_port"), parent=self.root)
            return
        self.serial_obj = SimpleSerial(path)
        if self.serial_obj.is_connected:
            self.is_connected = True
            self.serial_btn.config(text=self.t("disconnect"))
            self.log(f"[serial] connected {path}")
            self.start_monitor()
        else:
            self.serial_obj = None
            messagebox.showerror(
                self.t("title_error"),
                f"{self.t('e_serial_open')} {path}",
                parent=self.root,
            )
        self.apply_language()

    def disconnect_serial(self):
        self.stop_monitor()
        if self.serial_obj:
            try:
                self.serial_obj.close()
            except Exception:
                pass
            self.serial_obj = None
        self.is_connected = False
        self.serial_btn.config(text=self.t("connect"))
        self.log("[serial] disconnected")
        self.apply_language()

    def start_monitor(self):
        if self.monitor_running:
            return
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self.monitor_thread.start()

    def stop_monitor(self):
        self.monitor_running = False

    def _monitor_worker(self):
        while self.monitor_running and self.is_connected and self.serial_obj and self.serial_obj.main_engine:
            try:
                eng = self.serial_obj.main_engine
                if eng.in_waiting > 0:
                    raw = eng.readline()
                    line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if line:
                        self.log(line, "rx")
                else:
                    time.sleep(0.05)
            except Exception as e:
                self.log(f"[serial read] {e}", "err")
                break

    def connect_ws(self):
        self._open_websocket_to_ip(interactive=True)

    def disconnect_ws(self):
        for _ip, c in list(self.websocket_clients.items()):
            try:
                c.disconnect()
            except Exception:
                pass
        self.websocket_clients.clear()
        self.websocket_client = None
        self.websocket_connected = False
        self.log("[ws] disconnected all")

    def add_serial_info(self, msg, kind="info"):
        prefix = {"send": ">", "receive": "<", "info": "*", "error": "!"}.get(kind, "*")
        self.log(f"{prefix} {msg}")

    def send_websocket_command(self, command):
        if not self.websocket_clients:
            return False
        success = False
        for _ip, client in list(self.websocket_clients.items()):
            try:
                r = client.send_command(command)
                if r:
                    success = True
            except Exception as e:
                self.log(f"[ws send error] {e}", "err")
        return success

    def send_user_line(self):
        line = self.cmd_var.get().strip()
        if not line:
            return
        self._cmd_hist_append(line)
        self._cmd_hist_pos = None
        self._send_line_impl(line)
        self.cmd_var.set("")

    def send_k_skill(self):
        if not self.serial_obj or not getattr(self.serial_obj, "is_connected", False):
            if not self.websocket_connected:
                messagebox.showwarning(
                    self.t("title_warn"),
                    self.t("k_need_conn"),
                    parent=self.root,
                )
                return
        ok = send_K_skill_data(
            list(DEFAULT_K_SKILL_DATA),
            tuner_instance=self,
            instinct_cpp_label="minimal_test_K",
            instinct_log_fragment=False,
        )
        if ok:
            self.log("[K] payload sent (107 int8 values)")
        else:
            messagebox.showerror(self.t("title_error"), self.t("k_fail"), parent=self.root)

    def parse_k_skill_text(self, text):
        nums = [int(x) for x in _RE_LINE_INTS.findall(text)]
        return nums

    def run(self):
        self.root.mainloop()


def main():
    app = MinimalTesterApp()
    app.run()


if __name__ == "__main__":
    main()
