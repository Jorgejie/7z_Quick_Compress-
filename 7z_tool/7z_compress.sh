#!/bin/bash
# 7z快捷压缩 - 终端版
# 用法: 7z_compress.sh <file1> [file2] [file3] ...

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志目录
LOG_DIR="$HOME/Library/Logs/7z快捷压缩"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/service.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# 加载用户环境
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bash_profile" ]; then
    source "$HOME/.bash_profile" 2>/dev/null || true
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 参数检查
if [ $# -eq 0 ]; then
    echo -e "${RED}错误: 未指定文件${NC}"
    echo "用法: $0 <file1> [file2] [file3] ..."
    exit 1
fi

# 定位 7z
find_7z() {
    for p in /opt/homebrew/bin/7z /usr/local/bin/7z /usr/bin/7z; do
        if [ -x "$p" ]; then
            echo "$p"
            return
        fi
    done
    if command -v 7z &>/dev/null; then
        command -v 7z
        return
    fi
    echo ""
}

SEVENZIP=$(find_7z)

if [ -z "$SEVENZIP" ]; then
    echo -e "${RED}错误: 未找到 7z${NC}"
    echo "请先安装: brew install p7zip"
    exit 1
fi

echo -e "${GREEN}✓ 找到 7z: $SEVENZIP${NC}"

# 读取配置
CONFIG_FILE="$HOME/Library/Application Support/7z快捷压缩/config.json"
FORMAT="7z"
LEVEL="9"
PASSWORD=""
SPLIT=""

if [ -f "$CONFIG_FILE" ]; then
    # 简单解析 JSON
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

echo -e "${YELLOW}配置: format=$FORMAT level=$LEVEL${NC}"

# 确定输出路径
FIRST_FILE="$1"
FILE_COUNT=$#

if [ "$FILE_COUNT" -eq 1 ]; then
    BASENAME=$(basename "$FIRST_FILE")
    STEM="${BASENAME%.*}"
    [ "$STEM" = "$BASENAME" ] && STEM="$BASENAME"
    OUTPUT_NAME="${STEM}.${FORMAT}"
else
    PARENT_DIR=$(dirname "$FIRST_FILE")
    STEM=$(basename "$PARENT_DIR")
    [ "$STEM" = "/" ] && STEM="archive"
    OUTPUT_NAME="${STEM}.${FORMAT}"
fi

OUTPUT_DIR=$(dirname "$FIRST_FILE")
OUTPUT_PATH="${OUTPUT_DIR}/${OUTPUT_NAME}"

# 避免覆盖
if [ -f "$OUTPUT_PATH" ]; then
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    STEM="${STEM}_${TIMESTAMP}"
    OUTPUT_NAME="${STEM}.${FORMAT}"
    OUTPUT_PATH="${OUTPUT_DIR}/${OUTPUT_NAME}"
fi

echo -e "${GREEN}输出: $OUTPUT_PATH${NC}"
log "开始压缩: $@ -> $OUTPUT_PATH"

# 构建命令
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

echo -e "${YELLOW}执行: ${CMD[*]}${NC}"
echo ""

# 执行压缩
T0=$(date +%s)
OUTPUT=$("${CMD[@]}" 2>&1)
RC=$?
T1=$(date +%s)
DUR=$((T1 - T0))

if [ $RC -eq 0 ]; then
    TOTAL_SIZE=0
    if [ -f "$OUTPUT_PATH" ]; then
        TOTAL_SIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || echo 0)
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

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ 压缩完成!${NC}"
    echo -e "${GREEN}  文件: $OUTPUT_PATH${NC}"
    echo -e "${GREEN}  大小: ${SIZE_MB} MB${NC}"
    echo -e "${GREEN}  耗时: ${DUR}s${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"

    log "压缩成功: ${SIZE_MB}MB, ${DUR}s"

    # 在 Finder 中显示结果
    open -R "$OUTPUT_PATH" 2>/dev/null || true
else
    echo ""
    echo -e "${RED}═══════════════════════════════════════${NC}"
    echo -e "${RED}✗ 压缩失败${NC}"
    echo -e "${RED}$OUTPUT${NC}"
    echo -e "${RED}═══════════════════════════════════════${NC}"

    log "压缩失败: $OUTPUT"
fi

echo ""
read -p "按 Enter 键关闭..."
