#!/bin/bash
# 7z快捷压缩 - Finder 右键压缩服务
# 由 macOS Automator Quick Action (Run Shell Script) 直接后台调用，
# 接收选中的文件路径，静默执行，完成后发系统通知

# 加载用户环境（确保 PATH 包含 Homebrew）
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bash_profile" ]; then
    source "$HOME/.bash_profile" 2>/dev/null || true
elif [ -f "$HOME/.profile" ]; then
    source "$HOME/.profile" 2>/dev/null || true
fi

# 确保 PATH 包含 Homebrew
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

set -euo pipefail

# ── 日志 ──
LOG_DIR="$HOME/Library/Logs/7z快捷压缩"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/service.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

notify() {
    # 系统通知（无需自动化授权）
    osascript -e "display notification \"$2\" with title \"7z快捷压缩\" subtitle \"$1\"" 2>/dev/null || true
}

log "=== 压缩服务启动 ==="
log "脚本路径: $0"
log "参数数量: $#"
log "参数: $*"
log "PATH: $PATH"
log "用户: $(whoami)"
log "工作目录: $(pwd)"
log "Shell: $SHELL"
log "HOME: $HOME"

# ── 解码 file:// URL 参数 ──
# Automator Quick Action 以 inputMethod=1 传递参数时，
# 参数可能是 file:///path 格式，需要解码为本地路径
decode_path() {
    local p="$1"
    # 去掉 file:// 前缀
    if [[ "$p" == file://* ]]; then
        p="${p#file://}"
    fi
    # 使用 printf 进行 URL 解码 (%XX -> 字符)
    p=$(printf '%b' "$(echo "$p" | sed 's/%\([0-9A-Fa-f][0-9A-Fa-f]\)/\\x\1/g')")
    echo "$p"
}

decoded_args=()
for arg in "$@"; do
    decoded_args+=("$(decode_path "$arg")")
done
set -- "${decoded_args[@]}"

log "解码后参数: $*"

# ── 参数检查 ──
if [ $# -eq 0 ]; then
    log "错误: 未传入文件路径"
    notify "压缩失败" "未检测到文件，请在 Finder 中选中文件后使用"
    exit 1
fi

# ── 定位 7z ──
find_7z() {
    # 1. 脚本同级目录 (开发环境)
    local script_dir
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    if [ -x "$script_dir/p7zip/7z" ]; then
        echo "$script_dir/p7zip/7z"
        return
    fi
    # 2. macOS .app bundle: Contents/Resources/p7zip/7z
    if [ -x "$script_dir/p7zip/7z" ]; then
        echo "$script_dir/p7zip/7z"
        return
    fi
    # 3. 常见 Homebrew 路径
    for p in /opt/homebrew/bin/7z /usr/local/bin/7z /usr/bin/7z; do
        if [ -x "$p" ]; then
            echo "$p"
            return
        fi
    done
    # 4. PATH
    if command -v 7z &>/dev/null; then
        command -v 7z
        return
    fi
    echo ""
}

SEVENZIP=$(find_7z)

if [ -z "$SEVENZIP" ]; then
    log "错误: 未找到 7z"
    notify "压缩失败" "未找到 7z，请先安装: brew install p7zip"
    exit 1
fi

log "使用 7z: $SEVENZIP"

# ── 读取用户配置 ──
CONFIG_FILE="$HOME/Library/Application Support/7z快捷压缩/config.json"
FORMAT="7z"
LEVEL="9"
PASSWORD=""
SPLIT=""

if [ -f "$CONFIG_FILE" ]; then
    log "读取配置: $CONFIG_FILE"
    # 简单解析 JSON（不依赖 jq）
    parse_json_val() {
        local key="$1"
        local val
        val=$(grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$CONFIG_FILE" 2>/dev/null | head -1 | sed "s/\"$key\"[[:space:]]*:[[:space:]]*\"//;s/\"$//")
        echo "$val"
    }
    parse_json_int() {
        local key="$1"
        local val
        val=$(grep -o "\"$key\"[[:space:]]*:[[:space:]]*[0-9]*" "$CONFIG_FILE" 2>/dev/null | head -1 | sed "s/\"$key\"[[:space:]]*:[[:space:]]*//")
        echo "$val"
    }

    fmt_val=$(parse_json_val "format")
    lvl_val=$(parse_json_int "level")
    pwd_val=$(parse_json_val "password")
    split_val=$(parse_json_val "split")

    [ -n "$fmt_val" ] && FORMAT="$fmt_val"
    [ -n "$lvl_val" ] && LEVEL="$lvl_val"
    [ -n "$pwd_val" ] && PASSWORD="$pwd_val"
    [ -n "$split_val" ] && SPLIT="$split_val"
fi

log "配置: format=$FORMAT level=$LEVEL split=$SPLIT pwd=$([ -n "$PASSWORD" ] && echo "已设置" || echo "无")"

# ── 确定输出路径 ──
FIRST_FILE="$1"
FILE_COUNT=$#

if [ "$FILE_COUNT" -eq 1 ]; then
    # 单文件：取文件名（不含扩展名）
    BASENAME=$(basename "$FIRST_FILE")
    STEM="${BASENAME%.*}"
    # 如果没有扩展名（如文件夹），直接用文件名
    [ "$STEM" = "$BASENAME" ] || true
    OUTPUT_NAME="${STEM}.${FORMAT}"
else
    # 多文件：取父目录名
    PARENT_DIR=$(dirname "$FIRST_FILE")
    STEM=$(basename "$PARENT_DIR")
    [ "$STEM" = "/" ] && STEM="archive"
    OUTPUT_NAME="${STEM}.${FORMAT}"
fi

OUTPUT_DIR=$(dirname "$FIRST_FILE")
OUTPUT_PATH="${OUTPUT_DIR}/${OUTPUT_NAME}"

# 避免覆盖已有文件
if [ -f "$OUTPUT_PATH" ]; then
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    STEM="${STEM}_${TIMESTAMP}"
    OUTPUT_NAME="${STEM}.${FORMAT}"
    OUTPUT_PATH="${OUTPUT_DIR}/${OUTPUT_NAME}"
fi

log "输出: $OUTPUT_PATH"

# ── 构建命令 ──
CMD=("$SEVENZIP" "a" "-t$FORMAT" "-mx=$LEVEL")
if [ "$FORMAT" = "7z" ]; then
    CMD+=("-m0=lzma2")
fi
[ -n "$SPLIT" ] && CMD+=("-v$SPLIT")
[ -n "$PASSWORD" ] && CMD+=("-p$PASSWORD")
if [ "$FORMAT" = "7z" ] && [ -n "$PASSWORD" ]; then
    CMD+=("-mhe=on")
fi
CMD+=("$OUTPUT_PATH")
CMD+=("$@")

log "命令: ${CMD[*]}"

# ── 执行压缩 ──
notify "开始压缩" "$OUTPUT_NAME"
T0=$(date +%s)
OUTPUT=$("${CMD[@]}" 2>&1) || {
    RC=$?
    log "压缩失败 (exit=$RC): $OUTPUT"
    SAFE_MSG=$(echo "$OUTPUT" | grep -i error | head -1 | sed 's/"/\\"/g')
    notify "压缩失败" "${SAFE_MSG:-7z 退出码 $RC}"
    exit 1
}

T1=$(date +%s)
DUR=$((T1 - T0))

# ── 计算输出大小 ──
TOTAL_SIZE=0
if [ -f "$OUTPUT_PATH" ]; then
    TOTAL_SIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || echo 0)
    # 分卷文件
    for i in $(seq 1 999); do
        PART=$(printf "%s.%03d" "$OUTPUT_PATH" "$i")
        if [ -f "$PART" ]; then
            PSIZE=$(stat -f%z "$PART" 2>/dev/null || echo 0)
            TOTAL_SIZE=$((TOTAL_SIZE + PSIZE))
        else
            break
        fi
    done
fi

SIZE_MB=$(echo "scale=1; $TOTAL_SIZE / 1048576" | bc 2>/dev/null || echo "?")
log "压缩完成: ${SIZE_MB}MB, ${DUR}s"

# ── 通知用户 ──
notify "压缩完成" "${SIZE_MB} MB · ${DUR}s"

# 在 Finder 中显示结果
open -R "$OUTPUT_PATH" 2>/dev/null || true

log "=== 压缩服务结束 ==="
exit 0
