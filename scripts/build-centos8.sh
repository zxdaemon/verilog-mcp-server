#!/bin/bash
# CentOS 8.4 一键构建 verilog-mcp-server 可执行文件
# 用法: bash scripts/build-centos8.sh
# 跳过 yosys: YOSYS_ENABLED=0 bash scripts/build-centos8.sh
# 指定 yosys 源码路径: YOSYS_SRC=/path/to/yosys bash scripts/build-centos8.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
YOSYS_ENABLED="${YOSYS_ENABLED:-1}"
YOSYS_SRC="${YOSYS_SRC:-/wa/project/yosys}"

# 检测 yosys 源码路径和编译工具链
if [ "$YOSYS_ENABLED" = "1" ]; then
    if [ ! -d "$YOSYS_SRC" ]; then
        echo "⚠ 警告: yosys 源码目录不存在: $YOSYS_SRC，将禁用 yosys 功能"
        YOSYS_ENABLED=0
    fi
fi

if [ "$YOSYS_ENABLED" = "1" ]; then
    _MISSING_TOOLS=""
    for _tool in gcc make bison flex; do
        if ! which "$_tool" >/dev/null 2>&1; then
            _MISSING_TOOLS="$_MISSING_TOOLS $_tool"
        fi
    done
    if [ -n "$_MISSING_TOOLS" ]; then
        echo "⚠ 警告: 缺少 yosys 编译工具:$_MISSING_TOOLS"
        echo "  安装建议: sudo yum install -y gcc make bison flex"
        echo "  将禁用 yosys 功能"
        YOSYS_ENABLED=0
    fi
fi

echo "=== CentOS 8.4 构建 verilog-mcp-server ==="
echo "Python: $(python3 --version)"
echo "glibc: $(ldd --version 2>&1 | head -1)"
echo "Yosys: $([ "$YOSYS_ENABLED" = "1" ] && echo '启用 (pyosys)' || echo '跳过')"

# ── 1. 系统依赖 ──
echo "[1/6] 检查系统依赖..."
#yum install -y gcc gcc-c++ make cmake openssl-devel bzip2-devel libffi-devel \
#    zlib-devel readline-devel sqlite-devel wget xz-devel tk-devel \
#    clang bison flex tcl-devel 2>&1 | tail -3

# ── 2. 编译 pyosys ──
if [ "$YOSYS_ENABLED" = "1" ]; then
    echo "[2/6] 从源码编译 pyosys..."
    cd "$YOSYS_SRC"

    # 检查是否已安装 pyosys
    if python3 -c "import pyosys" 2>/dev/null; then
        echo "  pyosys 已安装，跳过编译"
    else
        echo "  编译 pyosys (ENABLE_PYOSYS=1)..."
        ENABLE_PYOSYS=1 pip wheel . --no-deps -w "$PROJECT_DIR/dist/" 2>&1 | tail -10
        # 安装编译出的 wheel
        WHEEL=$(ls -t "$PROJECT_DIR"/dist/pyosys-*.whl 2>/dev/null | head -1)
        if [ -n "$WHEEL" ]; then
            pip install "$WHEEL" --force-reinstall 2>&1 | tail -5
            echo "  ✓ pyosys 已安装: $WHEEL"
        else
            echo "  ⚠ pyosys wheel 编译失败，禁用 yosys 功能"
            YOSYS_ENABLED=0
        fi
    fi
else
    echo "[2/6] 跳过 pyosys 编译"
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
