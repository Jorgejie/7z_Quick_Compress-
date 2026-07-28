#!/bin/bash
# 7z快捷解压 - Finder 右键解压服务
# 由 macOS Automator Quick Action (Run Shell Script) 直接后台调用，
# 接收选中的压缩包路径，解压到同目录的同名文件夹，完成后发系统通知

# 加载用户环境（确保 PATH 包含 Homebrew）
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

set -uo pipefail

# ── 日志 ──
LOG_DIR="$HOME/Library/Logs/7z快捷压缩"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/service.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [解压] $*" >> "$LOG_FILE"
}

notify() {
    osascript -e "display notification \"$2\" with title \"7z快捷解压\" subtitle \"$1\"" 2>/dev/null || true
}

log "=== 解压服务启动 ==="
log "参数: $*"

if [ $# -eq 0 ]; then
    notify "解压失败" "未检测到文件，请在 Finder 中选中压缩包后使用"
    exit 1
fi

# ── 定位 7z ──
find_7z() {
    local script_dir
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    if [ -x "$script_dir/p7zip/7z" ]; then
        echo "$script_dir/p7zip/7z"; return
    fi
    for p in /opt/homebrew/bin/7z /usr/local/bin/7z /usr/bin/7z; do
        [ -x "$p" ] && { echo "$p"; return; }
    done
    command -v 7z 2>/dev/null || echo ""
}

SEVENZIP=$(find_7z)
if [ -z "$SEVENZIP" ]; then
    log "错误: 未找到 7z"
    notify "解压失败" "未找到 7z，请先安装: brew install p7zip"
    exit 1
fi
log "使用 7z: $SEVENZIP"

OK_COUNT=0
FAIL_COUNT=0

for ARCHIVE in "$@"; do
    [ -f "$ARCHIVE" ] || continue

    BASENAME=$(basename "$ARCHIVE")

    # 分卷处理：.002 及之后的分卷跳过（只解 .001，7z 会自动串联）
    if [[ "$BASENAME" =~ \.[0-9]{3}$ ]] && [[ ! "$BASENAME" =~ \.001$ ]]; then
        log "跳过后续分卷: $BASENAME"
        continue
    fi

    # 计算解压目录名：去掉归档后缀
    STEM="$BASENAME"
    STEM="${STEM%.001}"
    for EXT in .tar.gz .tar.bz2 .tar.xz .tgz .tbz2 .txz .7z .zip .rar .tar .gz .bz2 .xz; do
        if [[ "$STEM" == *"$EXT" ]]; then
            STEM="${STEM%$EXT}"
            break
        fi
    done
    [ -z "$STEM" ] && STEM="extracted"

    DEST="$(dirname "$ARCHIVE")/$STEM"
    # 目标被同名文件占用时换名
    if [ -e "$DEST" ] && [ ! -d "$DEST" ]; then
        N=1
        while [ -e "${DEST}_${N}" ] && [ ! -d "${DEST}_${N}" ]; do N=$((N+1)); done
        DEST="${DEST}_${N}"
    fi
    mkdir -p "$DEST"

    log "解压: $ARCHIVE -> $DEST"
    # -p 空密码防止无 tty 时挂起等待输入
    OUTPUT=$("$SEVENZIP" x "$ARCHIVE" -o"$DEST" -y -p 2>&1)
    RC=$?
    if [ $RC -ne 0 ]; then
        log "解压失败 (exit=$RC): $(echo "$OUTPUT" | tail -3)"
        if echo "$OUTPUT" | grep -qi "wrong password\|encrypted"; then
            notify "解压失败" "$BASENAME 已加密，请打开应用输入密码解压"
        else
            notify "解压失败" "$BASENAME（详情见日志）"
        fi
        FAIL_COUNT=$((FAIL_COUNT+1))
        continue
    fi

    # tar.gz 等二次解压：结果目录里只有一个 .tar 时自动再解一次
    INNER_COUNT=$(ls -1 "$DEST" | wc -l | tr -d ' ')
    INNER_FILE=$(ls -1 "$DEST" | head -1)
    if [ "$INNER_COUNT" = "1" ] && [[ "$INNER_FILE" == *.tar ]]; then
        log "二次解压内层 tar: $INNER_FILE"
        if "$SEVENZIP" x "$DEST/$INNER_FILE" -o"$DEST" -y -p >/dev/null 2>&1; then
            rm -f "$DEST/$INNER_FILE"
        fi
    fi

    OK_COUNT=$((OK_COUNT+1))
    LAST_DEST="$DEST"
done

if [ $OK_COUNT -gt 0 ]; then
    notify "解压完成" "成功 ${OK_COUNT} 个$([ $FAIL_COUNT -gt 0 ] && echo "，失败 ${FAIL_COUNT} 个")"
    open -R "$LAST_DEST" 2>/dev/null || true
elif [ $FAIL_COUNT -eq 0 ]; then
    notify "未执行" "选中的不是可解压的文件"
fi

log "=== 解压服务结束: 成功 $OK_COUNT, 失败 $FAIL_COUNT ==="
exit 0
