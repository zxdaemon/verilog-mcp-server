#!/bin/bash
# CentOS 8.4 一键构建 verilog-mcp-server 可执行文件
# 用法: bash scripts/build-centos8.sh
# 跳过 yosys: YOSYS_ENABLED=0 bash scripts/build-centos8.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
YOSYS_ENABLED="${YOSYS_ENABLED:-1}"

# 检测 yosys 可用性
if [ "$YOSYS_ENABLED" = "1" ]; then
    if ! which yosys >/dev/null 2>&1; then
        echo "⚠ 警告: 未在 PATH 中找到 yosys，将禁用 yosys 功能"
        YOSYS_ENABLED=0
    fi
fi

echo "=== CentOS 8.4 构建 verilog-mcp-server ==="
echo "Python: $(python3 --version)"
echo "glibc: $(ldd --version 2>&1 | head -1)"
echo "Yosys: $([ "$YOSYS_ENABLED" = "1" ] && echo '启用' || echo '跳过')"

# ── 1. 系统依赖 ──
echo "[1/6] 检查系统依赖..."
#yum install -y gcc gcc-c++ make cmake openssl-devel bzip2-devel libffi-devel \
#    zlib-devel readline-devel sqlite-devel wget xz-devel tk-devel \
#    clang bison flex tcl-devel 2>&1 | tail -3

# ── 2. 准备 yosys ──
if [ "$YOSYS_ENABLED" = "1" ]; then
    echo "[2/6] 准备 yosys..."
    YOSYS_OUT="$PROJECT_DIR/verilog_mcp_server/eda/bin"
    mkdir -p "$YOSYS_OUT"

    # 只使用 which yosys 检测
    YOSYS_BIN=$(which yosys 2>/dev/null) || true
    
    if [ -x "$YOSYS_OUT/yosys" ]; then
        echo "  yosys 已存在，跳过"
    elif [ -n "$YOSYS_BIN" ] && [ -x "$YOSYS_BIN" ]; then
        echo "  使用 PATH 中的 yosys: $YOSYS_BIN"
        cp "$YOSYS_BIN" "$YOSYS_OUT/yosys"
        chmod +x "$YOSYS_OUT/yosys"
        echo "  ✓ yosys 已复制到: $YOSYS_OUT/yosys"
    else
        echo "  ⚠ 未在 PATH 中找到 yosys，禁用 yosys 功能"
        YOSYS_ENABLED=0
    fi
else
    echo "[2/6] 跳过 yosys"
fi

# ── 3. venv ──
echo "[3/6] 跳过 venv，使用系统 Python..."
pip install --upgrade pip setuptools wheel -q

# ── 4. 安装依赖 ──
echo "[4/6] 安装依赖..."
cd "$PROJECT_DIR"
pip install --user --no-binary tree-sitter-language-pack -e . 2>&1 | tail -10
pip install pyinstaller -q

# ── 5. PyInstaller 打包 ──
echo "[5/6] PyInstaller 打包..."
pyinstaller --clean verilog-mcp-server.spec 2>&1 | tail -5

# ── 6. 打包 ──
echo "[6/6] 打包..."
cd "$PROJECT_DIR/dist"
rm -f verilog-mcp-server-linux-x86_64.tar.gz
tar czf verilog-mcp-server-linux-x86_64.tar.gz verilog-mcp-server

SIZE=$(du -sh verilog-mcp-server-linux-x86_64.tar.gz | cut -f1)
echo ""
echo "=== 构建完成 ==="
echo "输出: $PROJECT_DIR/dist/verilog-mcp-server-linux-x86_64.tar.gz ($SIZE)"
