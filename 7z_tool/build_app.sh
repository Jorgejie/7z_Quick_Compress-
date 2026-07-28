#!/bin/bash
# 7z快捷压缩 - macOS 打包脚本
# 用法: bash build_app.sh [arm64|x86_64|universal2]
set -e

APP_NAME="7z快捷压缩"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$PROJECT_DIR/dist"
APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$APP_NAME.dmg"

# ── 解析架构参数 ──
TARGET_ARCH="${1:-universal2}"
case "$TARGET_ARCH" in
    arm64|x86_64|universal2) ;;
    *) echo "用法: $0 [arm64|x86_64|universal2]"; exit 1 ;;
esac

if [ "$TARGET_ARCH" = "universal2" ]; then
    DMG_PATH="$DIST_DIR/${APP_NAME}-universal2.dmg"
else
    DMG_PATH="$DIST_DIR/${APP_NAME}-${TARGET_ARCH}.dmg"
fi

echo "========================================="
echo "  目标架构: $TARGET_ARCH"
echo "========================================="

# ── 生成 PyInstaller spec ──
generate_spec() {
    local arch="$1"
    local include_bundle="${2:-true}"

    cat > "$PROJECT_DIR/${APP_NAME}.spec" << SPEC_EOF
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('html/index.html', 'html'),
        ('html_dist/', 'html_dist'),
        ('compress_service.sh', '.'),
        ('extract_service.sh', '.'),
        ('7z_compress.sh', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='7z快捷压缩',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
    target_arch='$arch',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='7z快捷压缩',
)
SPEC_EOF

    if [ "$include_bundle" = "true" ]; then
        cat >> "$PROJECT_DIR/${APP_NAME}.spec" << 'BUNDLE_EOF'

app = BUNDLE(
    coll,
    name='7z快捷压缩.app',
    icon=None,
    bundle_identifier='com.7zquickcompress.app',
    info_plist={
        'CFBundleName': '7z快捷压缩',
        'CFBundleDisplayName': '7z快捷压缩',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.13',
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': '需要 AppleScript 权限来选择文件和文件夹',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'All Files',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['public.item'],
                'CFBundleTypeExtensions': ['*'],
            }
        ],
    },
)
BUNDLE_EOF
    fi
}

# ── 构建后处理：清理、签名、打包资源 ──
post_process() {
    local app_path="$1"

    # 清理 .DS_Store 和 resource fork 文件
    find "$app_path" -name ".DS_Store" -delete 2>/dev/null || true
    find "$app_path" -name "._*" -delete 2>/dev/null || true

    # 复制 7z 二进制
    local app_resources="$app_path/Contents/Resources"
    local collect_dir="$app_resources/7z快捷压缩"

    # 查找 p7zip 目录（支持 arm64 和 x86_64 Homebrew 路径）
    local p7zip_lib_dir=""
    for dir in /opt/homebrew/Cellar/p7zip/*/lib/p7zip \
               /usr/local/Cellar/p7zip/*/lib/p7zip; do
        if [ -d "$dir" ] && [ -f "$dir/7z" ]; then
            p7zip_lib_dir="$dir"
            break
        fi
    done

    # 检查 p7zip 架构是否与目标架构匹配
    local skip_p7zip=false
    if [ -n "$p7zip_lib_dir" ] && [ -f "$p7zip_lib_dir/7z" ]; then
        local p7z_arch=$(file "$p7zip_lib_dir/7z" | grep -o 'arm64\|x86_64' | head -1)
        if [ "$TARGET_ARCH" != "universal2" ] && [ "$p7z_arch" != "$TARGET_ARCH" ]; then
            echo "警告: p7zip ($p7z_arch) 与目标架构 ($TARGET_ARCH) 不匹配，跳过内嵌"
            skip_p7zip=true
        fi
    fi

    if [ -n "$p7zip_lib_dir" ] && [ "$skip_p7zip" = "false" ]; then
        mkdir -p "$app_resources/p7zip"
        # 使用 ditto 替代 cp，避免携带 resource fork / xattr
        ditto --noextattr --norsrc "$p7zip_lib_dir/7z" "$app_resources/p7zip/7z"
        ditto --noextattr --norsrc "$p7zip_lib_dir/7z.so" "$app_resources/p7zip/7z.so"
        chmod +x "$app_resources/p7zip/7z"
        if [ -d "$collect_dir" ]; then
            mkdir -p "$collect_dir/p7zip"
            ditto --noextattr --norsrc "$p7zip_lib_dir/7z" "$collect_dir/p7zip/7z"
            ditto --noextattr --norsrc "$p7zip_lib_dir/7z.so" "$collect_dir/p7zip/7z.so"
            chmod +x "$collect_dir/p7zip/7z"
        fi
        echo "已打包 7z 库: $p7zip_lib_dir"
    else
        echo "警告: 未找到 7z 二进制文件，用户需要自行安装 (brew install p7zip)"
    fi

    # 复制 html_dist/ (Vite 产物) 或 html/ (回退) 到 Resources
    if [ -d "$PROJECT_DIR/html_dist" ]; then
        ditto --noextattr --norsrc "$PROJECT_DIR/html_dist" "$app_resources/html_dist"
        if [ -d "$collect_dir" ]; then
            ditto --noextattr --norsrc "$PROJECT_DIR/html_dist" "$collect_dir/html_dist"
        fi
        echo "已打包 html_dist/ (Vite 产物)"
    else
        mkdir -p "$app_resources/html"
        cp "$PROJECT_DIR/html/index.html" "$app_resources/html/"
        if [ -d "$collect_dir" ]; then
            mkdir -p "$collect_dir/html"
            cp "$PROJECT_DIR/html/index.html" "$collect_dir/html/"
        fi
        echo "已打包 html/ (无 Vite 产物)"
    fi

    # 复制 compress_service.sh / extract_service.sh 到 Resources
    for svc in compress_service.sh extract_service.sh; do
        if [ -f "$PROJECT_DIR/$svc" ]; then
            cp "$PROJECT_DIR/$svc" "$app_resources/"
            chmod +x "$app_resources/$svc"
            if [ -d "$collect_dir" ]; then
                cp "$PROJECT_DIR/$svc" "$collect_dir/"
                chmod +x "$collect_dir/$svc"
            fi
            echo "已打包 $svc"
        fi
    done

    # 复制 7z_compress.sh 到 Resources
    if [ -f "$PROJECT_DIR/7z_compress.sh" ]; then
        cp "$PROJECT_DIR/7z_compress.sh" "$app_resources/"
        chmod +x "$app_resources/7z_compress.sh"
        if [ -d "$collect_dir" ]; then
            cp "$PROJECT_DIR/7z_compress.sh" "$collect_dir/"
            chmod +x "$collect_dir/7z_compress.sh"
        fi
        echo "已打包 7z_compress.sh"
    fi

    # 最终清理：用 ditto 复制以剥离所有 xattr/resource fork
    local app_clean="${app_path}_clean"
    rm -rf "$app_clean"
    ditto --noextattr --norsrc "$app_path" "$app_clean"
    rm -rf "$app_path"
    mv "$app_clean" "$app_path"

    # 签名
    codesign --remove-signature "$app_path" 2>/dev/null || true
    codesign --force --deep -s - "$app_path" 2>&1 && echo "签名成功" || {
        echo "常规签名失败，尝试回退方案..."
        find "$app_path/Contents" \( -name "*.so" -o -name "*.dylib" \) -type f \
            -exec codesign --force -s - {} \; 2>/dev/null || true
        codesign --force -s - "$app_path/Contents/Frameworks/Python3.framework" 2>/dev/null || true
        codesign --force -s - "$app_path/Contents/MacOS/"* 2>/dev/null || true
        codesign --force --deep -s - "$app_path" 2>&1 && echo "签名成功" || echo "签名跳过"
    }
}

# ── 创建 DMG ──
create_dmg() {
    local app_path="$1"
    local dmg_path="$2"
    local dmg_name="$3"

    rm -f "$dmg_path"

    local dmg_temp="$BUILD_DIR/dmg_temp"
    rm -rf "$dmg_temp"
    mkdir -p "$dmg_temp"
    ditto --noextattr --norsrc "$app_path" "$dmg_temp/$(basename "$app_path")"
    ln -s /Applications "$dmg_temp/Applications"

    hdiutil create \
        -volname "$dmg_name" \
        -srcfolder "$dmg_temp" \
        -ov \
        -format UDZO \
        -imagekey zlib-level=9 \
        "$dmg_path"
}

# ═══════════════════════════════════════════
#  构建
# ═══════════════════════════════════════════

echo "=== Vite 构建 ==="
cd "$PROJECT_DIR"
if [ -f "node_modules/.package-lock.json" ]; then
    npx vite build 2>&1
    echo "Vite 构建完成"
else
    echo "未找到 node_modules，使用 html/ 目录 (请先 npm install)"
fi

echo "=== 清理旧构建 ==="
rm -rf "$BUILD_DIR" "$DIST_DIR" "$PROJECT_DIR/__pycache__"

if [ "$TARGET_ARCH" = "arm64" ] || [ "$TARGET_ARCH" = "universal2" ]; then
    echo ""
    echo "══════ 构建 arm64 ══════"

    generate_spec "arm64" "true"

    cd "$PROJECT_DIR"
    python3 -m PyInstaller --clean \
        --distpath "$DIST_DIR" \
        --workpath "$BUILD_DIR/arm64" \
        "$APP_NAME.spec"

    if [ "$TARGET_ARCH" = "arm64" ]; then
        post_process "$APP_PATH"
        create_dmg "$APP_PATH" "$DMG_PATH" "7z快捷压缩"
    else
        # 保存 arm64 产物用于后续合并
        rm -rf "$BUILD_DIR/arm64_app"
        cp -R "$APP_PATH" "$BUILD_DIR/arm64_app"
        echo "arm64 构建完成，产物已保存"
    fi
fi

if [ "$TARGET_ARCH" = "x86_64" ] || [ "$TARGET_ARCH" = "universal2" ]; then
    echo ""
    echo "══════ 构建 x86_64 ══════"

    # x86_64 只需要 COLLECT（不需要 BUNDLE）
    generate_spec "x86_64" "false"

    cd "$PROJECT_DIR"
    arch -x86_64 python3 -m PyInstaller --clean \
        --distpath "$DIST_DIR/x86_64" \
        --workpath "$BUILD_DIR/x86_64" \
        "$APP_NAME.spec"

    if [ "$TARGET_ARCH" = "x86_64" ]; then
        # 仅 Intel 构建：手动创建 .app bundle
        echo ""
        echo "=== 手动创建 x86_64 .app Bundle ==="
        INTEL_COLLECT="$DIST_DIR/x86_64/7z快捷压缩"
        rm -rf "$APP_PATH"
        mkdir -p "$APP_PATH/Contents/MacOS"
        mkdir -p "$APP_PATH/Contents/Resources"
        mkdir -p "$APP_PATH/Contents/Frameworks"

        # Info.plist
        cat > "$APP_PATH/Contents/Info.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>7z快捷压缩</string>
    <key>CFBundleExecutable</key>
    <string>7z快捷压缩</string>
    <key>CFBundleIconFile</key>
    <string>icon-windowed.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.7zquickcompress.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>7z快捷压缩</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>需要 AppleScript 权限来选择文件和文件夹</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST_EOF

        cp "$INTEL_COLLECT/7z快捷压缩" "$APP_PATH/Contents/MacOS/"
        chmod +x "$APP_PATH/Contents/MacOS/7z快捷压缩"

        # 复制 COLLECT 内容到 Resources/7z快捷压缩/
        cp -R "$INTEL_COLLECT/"* "$APP_PATH/Contents/Resources/" 2>/dev/null || true

        # 建立 Frameworks 符号链接
        if [ -d "$APP_PATH/Contents/Resources/Python3.framework" ]; then
            ln -sf ../Resources/Python3.framework "$APP_PATH/Contents/Frameworks/Python3.framework"
        fi

        post_process "$APP_PATH"
        create_dmg "$APP_PATH" "$DMG_PATH" "7z快捷压缩"
    else
        echo "x86_64 COLLECT 构建完成"
    fi
fi

if [ "$TARGET_ARCH" = "universal2" ]; then
    echo ""
    echo "══════ 合并 universal2 ══════"

    ARM64_COLLECT="$DIST_DIR/7z快捷压缩/7z快捷压缩"
    X86_COLLECT="$DIST_DIR/x86_64/7z快捷压缩/7z快捷压缩"
    ARM64_APP="$BUILD_DIR/arm64_app"

    # 验证两个 EXE 的架构
    echo "arm64 EXE: $(file "$ARM64_COLLECT" | grep -o 'arm64\|x86_64')"
    echo "x86_64 EXE: $(file "$X86_COLLECT" | grep -o 'arm64\|x86_64')"

    # lipo 合并主 EXE
    echo "合并主 EXE..."
    lipo -create "$ARM64_COLLECT" "$X86_COLLECT" -output "$ARM64_COLLECT.universal"
    mv "$ARM64_COLLECT.universal" "$ARM64_COLLECT"

    # ── 合并 Python 框架为 universal2 ──
    ARM64_FW="$ARM64_APP/Contents/Frameworks"
    ARM64_PYTHON_DYLIB="$ARM64_FW/Python3.framework/Versions/3.9/Python3"
    ARM64_SO_DIR="$ARM64_FW/python3__dot__9/lib-dynload"

    X86_COLLECT_DIR="$DIST_DIR/x86_64/7z快捷压缩"
    X86_PYTHON_DYLIB="$X86_COLLECT_DIR/_internal/Python3.framework/Versions/3.9/Python3"
    X86_SO_DIR="$X86_COLLECT_DIR/_internal/python3.9/lib-dynload"

    if [ -f "$X86_PYTHON_DYLIB" ]; then
        echo "合并 Python3 dylib..."
        lipo -create "$ARM64_PYTHON_DYLIB" "$X86_PYTHON_DYLIB" -output "$ARM64_PYTHON_DYLIB.universal"
        mv "$ARM64_PYTHON_DYLIB.universal" "$ARM64_PYTHON_DYLIB"
    fi

    if [ -d "$X86_SO_DIR" ] && [ -d "$ARM64_SO_DIR" ]; then
        echo "合并 .so 文件..."
        for so in "$ARM64_SO_DIR"/*.so; do
            name=$(basename "$so")
            x86_so="$X86_SO_DIR/$name"
            if [ -f "$x86_so" ]; then
                lipo -create "$so" "$x86_so" -output "$so.universal" 2>/dev/null && \
                    mv "$so.universal" "$so" || true
            fi
        done
        echo ".so 文件合并完成"
    fi

    # ── 更新 .app 内的可执行文件 ──
    cp "$ARM64_COLLECT" "$ARM64_APP/Contents/MacOS/7z快捷压缩"
    chmod +x "$ARM64_APP/Contents/MacOS/7z快捷压缩"

    # 同时更新 Resources 内的 COLLECT 副本
    ARM64_RESOURCES="$ARM64_APP/Contents/Resources"
    if [ -f "$ARM64_RESOURCES/7z快捷压缩" ]; then
        cp "$ARM64_COLLECT" "$ARM64_RESOURCES/7z快捷压缩"
        chmod +x "$ARM64_RESOURCES/7z快捷压缩"
    fi

    # 同时更新 Resources 内的 Python3 副本（如果不是同一个文件）
    if [ -f "$ARM64_RESOURCES/Python3" ] && [ "$ARM64_RESOURCES/Python3" -ef "$ARM64_PYTHON_DYLIB" ]; then
        true  # 同一个文件，已在上一步合并
    elif [ -f "$ARM64_RESOURCES/Python3" ]; then
        cp "$ARM64_PYTHON_DYLIB" "$ARM64_RESOURCES/Python3"
    fi

    # ── 验证关键文件架构 ──
    echo ""
    echo "=== 架构验证 ==="
    echo "Python3 dylib: $(file "$ARM64_PYTHON_DYLIB" 2>/dev/null)"
    first_so=$(ls "$ARM64_SO_DIR"/*.so 2>/dev/null | head -1)
    if [ -n "$first_so" ]; then
        echo "sample .so: $(file "$first_so")"
    fi

    # 移除 arm64 旧产物，用 universal 版本替换
    rm -rf "$DIST_DIR/7z快捷压缩"
    rm -rf "$APP_PATH"
    cp -R "$ARM64_APP" "$APP_PATH"

    echo ""
    echo "universal2 合并完成"
    file "$APP_PATH/Contents/MacOS/7z快捷压缩"

    post_process "$APP_PATH"
    create_dmg "$APP_PATH" "$DMG_PATH" "7z快捷压缩 (Universal)"
fi

# ── 清理临时文件 ──
rm -rf "$DIST_DIR/x86_64" "$DIST_DIR/7z快捷压缩" "$BUILD_DIR/arm64_app" 2>/dev/null || true
rm -f "$PROJECT_DIR/${APP_NAME}.spec"

echo ""
echo "========================================="
echo "  构建完成: $TARGET_ARCH"
echo "  DMG: $DMG_PATH"
echo "  大小: $(du -h "$DMG_PATH" 2>/dev/null | cut -f1)"
echo "========================================="
