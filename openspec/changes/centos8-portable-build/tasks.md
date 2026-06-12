## 1. 构建脚本

- [x] 1.1 编写 `scripts/build-centos8.sh` — CentOS 8.4 一键构建脚本
- [x] 1.2 脚本内创建 venv，pip 安装依赖（`--no-binary tree-sitter-language-pack` 强制源码编译）
- [x] 1.3 pyslang 使用预编译 wheel（manylinux_2_28，兼容 glibc 2.28）
- [x] 1.4 运行 PyInstaller 打包
- [x] 1.5 打包 `dist/verilog-mcp-server` 为 tar.gz

## 2. Spec 文件

- [x] 2.1 `verilog-mcp-server.spec` 保持 onefile 模式

## 3. 远程构建验证

- [x] 3.1 SSH 到 CentOS 8.4 (192.168.50.131)，运行构建脚本 — 构建成功
- [x] 3.2 验证可执行文件 glibc 依赖: bootloader GLIBC_2.14, tree-sitter GLIBC_2.28
- [x] 3.3 下载 tar.gz 回构建机器 (40MB)

## 4. 清理

- [ ] 4.1 删除 `scripts/build-portable.sh`
- [ ] 4.2 删除 `dist/verilog-mcp-server-portable/`
