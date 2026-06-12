## Why

PyInstaller 在 Ubuntu 22.04 (glibc 2.35) 上构建的可执行文件无法在 CentOS 8.4 (glibc 2.28) 上运行。`tree-sitter-language-pack` 1.8.1 预编译 wheel 需要 glibc 2.34，与其原生 `.so` 库绑定。通过 LD_LIBRARY_PATH / patchelf 注入 glibc 的方案存在 stack smashing 等兼容性问题。

最简方案：直接在 CentOS 8.4 上构建，从源码编译原生依赖，使所有 `.so` 自然链接到 glibc 2.28。

## What Changes

- 新增 `scripts/build-centos8.sh` — CentOS 8.4 一键构建脚本（Python 3.10 安装 + 依赖编译 + PyInstaller 打包）
- 恢复 `verilog-mcp-server.spec` 为 onefile 模式（无需 glibc 注入）
- 清理之前的 portable 构建产物和脚本（不再需要 wrapper / patchelf）
- 构建产物：`dist/verilog-mcp-server-linux-x86_64.tar.gz`，直接可执行，无需 Python 环境

## Capabilities

### New Capabilities

- `centos8-portable-build`: 在 CentOS 8.4 上原生构建 PyInstaller 可执行文件，兼容 CentOS 8.4+ (glibc 2.28)

### Modified Capabilities

- `pyinstaller-packaging`: 构建环境从 Ubuntu 22.04 改为 CentOS 8.4，消除 glibc 兼容层

## Impact

- 新增: `scripts/build-centos8.sh`
- 修改: `verilog-mcp-server.spec`（恢复 onefile）
- 清理: `scripts/build-portable.sh`、`dist/verilog-mcp-server-portable/`
- 依赖: CentOS 8.4 + Python 3.10 (源码编译) + tree-sitter-language-pack (sdist 编译) + PyInstaller
- 现有代码和 MCP 工具接口不变
