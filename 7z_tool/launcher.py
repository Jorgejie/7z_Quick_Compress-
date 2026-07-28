#!/usr/bin/env python3
"""7z快捷压缩 - 启动器
自动启动 HTTP 服务并打开浏览器
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Thread

PORT_START = 8765
PORT_END = 8775

# ── 心跳检测配置 ──
HEARTBEAT_TIMEOUT = 120  # 120秒无心跳则认为页面已关闭
last_heartbeat_time = time.time()
heartbeat_lock = threading.Lock()
page_closed = False

# ── 日志（打包后无控制台，写文件便于排查） ──
LOG_DIR = os.path.expanduser("~/Library/Logs/7z快捷压缩")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "launcher.log")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ── 配置管理 ──
CONFIG_DIR = os.path.expanduser("~/Library/Application Support/7z快捷压缩")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PORT_FILE = os.path.join(CONFIG_DIR, "port.json")
# 拖拽上传暂存目录（浏览器拿不到拖入文件的绝对路径，需上传字节到本地后端）
UPLOAD_DIR = os.path.expanduser("~/Library/Caches/7z快捷压缩/uploads")
DEFAULT_CONFIG = {
    "format": "7z",
    "level": 9,
    "password": "",
    "split": "",
    "output_dir": "",
    "extreme": False,
    "merge_split": False,
}


def load_config():
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(saved)
            return cfg
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ── 端口管理 ──
def save_port_info(port):
    """保存当前使用的端口信息，供下次启动快速定位"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(PORT_FILE, "w", encoding="utf-8") as f:
            json.dump({"port": port, "pid": os.getpid()}, f)
    except Exception:
        pass


def load_port_info():
    """读取上次保存的端口信息"""
    try:
        if os.path.isfile(PORT_FILE):
            with open(PORT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def port_is_listening(port):
    """快速检测端口是否有进程在监听 (<1ms)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.01)
            result = s.connect_ex(("127.0.0.1", port))
            return result == 0
    except Exception:
        return False


def find_available_port(start, end):
    """在指定范围内寻找可用端口"""
    for port in range(start, end + 1):
        if not port_is_listening(port):
            return port
    return None


def find_existing_instance_port(start, end):
    """快速探测已有实例的端口，先socket探测再HTTP验证"""
    # 快速路径：先查看上次保存的端口
    saved = load_port_info()
    if saved and saved.get("port"):
        saved_port = saved["port"]
        if saved_port >= start and saved_port <= end:
            if port_is_listening(saved_port) and _http_check(saved_port):
                return saved_port

    # 扫描端口范围
    for port in range(start, end + 1):
        if port_is_listening(port):
            if _http_check(port):
                return port
    return None


def _http_check(port):
    """HTTP 验证端口上是否运行的是本应用"""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/check_7z",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=1)
        resp.read()
        return True
    except Exception:
        return False


# ── Service 安装 ──
SERVICES_DIR = os.path.expanduser("~/Library/Services")
SERVICE_VERSION = "# v11"  # 版本标记：变更时自动重装 workflow
SERVICES = [
    # (workflow 文件名, 菜单名, 服务脚本, bundle id 后缀)
    ("7z快捷压缩.workflow", "7z快捷压缩", "compress_service.sh", "7zquickcompress"),
    ("7z快捷解压.workflow", "7z快捷解压", "extract_service.sh", "7zquickextract"),
]


def _get_script_path(script_name="compress_service.sh"):
    """获取服务脚本的路径"""
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, script_name))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name))
    exe_dir = os.path.dirname(sys.executable)
    resources_dir = os.path.join(os.path.dirname(exe_dir), "Resources")
    candidates.append(os.path.join(resources_dir, script_name))
    candidates.append(os.path.join(resources_dir, "_internal", script_name))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return candidates[0]



def _build_workflow_plist(script_path):
    """生成 Automator Quick Action 的 document.wflow plist 内容

    严格按 Automator 真实导出的 Quick Action 结构生成（含 AMDocumentVersion、
    AMParameterProperties、arguments、workflowMetaData 输入输出类型声明等），
    缺字段会导致新版 macOS 的 WorkflowServiceRunner 抛 NSInternalInconsistencyException 崩溃。
    """
    import uuid
    import plistlib

    action_id = uuid.uuid4().hex[:24].upper()
    output_id = uuid.uuid4().hex[:24].upper()

    shell_cmd = (
        f"{SERVICE_VERSION} - Run Shell Script (native)\n"
        f'nohup "{script_path}" "$@" >/dev/null 2>&1 &\n'
    )

    plist_data = {
        'AMApplicationBuild': '528',
        'AMApplicationVersion': '2.10',
        'AMDocumentVersion': '2',
        'actions': [
            {
                'action': {
                    'AMAccepts': {
                        'Container': 'List',
                        'Optional': True,
                        'Types': ['com.apple.cocoa.string']
                    },
                    'AMActionVersion': '2.0.3',
                    'AMApplication': ['Automator'],
                    'AMParameterProperties': {
                        'COMMAND_STRING': {},
                        'CheckedForUserReplacement': {},
                        'inputMethod': {},
                        'shell': {},
                        'source': {},
                    },
                    'AMProvides': {
                        'Container': 'List',
                        'Types': ['com.apple.cocoa.string']
                    },
                    'ActionBundlePath': '/System/Library/Automator/Run Shell Script.action',
                    'ActionName': 'Run Shell Script',
                    'ActionParameters': {
                        'COMMAND_STRING': shell_cmd,
                        'CheckedForUserReplacement': False,
                        'inputMethod': 1,  # 作为参数传入 ("$@")
                        'shell': '/bin/bash',
                        'source': '',
                    },
                    'BundleIdentifier': 'com.apple.RunShellScript',
                    'CFBundleVersion': '2.0.3',
                    'CanShowSelectedItemsWhenRun': False,
                    'CanShowWhenRun': True,
                    'Category': ['AMCategoryUtilities'],
                    'Class Name': 'RunShellScriptAction',
                    'InputUUID': action_id,
                    'Keywords': ['Shell', 'Script', 'Command', 'Run', 'Unix'],
                    'OutputUUID': output_id,
                    'UUID': action_id,
                    'UnlocalizedApplications': ['Automator'],
                    'arguments': {
                        '0': {'default value': 0, 'name': 'inputMethod', 'required': '0', 'type': '0', 'uuid': '0'},
                        '1': {'default value': False, 'name': 'CheckedForUserReplacement', 'required': '0', 'type': '0', 'uuid': '1'},
                        '2': {'default value': '', 'name': 'source', 'required': '0', 'type': '0', 'uuid': '2'},
                        '3': {'default value': '', 'name': 'COMMAND_STRING', 'required': '0', 'type': '0', 'uuid': '3'},
                        '4': {'default value': '/bin/sh', 'name': 'shell', 'required': '0', 'type': '0', 'uuid': '4'},
                    },
                    'isViewVisible': 1,
                    'location': '309.000000:253.000000',
                    'nibPath': '/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib',
                },
                'isViewVisible': 1,
            }
        ],
        'connectors': {},
        'workflowMetaData': {
            'applicationBundleIDsByPath': {},
            'applicationPaths': [],
            'inputTypeIdentifier': 'com.apple.Automator.fileSystemObject',
            'outputTypeIdentifier': 'com.apple.Automator.nothing',
            'presentationMode': 15,
            'processesInput': 0,
            'serviceInputTypeIdentifier': 'com.apple.Automator.fileSystemObject',
            'serviceOutputTypeIdentifier': 'com.apple.Automator.nothing',
            'serviceProcessesInput': 0,
            'systemImageName': 'NSActionTemplate',
            'useAutomaticInputType': 0,
            'workflowTypeIdentifier': 'com.apple.Automator.servicesMenu',
        }
    }

    return plistlib.dumps(plist_data, fmt=plistlib.FMT_XML).decode('utf-8')


def _build_service_info_plist(menu_name, bundle_suffix):
    """生成 workflow 的 Info.plist（NSServices 声明右键菜单项）"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>Chinese</string>
    <key>CFBundleIdentifier</key>
    <string>com.apple.Automator.{bundle_suffix}</string>
    <key>CFBundleName</key>
    <string>{menu_name}</string>
    <key>CFBundleDisplayName</key>
    <string>{menu_name}</string>
    <key>CFBundlePackageType</key>
    <string>BNDL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>{menu_name}</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendFileTypes</key>
            <array>
                <string>public.item</string>
                <string>public.data</string>
                <string>public.content</string>
            </array>
        </dict>
    </array>
</dict>
</plist>"""


def install_service():
    """安装压缩/解压两个 Automator Quick Action 到 ~/Library/Services/"""
    changed = False
    for workflow_name, menu_name, script_name, bundle_suffix in SERVICES:
        script_path = _get_script_path(script_name)
        if not os.path.isfile(script_path):
            log(f"{script_name} 不存在: {script_path}")
            continue

        workflow_path = os.path.join(SERVICES_DIR, workflow_name)
        contents_dir = os.path.join(workflow_path, "Contents")
        wflow_path = os.path.join(contents_dir, "document.wflow")

        # 已安装且版本与脚本路径均一致则跳过
        if os.path.isfile(wflow_path):
            try:
                existing = Path(wflow_path).read_text(encoding="utf-8")
                if script_path in existing and SERVICE_VERSION in existing:
                    log(f"{menu_name} Service 已安装且版本正确，跳过")
                    continue
                log(f"{menu_name} Service 版本已变更，重新安装")
            except Exception:
                pass

        log(f"安装 Service: {menu_name} -> {script_path}")
        try:
            os.makedirs(contents_dir, exist_ok=True)
            Path(wflow_path).write_text(_build_workflow_plist(script_path), encoding="utf-8")
            Path(os.path.join(contents_dir, "Info.plist")).write_text(
                _build_service_info_plist(menu_name, bundle_suffix), encoding="utf-8")
            changed = True
            log(f"{menu_name} Service 安装成功")
        except Exception as e:
            log(f"{menu_name} Service 安装失败: {e}")

    if changed:
        # 刷新 macOS Services 缓存
        subprocess.run(["/System/Library/CoreServices/pbs", "-flush"], capture_output=True, timeout=5)
        # 重启 Finder 以重新加载服务（macOS Sonoma+ 需要）
        try:
            subprocess.run(["killall", "Finder"], capture_output=True, timeout=5)
            log("Finder 已重启")
        except Exception:
            pass


def show_alert(title, text):
    """弹出 macOS 对话框通知用户"""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display dialog "{text}" with title "{title}" buttons {{"OK"}} default button "OK" with icon caution'
        ], capture_output=True, timeout=10)
    except Exception:
        pass


def resource_path(relative):
    """获取打包后的资源路径，兼容多种打包布局"""
    candidates = []
    # 1. PyInstaller one-file 模式: _MEIPASS 是临时解压目录
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, relative))
    # 2. 脚本同级目录 (开发时 / spec 的 COLLECT 目录)
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), relative))
    # 3. macOS .app 的 Contents/Resources/ 目录
    exe_dir = os.path.dirname(sys.executable)
    resources_dir = os.path.join(os.path.dirname(exe_dir), "Resources")
    candidates.append(os.path.join(resources_dir, relative))
    # 4. PyInstaller _internal 目录 (新版布局)
    candidates.append(os.path.join(resources_dir, "_internal", relative))

    for p in candidates:
        if os.path.exists(p):
            return p
    # 回退：返回最常见的路径
    return candidates[1] if len(candidates) > 1 else relative


def find_7z():
    """查找 7z 可执行文件"""
    import platform
    import shutil

    current_arch = platform.machine()

    def arch_ok(path):
        """检测二进制是否可在当前架构运行"""
        try:
            result = subprocess.run(
                ["file", path], capture_output=True, text=True, timeout=1
            )
            return current_arch in result.stdout or (
                current_arch == "aarch64" and "arm64" in result.stdout
            )
        except Exception:
            return True  # 无法检测时假定可用

    # 1. 打包内自带的 (p7zip 完整目录) — 需要架构检查
    bundled = resource_path("p7zip/7z")
    if os.path.isfile(bundled) and arch_ok(bundled):
        return bundled
    # 2. 常见安装路径 — 系统路径无需架构检查（Homebrew 保证架构匹配）
    for p in ["/opt/homebrew/bin/7z", "/usr/local/bin/7z", "/usr/bin/7z"]:
        if os.path.isfile(p):
            return p
    # 3. PATH 中查找
    found = shutil.which("7z")
    if found:
        return found
    return None


# ── 7z 懒加载（后台解析，避免阻塞启动） ──
SEVENZIP = None
_7z_event = threading.Event()


def _resolve_7z():
    """后台线程解析 7z 路径"""
    global SEVENZIP
    try:
        SEVENZIP = find_7z()
        log(f"7z 解析完成: {SEVENZIP or '未找到'}")
    except Exception as e:
        log(f"7z 解析失败: {e}")
    _7z_event.set()
DESKTOP = os.path.expanduser("~/Desktop")
STATIC_DIR = None


# ── 压缩/解压辅助函数 ──
def _total_input_size(paths):
    """计算输入文件/目录的总字节数"""
    total = 0
    for p in paths:
        try:
            if os.path.isfile(p):
                total += os.path.getsize(p)
            elif os.path.isdir(p):
                for root, _dirs, names in os.walk(p):
                    for name in names:
                        try:
                            total += os.path.getsize(os.path.join(root, name))
                        except OSError:
                            pass
        except OSError:
            pass
    return total


def _pick_dict_size_mb(total_bytes, cap_mb):
    """字典大小自适应：输入总大小向上取整到 2 的幂，上限 cap_mb，下限 16m"""
    size_mb = max(1, (total_bytes + 1048575) // 1048576)
    d = 16
    while d < size_mb and d < cap_mb:
        d *= 2
    return min(d, cap_mb)


# 分卷后缀 (.001/.002...) 与常见归档后缀
def _prepare_volumes(paths):
    """分卷分组归一化：同组分卷只保留 .001；跨目录的分卷硬链接到同一暂存目录"""
    import re
    import shutil
    import uuid
    vols = {}
    others = []
    for p in paths:
        m = re.match(r"^(.*)\.(\d{3})$", os.path.basename(p))
        if m:
            vols.setdefault(m.group(1), []).append(p)
        elif p not in others:
            others.append(p)
    result = list(others)
    for base, parts in vols.items():
        dirs = {os.path.dirname(p) for p in parts}
        if len(dirs) == 1:
            d = dirs.pop()
        else:
            # 分卷散落在不同目录（如分批拖拽上传），归位到同一暂存目录
            d = os.path.join(UPLOAD_DIR, "vol_" + uuid.uuid4().hex[:8])
            os.makedirs(d, exist_ok=True)
            for p in parts:
                link = os.path.join(d, os.path.basename(p))
                if not os.path.exists(link):
                    try:
                        os.link(p, link)
                    except OSError:
                        shutil.copy2(p, link)
        first = os.path.join(d, base + ".001")
        if not os.path.isfile(first):
            raise ValueError(f"缺少分卷 {base}.001，请把所有分卷一起添加")
        result.append(first)
    return result


def _archive_stem(path):
    """去掉归档后缀得到主名，用作解压子目录名"""
    import re
    name = os.path.basename(path)
    name = re.sub(r"\.\d{3}$", "", name)  # 先去分卷序号
    name = re.sub(r"\.(tar\.(gz|bz2|xz)|tgz|tbz2|txz|7z|zip|rar|tar|gz|bz2|xz)$", "", name, flags=re.IGNORECASE)
    return name or "extracted"

# ── 多线程 HTTP 服务器，避免 picker 阻塞其他请求 ──
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


# ── 预热 osascript（首次调用需初始化 OSA 框架，约数十秒） ──
def warmup_osascript():
    """在后台线程预热 osascript，避免首次选择文件时卡顿"""
    try:
        subprocess.run(
            ["osascript", "-e", 'id of app "Finder"'],
            capture_output=True, timeout=30,
        )
        log("osascript 预热完成")
    except Exception as e:
        log(f"osascript 预热失败: {e}")


def heartbeat_monitor():
    """心跳监控线程，检测页面是否仍然活跃"""
    global last_heartbeat_time, page_closed
    log("心跳监控线程启动")
    
    while not page_closed:
        time.sleep(5)  # 每5秒检查一次
        
        with heartbeat_lock:
            elapsed = time.time() - last_heartbeat_time
        
        if elapsed > HEARTBEAT_TIMEOUT:
            log(f"心跳超时 ({elapsed:.1f}s > {HEARTBEAT_TIMEOUT}s)，页面可能已关闭，准备退出...")
            page_closed = True
            os._exit(0)
    
    log("心跳监控线程退出")


def activate_app():
    """激活应用到前台（macOS 特有）"""
    try:
        # 尝试通过 osascript 激活应用
        script = '''
        tell application "System Events"
            set frontmost of process "Python" to true
        end tell
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        log("应用激活成功")
    except Exception as e:
        log(f"应用激活失败: {e}")


def open_browser(port):
    """直接打开浏览器（socket 已绑定，无需轮询等待）"""
    url = f"http://localhost:{port}"
    log(f"打开浏览器: {url}")

    # 先激活应用到前台
    activate_app()

    # 多策略打开浏览器
    opened = False

    # 策略 1: macOS open 命令（使用 -g 选项在后台打开，避免阻塞）
    try:
        subprocess.run(["open", "-g", url], capture_output=True, timeout=10)
        opened = True
        log("浏览器打开成功 (open -g 命令)")
    except Exception as e:
        log(f"open -g 命令失败: {e}")

    # 策略 2: macOS open 命令（无 -g 选项）
    if not opened:
        try:
            subprocess.run(["open", url], capture_output=True, timeout=10)
            opened = True
            log("浏览器打开成功 (open 命令)")
        except Exception as e:
            log(f"open 命令失败: {e}")

    # 策略 3: webbrowser 模块
    if not opened:
        try:
            webbrowser.open(url)
            log("浏览器打开成功 (webbrowser)")
            opened = True
        except Exception as e:
            log(f"webbrowser 失败: {e}")

    # 策略 4: 尝试用 Python 打开 Chromium/Chrome
    if not opened:
        for browser in [
            "/Applications/Google Chrome.app",
            "/Applications/Chromium.app",
            "/Applications/Safari.app",
        ]:
            try:
                subprocess.run(["open", "-a", browser, url], capture_output=True, timeout=10)
                log(f"浏览器打开成功 ({browser})")
                opened = True
                break
            except Exception:
                continue

    if not opened:
        log("所有浏览器打开策略均失败!")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
            return

        # 静态资源 (Vite 构建的 JS/CSS)
        if STATIC_DIR:
            safe_path = os.path.normpath(self.path.lstrip("/"))
            file_path = os.path.join(STATIC_DIR, safe_path)
            if os.path.isfile(file_path) and file_path.startswith(STATIC_DIR):
                ext = os.path.splitext(file_path)[1]
                mime = {".js": "application/javascript", ".css": "text/css", ".png": "image/png",
                        ".svg": "image/svg+xml", ".json": "application/json", ".ico": "image/x-icon",
                        ".woff2": "font/woff2", ".woff": "font/woff"}.get(ext, "application/octet-stream")
                try:
                    data = Path(file_path).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass

        self.send_error(404)

    def do_POST(self):
        routes = {
            "/stat": self._handle_stat,
            "/compress": self._handle_compress,
            "/extract": self._handle_extract,
            "/upload": self._handle_upload,
            "/open_finder": self._handle_open_finder,
            "/pick_files": self._handle_pick_files,
            "/pick_folder": self._handle_pick_folder,
            "/check_7z": self._handle_check_7z,
            "/get_config": self._handle_get_config,
            "/save_config": self._handle_save_config,
            "/heartbeat": self._handle_heartbeat,
            "/page_close": self._handle_page_close,
        }
        handler = routes.get(self.path.split("?")[0])
        if handler:
            try:
                handler()
            except Exception as e:
                # 兜底：任何异常都返回 JSON，避免连接重置导致前端 Failed to fetch
                log(f"接口异常 {self.path}: {e}")
                try:
                    self._json_response({"success": False, "error": f"服务内部错误: {e}"})
                except Exception:
                    pass
        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _handle_check_7z(self):
        self._json_response({
            "found": SEVENZIP is not None,
            "path": SEVENZIP or "",
            "resolving": not _7z_event.is_set(),
        })

    def _handle_get_config(self):
        self._json_response(load_config())

    def _handle_save_config(self):
        body = self._read_body()
        save_config(body)
        self._json_response({"success": True})

    def _handle_stat(self):
        body = self._read_body()
        path = os.path.expanduser(body.get("path", "").strip())
        exists = os.path.exists(path)
        name = os.path.basename(path.rstrip("/")) if exists else ""
        self._json_response({"exists": exists, "path": path, "name": name})

    def _handle_upload(self):
        """接收拖拽上传的文件字节，存入暂存目录并返回绝对路径"""
        import re
        import urllib.parse
        import uuid
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        name = params.get("name", ["upload.bin"])[0]
        name = os.path.basename(name).strip() or "upload.bin"
        # 同一次拖放的文件用同一会话子目录，保证分卷落在一起
        sid = re.sub(r"[^A-Za-z0-9]", "", params.get("sid", [""])[0])[:16]
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self._json_response({"success": False, "error": "空文件或文件夹，请用选择按钮添加"})
            return
        sub = os.path.join(UPLOAD_DIR, sid or uuid.uuid4().hex[:8])
        try:
            os.makedirs(sub, exist_ok=True)
            dest = os.path.join(sub, name)
            remaining = length
            with open(dest, "wb") as f:
                while remaining > 0:
                    chunk = self.rfile.read(min(1048576, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            if remaining > 0:
                os.remove(dest)
                self._json_response({"success": False, "error": "上传不完整"})
                return
            log(f"上传接收: {dest} ({length} 字节)")
            self._json_response({"success": True, "path": dest, "name": name})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)})

    def _handle_pick_files(self):
        try:
            # 激活应用到前台，确保 osascript 对话框能正常显示
            activate_app()
            result = subprocess.run(
                ["osascript", "-e",
                 'set f to choose file with prompt "选择要压缩的文件" with multiple selections allowed\n'
                 'set paths to ""\n'
                 'repeat with i in f\n'
                 '  set paths to paths & POSIX path of i & "\\n"\n'
                 'end repeat\n'
                 'return paths'],
                capture_output=True, text=True, timeout=120
            )
            paths = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            self._json_response({"paths": paths})
        except Exception:
            self._json_response({"paths": []})

    def _handle_pick_folder(self):
        try:
            # 激活应用到前台，确保 osascript 对话框能正常显示
            activate_app()
            result = subprocess.run(
                ["osascript", "-e",
                 'POSIX path of (choose folder with prompt "选择文件夹")'],
                capture_output=True, text=True, timeout=120
            )
            path = result.stdout.strip()
            self._json_response({"path": path})
        except Exception:
            self._json_response({"path": ""})

    def _handle_compress(self):
        # 如果 7z 尚未解析完成，等待最多 3 秒
        if not SEVENZIP and not _7z_event.is_set():
            _7z_event.wait(timeout=3)
        if not SEVENZIP:
            self._json_response({"success": False, "error": "未找到 7z，请先安装: brew install p7zip"})
            return

        body = self._read_body()
        files = body["files"]
        output_name = body.get("output", "output.7z")
        output_dir = body.get("output_dir", "").strip()
        fmt = body.get("format", "7z")
        level = body.get("level", 9)
        pwd = body.get("password", "")
        split = body.get("split", "")
        extreme = bool(body.get("extreme", False))
        merge_split = bool(body.get("merge_split", False))

        if output_dir:
            output_dir = os.path.expanduser(output_dir)
        else:
            output_dir = os.path.dirname(files[0])

        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, output_name)

        cmd = [SEVENZIP, "a", f"-t{fmt}", f"-mx={level}"]
        if fmt == "7z":
            if level >= 5:
                # 字典大小按输入总大小自适应，大字典 + fb=273 显著提升压缩率
                dict_mb = _pick_dict_size_mb(_total_input_size(files), 512 if extreme else 64)
                cmd.append(f"-m0=lzma2:d={dict_mb}m:fb=273")
                cmd.append("-ms=on")   # 固实压缩
                cmd.append("-mqs=on")  # 按扩展名排序，同类文件相邻
                if extreme:
                    cmd.append("-mmt=2")  # 减少 LZMA2 分块对压缩率的损失
                    cmd.append("-myx=9")  # 可执行文件过滤器分析
            else:
                cmd.append("-m0=lzma2")
        elif fmt == "zip" and level >= 9:
            cmd.append("-mfb=258")
            cmd.append("-mpass=15")
        if split:
            cmd.append(f"-v{split}")
        if pwd:
            cmd.append(f"-p{pwd}")
            if fmt == "7z":
                cmd.append("-mhe=on")
        cmd.append(output)
        cmd.extend(files)

        t0 = datetime.now()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800 if extreme else 600)
            dur = (datetime.now() - t0).total_seconds()
            if proc.returncode == 0:
                # 收集分卷产物（分卷时不存在主文件，只有 .001/.002... 分卷）
                parts = []
                for i in range(1, 1000):
                    part = f"{output}.{i:03d}"
                    if os.path.exists(part):
                        parts.append(part)
                    else:
                        break
                merged_parts = 0
                if split and merge_split and parts:
                    if len(parts) == 1:
                        # 内容不足一卷：直接转正为单文件
                        os.replace(parts[0], output)
                    else:
                        # 所有分卷打包进单个容器文件（仅存储，不再二次压缩）
                        if os.path.exists(output):
                            os.remove(output)  # 防止向旧档追加
                        proc2 = subprocess.run(
                            [SEVENZIP, "a", "-t7z", "-mx=0", output] + parts,
                            capture_output=True, text=True, timeout=600,
                        )
                        if proc2.returncode != 0:
                            self._json_response({
                                "success": False,
                                "error": "分卷合并失败: " + (proc2.stdout + proc2.stderr).strip()[:500],
                            })
                            return
                        for p in parts:
                            os.remove(p)
                        merged_parts = len(parts)
                    parts = []
                size = os.path.getsize(output) if os.path.exists(output) else 0
                for p in parts:
                    size += os.path.getsize(p)
                resp = {
                    "success": True, "output": output, "output_dir": output_dir,
                    "size": size, "size_mb": round(size / 1048576, 1),
                    "duration": f"{dur:.1f}s",
                }
                if merged_parts:
                    resp["merged_parts"] = merged_parts
                self._json_response(resp)
            else:
                self._json_response({
                    "success": False,
                    "error": (proc.stdout + proc.stderr).strip() or f"7z 返回码: {proc.returncode}"
                })
        except subprocess.TimeoutExpired:
            self._json_response({"success": False, "error": "压缩超时 (10分钟)"})
        except Exception as e:
            self._json_response({"success": False, "error": str(e)})

    def _handle_extract(self):
        # 如果 7z 尚未解析完成，等待最多 3 秒
        if not SEVENZIP and not _7z_event.is_set():
            _7z_event.wait(timeout=3)
        if not SEVENZIP:
            self._json_response({"success": False, "error": "未找到 7z，请先安装: brew install p7zip"})
            return

        body = self._read_body()
        files = body.get("files", [])
        output_dir = body.get("output_dir", "").strip()
        pwd = body.get("password", "")

        if not files:
            self._json_response({"success": False, "error": "未选择压缩包"})
            return

        # 分卷归一化 + 去重（多个分卷只解一次；跨目录分卷自动归位）
        try:
            archives = _prepare_volumes([os.path.expanduser(f) for f in files])
        except ValueError as e:
            self._json_response({"success": False, "error": str(e)})
            return

        if output_dir:
            output_dir = os.path.expanduser(output_dir)
        else:
            output_dir = os.path.dirname(archives[0])

        t0 = datetime.now()
        extracted_dirs = []
        total_entries = 0
        for archive in archives:
            if not os.path.isfile(archive):
                self._json_response({"success": False, "error": f"文件不存在: {archive}"})
                return

            dest = os.path.join(output_dir, _archive_stem(archive))
            # 避免与输出目录里的同名文件冲突（如解 xxx.apk.7z.001 时旁边已有 xxx.apk 文件）
            if os.path.exists(dest) and not os.path.isdir(dest):
                n = 1
                while os.path.exists(f"{dest}_{n}") and not os.path.isdir(f"{dest}_{n}"):
                    n += 1
                dest = f"{dest}_{n}"
            os.makedirs(dest, exist_ok=True)

            # 无密码时也传 -p，防止 7z 在无 tty 时挂起等待输入
            cmd = [SEVENZIP, "x", archive, f"-o{dest}", "-y", f"-p{pwd}"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            except subprocess.TimeoutExpired:
                self._json_response({"success": False, "error": "解压超时 (10分钟)"})
                return
            except Exception as e:
                self._json_response({"success": False, "error": str(e)})
                return

            if proc.returncode != 0:
                err = (proc.stdout + proc.stderr).strip()
                if "Wrong password" in err:
                    err = "密码错误" if pwd else "压缩包已加密，请输入密码"
                elif archive.endswith(".001") and ("Can't open as archive" in err or "Missing volume" in err):
                    err = "分卷不完整：请确保 .001/.002 等所有分卷都已一起添加"
                self._json_response({"success": False, "error": err or f"7z 返回码: {proc.returncode}"})
                return

            # tar.gz/tgz 等二次解压：若结果目录里只有一个 .tar，自动再解一次
            try:
                entries = os.listdir(dest)
                if len(entries) == 1 and entries[0].lower().endswith(".tar"):
                    inner_tar = os.path.join(dest, entries[0])
                    proc2 = subprocess.run(
                        [SEVENZIP, "x", inner_tar, f"-o{dest}", "-y", "-p"],
                        capture_output=True, text=True, timeout=600,
                    )
                    if proc2.returncode == 0:
                        os.remove(inner_tar)
            except Exception as e:
                log(f"tar 二次解压失败: {e}")

            try:
                total_entries += len(os.listdir(dest))
            except OSError:
                pass
            extracted_dirs.append(dest)

        dur = (datetime.now() - t0).total_seconds()
        self._json_response({
            "success": True,
            "output_dir": extracted_dirs[0] if len(extracted_dirs) == 1 else output_dir,
            "extracted_count": total_entries,
            "duration": f"{dur:.1f}s",
        })

    def _handle_open_finder(self):
        body = self._read_body()
        path = body.get("path", "")
        if path and os.path.exists(path):
            subprocess.run(["open", "-R", path])
        self._json_response({"ok": True})

    def _handle_heartbeat(self):
        """处理心跳请求，更新最后心跳时间"""
        global last_heartbeat_time
        with heartbeat_lock:
            last_heartbeat_time = time.time()
        self._json_response({"ok": True, "timestamp": last_heartbeat_time})

    def _handle_page_close(self):
        """处理页面关闭通知"""
        global page_closed
        page_closed = True
        log("收到页面关闭通知，准备退出...")
        self._json_response({"ok": True})
        # 延迟一小段时间确保响应发送完成
        Thread(target=self._shutdown_server, daemon=True).start()

    def _shutdown_server(self):
        """延迟关闭服务器"""
        time.sleep(0.5)
        log("正在关闭服务器...")
        # 使用 os._exit 强制退出，避免 serve_forever 阻塞
        os._exit(0)

    def _json_response(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    global HTML_PAGE, STATIC_DIR

    log("=== main() 开始 ===")

    # ── 1. 快速探测已有实例（socket探测 <1ms + HTTP验证 1s） ──
    existing_port = find_existing_instance_port(PORT_START, PORT_END)
    if existing_port is not None:
        log(f"检测到已有实例运行于端口 {existing_port}，直接打开浏览器")
        open_browser(existing_port)
        log("=== 已有实例，退出 ===")
        sys.exit(0)

    # ── 2. 寻找可用端口 ──
    port = find_available_port(PORT_START, PORT_END)
    if port is None:
        log("所有端口均被占用")
        show_alert("7z快捷压缩", "启动失败: 无可用端口 (8765-8775 均被占用)，请关闭其他程序后重试。")
        sys.exit(1)
    log(f"使用端口: {port}")

    # ── 3. 加载 HTML 页面 ──
    _html_path = None
    for _candidate in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_dist", "index.html"),
        resource_path("html_dist/index.html"),
        resource_path("html/index.html"),
    ]:
        if os.path.isfile(_candidate):
            _html_path = _candidate
            break
    if not _html_path:
        _html_path = resource_path("html/index.html")

    if _html_path:
        _html_dir = os.path.dirname(_html_path)
        _assets_dir = os.path.join(_html_dir, "assets")
        if os.path.isdir(_assets_dir):
            STATIC_DIR = _html_dir
            log(f"静态资源目录: {STATIC_DIR}")

    log(f"启动器启动, _MEIPASS={getattr(sys, '_MEIPASS', 'N/A')}")
    log(f"HTML路径: {_html_path}, 存在={os.path.isfile(_html_path)}")
    HTML_PAGE = Path(_html_path).read_text(encoding="utf-8") if os.path.isfile(_html_path) else ""
    log(f"HTML加载: {'成功, 长度=' + str(len(HTML_PAGE)) if HTML_PAGE else '失败!'}")

    if not HTML_PAGE:
        log("错误: HTML 资源文件未找到!")
        show_alert("7z快捷压缩", "启动失败: 找不到 HTML 资源文件，请重新安装应用。")
        sys.exit(1)

    # ── 4. 启动 HTTP 服务器（socket 在构造器中立即绑定） ──
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log(f"HTTP 服务已启动: http://localhost:{port}")
    print(f"7z快捷压缩 已启动: http://localhost:{port}")

    # ── 5. 保存端口信息 + 直接打开浏览器（无需轮询） ──
    save_port_info(port)
    time.sleep(0.3)  # 短暂安全延迟，确保 OS 注册 socket
    open_browser(port)

    # ── 6. 后台任务（不阻塞主线程） ──
    Thread(target=install_service, daemon=True).start()     # 安装右键压缩 Service
    Thread(target=_resolve_7z, daemon=True).start()         # 解析 7z 路径
    Thread(target=warmup_osascript, daemon=True).start()    # 预热 osascript
    Thread(target=heartbeat_monitor, daemon=True).start()   # 心跳监控线程
    Thread(target=_clean_uploads, daemon=True).start()      # 清理上次的拖拽上传暂存

    # ── 7. 主循环 ──
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("收到中断信号，退出")
    except Exception as e:
        log(f"服务异常: {e}")
        show_alert("7z快捷压缩", f"运行异常: {e}")


def _clean_uploads():
    """清理上次运行遗留的拖拽上传暂存文件"""
    import shutil
    try:
        if os.path.isdir(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
            log("上传暂存目录已清理")
    except Exception as e:
        log(f"清理上传暂存失败: {e}")


def run_compress_in_terminal(files):
    """在终端中执行压缩脚本"""
    # 获取 7z_compress.sh 路径
    script_path = resource_path("7z_compress.sh")
    if not os.path.isfile(script_path):
        show_alert("7z快捷压缩", "找不到压缩脚本，请重新安装应用。")
        sys.exit(1)

    # 构建命令
    cmd = [script_path] + files

    # 在终端中执行
    apple_script = f'''
    tell application "Terminal"
        activate
        do script "{' '.join(cmd)}"
    end tell
    '''
    subprocess.run(["osascript", "-e", apple_script])


if __name__ == "__main__":
    try:
        # 检查是否有文件参数（拖拽到应用图标上的文件）
        if len(sys.argv) > 1:
            files = sys.argv[1:]
            log(f"收到文件参数: {files}")
            run_compress_in_terminal(files)
        else:
            main()
    except Exception as e:
        log(f"致命错误: {e}")
        show_alert("7z快捷压缩", f"启动失败: {e}")
        sys.exit(1)
