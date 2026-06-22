#!/bin/bash
# CentOS 8.4 一键构建 verilog-mcp-server 可执行文件
# 用法: bash scripts/build-centos8.sh
# 跳过 yosys: YOSYS_ENABLED=0 bash scripts/build-centos8.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
YOSYS_ENABLED="${YOSYS_ENABLED:-1}"

echo "=== CentOS 8.4 构建 verilog-mcp-server ==="
echo "Python: $(python3 --version)"
echo "glibc: $(ldd --version 2>&1 | head -1)"
echo "Yosys: $([ "$YOSYS_ENABLED" = "1" ] && echo '启用' || echo '跳过')"

# ── 1. 系统依赖 ──
echo "[1/6] 检查系统依赖..."
yum install -y gcc gcc-c++ make cmake openssl-devel bzip2-devel libffi-devel \
    zlib-devel readline-devel sqlite-devel wget xz-devel tk-devel \
    clang bison flex tcl-devel 2>&1 | tail -3

# ── 2. 编译 yosys ──
if [ "$YOSYS_ENABLED" = "1" ]; then
    echo "[2/6] 编译 yosys..."
    YOSYS_VER="0.51"
    YOSYS_SRC="$PROJECT_DIR/build/yosys"
    YOSYS_OUT="$PROJECT_DIR/verilog_mcp_server/eda/bin"

    if [ -x "$YOSYS_OUT/yosys" ]; then
        echo "  yosys 已存在，跳过"
    else
        mkdir -p "$PROJECT_DIR/build" "$YOSYS_OUT"
        if [ ! -d "$YOSYS_SRC" ]; then
            echo "  下载 yosys-${YOSYS_VER}..."
            wget -q "https://github.com/YosysHQ/yosys/archive/refs/tags/yosys-${YOSYS_VER}.tar.gz" \
                -O "$PROJECT_DIR/build/yosys.tar.gz"
            tar xzf "$PROJECT_DIR/build/yosys.tar.gz" -C "$PROJECT_DIR/build"
            mv "$PROJECT_DIR/build/yosys-yosys-${YOSYS_VER}" "$YOSYS_SRC"
        fi
        echo "  编译..."
        make -C "$YOSYS_SRC" config-gcc -j$(nproc) 2>&1 | tail -1
        make -C "$YOSYS_SRC" -j$(nproc) 2>&1 | tail -3
        cp "$YOSYS_SRC/yosys" "$YOSYS_OUT/"
        chmod +x "$YOSYS_OUT/yosys"
        echo "  ✓ yosys 编译完成: $YOSYS_OUT/yosys"
    fi
else
    echo "[2/6] 跳过 yosys 编译"
fi

# ── 3. venv ──
echo "[3/6] 创建 venv..."
python3 -m venv "$PROJECT_DIR/.venv-build"
source "$PROJECT_DIR/.venv-build/bin/activate"
pip install --upgrade pip setuptools wheel -q

# ── 4. 安装依赖 ──
echo "[4/6] 安装依赖..."
cd "$PROJECT_DIR"
pip install --no-binary tree-sitter-language-pack -e . 2>&1 | tail -10
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
