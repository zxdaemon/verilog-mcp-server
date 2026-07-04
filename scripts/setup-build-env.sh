#!/bin/bash
# ─────────────────────────────────────────────────────────────
# 构建环境初始化脚本 (仅需运行一次)
# 创建 conda 环境并安装 yosys 编译依赖
# 用法: bash scripts/setup-build-env.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ENV_NAME="${CONDA_ENV_NAME:-yosys-build}"
PYTHON_VER="${PYTHON_VER:-3.12}"

echo "=== 初始化构建环境: $ENV_NAME ==="

# 检查 conda
if ! which conda >/dev/null 2>&1; then
    echo "❌ conda 未安装，请先安装 miniconda3"
    exit 1
fi

# 创建 conda 环境（已存在则跳过）
if conda env list | grep -q "^$ENV_NAME "; then
    echo "✓ conda 环境 '$ENV_NAME' 已存在"
else
    echo "创建 conda 环境: $ENV_NAME (Python $PYTHON_VER)..."
    conda create -n "$ENV_NAME" python="$PYTHON_VER" -y 2>&1 | tail -5
fi

# 安装编译依赖
echo "安装编译依赖 (boost, bison, flex, pip)..."
source activate "$ENV_NAME"
conda install -y boost boost-cpp bison flex pip -c conda-forge 2>&1 | tail -5

echo ""
echo "=== 构建环境初始化完成 ==="
echo "激活环境: conda activate $ENV_NAME"
