#!/usr/bin/env python3
"""7z快捷压缩 - 终端压缩工具
接收文件路径参数，在终端中执行压缩
"""
import os
import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        # 没有参数时，打开文件选择对话框
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'set f to choose file with prompt "选择要压缩的文件" with multiple selections allowed\n'
                 'set paths to ""\n'
                 'repeat with i in f\n'
                 '  set paths to paths & POSIX path of i & " "\n'
                 'end repeat\n'
                 'return paths'],
                capture_output=True, text=True, timeout=120
            )
            if result.stdout.strip():
                files = result.stdout.strip().split()
            else:
                sys.exit(0)
        except Exception:
            sys.exit(0)
    else:
        files = sys.argv[1:]

    if not files:
        sys.exit(0)

    # 获取脚本路径
    if hasattr(sys, '_MEIPASS'):
        script_dir = sys._MEIPASS
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    script_path = os.path.join(script_dir, "7z_compress.sh")

    if not os.path.isfile(script_path):
        # 尝试其他路径
        for candidate in [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "7z_compress.sh"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Resources", "7z_compress.sh"),
        ]:
            if os.path.isfile(candidate):
                script_path = candidate
                break

    if not os.path.isfile(script_path):
        subprocess.run(["osascript", "-e",
                        'display dialog "找不到压缩脚本，请重新安装应用。" with title "7z快捷压缩" buttons {"OK"} default button "OK" with icon caution'])
        sys.exit(1)

    # 构建命令
    cmd = [script_path] + files

    # 在终端中执行
    apple_script = f'''
    tell application "Terminal"
        activate
        do script "{ ' '.join(cmd) }"
    end tell
    '''

    subprocess.run(["osascript", "-e", apple_script])

if __name__ == "__main__":
    main()
