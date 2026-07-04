#!/bin/bash
# ─────────────────────────────────────────────────────────────
# CentOS 8.4 一键构建 verilog-mcp-server 可执行文件
#
# 前提条件:
#   1. 已运行 scripts/setup-build-env.sh 创建 conda 环境
#   2. yosys 源码已就绪 (abc 子模块已下载)
#
# 用法:
#   bash scripts/build-centos8.sh                    # 完整构建
#   YOSYS_ENABLED=0 bash scripts/build-centos8.sh    # 跳过 yosys
#   YOSYS_SRC=/path/to/yosys bash scripts/build-centos8.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
YOSYS_ENABLED="${YOSYS_ENABLED:-1}"
YOSYS_SRC="${YOSYS_SRC:-/wa/project/yosys}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-yosys-build}"

# ── 前置检查 ──

# 检查 conda 环境
if ! conda env list 2>/dev/null | grep -q "^$CONDA_ENV_NAME "; then
    echo "⚠ conda 环境 '$CONDA_ENV_NAME' 不存在"
    echo "  请先运行: bash scripts/setup-build-env.sh"
    exit 1
fi

# 检查 yosys 源码
if [ "$YOSYS_ENABLED" = "1" ]; then
    if [ ! -d "$YOSYS_SRC" ]; then
        echo "⚠ yosys 源码目录不存在: $YOSYS_SRC，禁用 yosys"
        YOSYS_ENABLED=0
    elif [ ! -f "$YOSYS_SRC/abc/Makefile" ]; then
        echo "⚠ yosys abc 子模块未初始化"
        echo "  请下载 abc: https://github.com/YosysHQ/abc/tree/e55d316"
        echo "  解压到: $YOSYS_SRC/abc/"
        YOSYS_ENABLED=0
    fi
fi

# 激活 conda 环境
source activate "$CONDA_ENV_NAME"

echo "=== CentOS 8.4 构建 verilog-mcp-server ==="
echo "Python: $(python3 --version)"
echo "glibc: $(ldd --version 2>&1 | head -1)"
echo "Conda env: $CONDA_ENV_NAME"
echo "Yosys: $([ "$YOSYS_ENABLED" = "1" ] && echo '启用 (pyosys)' || echo '跳过')"

# ── 1. 编译 pyosys ──
if [ "$YOSYS_ENABLED" = "1" ]; then
    echo "[1/5] 编译 pyosys..."

    # 检查是否已安装
    if python3 -c "import pyosys" 2>/dev/null; then
        echo "  pyosys 已安装，跳过编译"
    else
        cd "$YOSYS_SRC"

        # 配置 Makefile.conf
        echo "  配置 Makefile.conf..."
        cat > Makefile.conf <<'EOF'
ENABLE_ABC := 0
ENABLE_PYOSYS := 1
ENABLE_LIBYOSYS := 1
EOF

        # 下载 cxxopts 头文件（如果缺失）
        if [ ! -f libs/cxxopts/include/cxxopts.hpp ]; then
            echo "  下载 cxxopts 头文件..."
            mkdir -p libs/cxxopts/include
            curl -sL "https://raw.githubusercontent.com/jarro2783/cxxopts/v3.1.1/include/cxxopts.hpp" \
                -o libs/cxxopts/include/cxxopts.hpp
        fi

        # 清理旧产物
        rm -f libyosys.so kernel/python_wrappers.cc kernel/python_wrappers.o

        # 编译 libyosys.so
        echo "  编译 libyosys.so (这可能需要几分钟)..."
        BOOST_PYTHON_LIB="-lboost_python312 -lpython3.12" \
        CPPFLAGS="-I$CONDA_PREFIX/include" \
        make -j"$(nproc)" libyosys.so share 2>&1 | tail -5

        if [ ! -f libyosys.so ]; then
            echo "  ❌ libyosys.so 编译失败，禁用 yosys"
            YOSYS_ENABLED=0
        else
            # strip 调试符号
            strip -S libyosys.so
            echo "  ✓ libyosys.so 编译成功 ($(du -h libyosys.so | cut -f1))"

            # 手动安装 pyosys（pip wheel 有兼容性问题）
            echo "  安装 pyosys..."
            PYOSYS_DIR="$(python3 -c 'import site; print(site.getsitepackages()[0])')/pyosys"
            mkdir -p "$PYOSYS_DIR"
            cp misc/__init__.py "$PYOSYS_DIR/"
            cp libyosys.so "$PYOSYS_DIR/"
            cp -r share "$PYOSYS_DIR/" 2>/dev/null || true

            # 验证
            if python3 -c "from pyosys import libyosys as ys; ys.Design()" 2>/dev/null; then
                echo "  ✓ pyosys 安装成功"
            else
                echo "  ❌ pyosys 验证失败，禁用 yosys"
                YOSYS_ENABLED=0
            fi
        fi
    fi
else
    echo "[1/5] 跳过 pyosys 编译"
fi

# ── 2. 安装项目依赖 ──
echo "[2/5] 安装项目依赖..."
cd "$PROJECT_DIR"
pip install --upgrade pip setuptools wheel -q
pip install --no-binary tree-sitter-language-pack -e . 2>&1 | tail -5
pip install pyinstaller typer -q

# ── 3. PyInstaller 打包 ──
echo "[3/5] PyInstaller 打包..."
pyinstaller --clean verilog-mcp-server.spec 2>&1 | tail -5

# ── 4. 打包 ──
echo "[4/5] 打包..."
cd "$PROJECT_DIR/dist"
rm -f verilog-mcp-server-linux-x86_64.tar.gz
tar czf verilog-mcp-server-linux-x86_64.tar.gz verilog-mcp-server

# ── 5. 验证 ──
echo "[5/5] 验证..."
cd "$PROJECT_DIR"
if ./dist/verilog-mcp-server --version >/dev/null 2>&1; then
    echo "  ✓ verilog-mcp-server --version: $(./dist/verilog-mcp-server --version)"
else
    echo "  ❌ verilog-mcp-server 启动失败"
fi

SIZE=$(du -sh dist/verilog-mcp-server-linux-x86_64.tar.gz | cut -f1)
echo ""
echo "=== 构建完成 ==="
echo "输出: $PROJECT_DIR/dist/verilog-mcp-server-linux-x86_64.tar.gz ($SIZE)"
echo "Yosys: $([ "$YOSYS_ENABLED" = "1" ] && echo '已集成 (pyosys)' || echo '未集成')"
