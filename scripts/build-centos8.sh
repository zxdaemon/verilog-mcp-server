#!/bin/bash
# CentOS 8.4 一键构建 verilog-mcp-server 可执行文件
# 用法: bash scripts/build-centos8.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== CentOS 8.4 构建 verilog-mcp-server ==="
echo "Python: $(python3 --version)"
echo "glibc: $(ldd --version 2>&1 | head -1)"

# 1. 系统依赖
echo "[1/5] 检查系统依赖..."
yum install -y gcc gcc-c++ make cmake openssl-devel bzip2-devel libffi-devel \
    zlib-devel readline-devel sqlite-devel wget xz-devel tk-devel 2>&1 | tail -3

# 2. 创建 venv
echo "[2/5] 创建 venv..."
python3 -m venv "$PROJECT_DIR/.venv-build"
source "$PROJECT_DIR/.venv-build/bin/activate"
pip install --upgrade pip setuptools wheel -q

# 3. 安装依赖
#    pyslang: 使用预编译 wheel (manylinux_2_28, 兼容 glibc 2.28)
#    tree-sitter-language-pack: 从源码编译 (预编译 wheel 需要 glibc 2.34)
echo "[3/5] 安装依赖..."
cd "$PROJECT_DIR"
pip install --no-binary tree-sitter-language-pack -e . 2>&1 | tail -10
pip install pyinstaller -q

# 验证 glibc 链接
echo "  验证 tree-sitter glibc:"
TSL_SO=$(python3 -c "
import tree_sitter_language_pack, os
d = os.path.dirname(tree_sitter_language_pack.__file__)
print(os.path.join(d, '_native.abi3.so'))
" 2>/dev/null || echo "")
if [ -n "$TSL_SO" ] && [ -f "$TSL_SO" ]; then
    GLIBC_NEED=$(objdump -T "$TSL_SO" 2>/dev/null | grep -oP 'GLIBC_\d+\.\d+(\.\d+)?' | sort -V | tail -1)
    echo "    tree_sitter_language_pack 需要 $GLIBC_NEED"
fi

# 4. PyInstaller 打包
echo "[4/5] PyInstaller 打包..."
pyinstaller --clean verilog-mcp-server.spec 2>&1 | tail -5

# 5. 打包
echo "[5/5] 打包..."
cd "$PROJECT_DIR/dist"
rm -f verilog-mcp-server-linux-x86_64.tar.gz
tar czf verilog-mcp-server-linux-x86_64.tar.gz verilog-mcp-server

SIZE=$(du -sh verilog-mcp-server-linux-x86_64.tar.gz | cut -f1)
echo ""
echo "=== 构建完成 ==="
echo "输出: $PROJECT_DIR/dist/verilog-mcp-server-linux-x86_64.tar.gz ($SIZE)"
