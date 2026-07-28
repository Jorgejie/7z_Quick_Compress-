# 7z快捷压缩

macOS 本地文件压缩工具 — 拖拽文件即可压缩，支持 7z/zip 格式、密码加密、分卷压缩。

## 功能

- **拖拽压缩** — 拖拽文件/文件夹到窗口即可添加
- **7z / zip 双格式** — 支持 LZMA2 高压缩率算法
- **密码加密** — 7z 格式支持文件名加密
- **分卷压缩** — 按指定大小切割（如 50m、100m）
- **完全本地** — 所有操作在本地 HTTP 服务完成，不联网

## 安装

从 [最新发布](https://github.com/your/repo/releases) 下载对应架构的 `.dmg`，拖拽到 Applications 即可。

| 架构 | 文件名 | 适用机型 |
|------|--------|---------|
| Apple Silicon | `7z快捷压缩-arm64.dmg` | M1 / M2 / M3 / M4 |
| Intel | `7z快捷压缩-x86_64.dmg` | Intel Mac |

首次打开时，macOS 可能弹出安全提示，右键点击 App → **打开** 即可。

### Intel Mac 用户注意

Intel 版未内嵌 7z 二进制文件，首次使用前请先安装：

```bash
brew install p7zip
```

应用启动时会自动查找 `/usr/local/bin/7z`，无需额外配置。Apple Silicon 版已自带，无需此步骤。

需要 macOS 11.0+。

## 构建

```bash
# 安装依赖
pip3 install pyinstaller
brew install p7zip

# 构建 universal2（同时支持 Apple Silicon + Intel）
cd 7z_tool && bash build_app.sh universal2

# 仅构建 Apple Silicon
bash build_app.sh arm64

# 仅构建 Intel（需在 Apple Silicon 机器上安装 Rosetta 2）
bash build_app.sh x86_64
```

产物在 `7z_tool/dist/`。

## 运行（开发模式）

```bash
python3 7z_tool/launcher.py
```

访问 `http://localhost:8765`。

## 开源协议

本项目代码基于 [MIT](LICENSE) 协议开源。

7z 压缩功能由 [p7zip](https://p7zip.sourceforge.net/)（LGPL）提供，详见 [NOTICE](./NOTICE)。
