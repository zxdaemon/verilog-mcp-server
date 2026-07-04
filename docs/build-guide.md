# CentOS 8.4 构建指南

## 构建环境

| 项目 | 值 |
|---|---|
| 操作系统 | CentOS 8.4 (glibc 2.28) |
| 构建机 IP | 192.168.50.21 |
| conda 环境名 | `yosys-build` |
| Python 版本 | 3.12 |
| yosys 源码 | `/wa/project/yosys` |
| 项目路径 | `/wa/project/verilog_mcp_server` |

## 构建步骤

### 1. 初始化构建环境 (仅首次)

```bash
bash scripts/setup-build-env.sh
```

这会创建 conda 环境 `yosys-build`，安装 boost、bison、flex 等编译依赖。

### 2. 准备 yosys 源码 (仅首次)

yosys 源码在 `/wa/project/yosys`，需要确保 abc 子模块就绪：

```bash
# 检查 abc 子模块
ls /wa/project/yosys/abc/Makefile

# 如果缺失，从 GitHub 下载 abc (commit e55d316)
# https://github.com/YosysHQ/abc/tree/e55d316
# 下载 ZIP 解压到 /wa/project/yosys/abc/
```

### 3. 执行构建

```bash
conda activate yosys-build
bash scripts/build-centos8.sh
```

构建产物: `dist/verilog-mcp-server-linux-x86_64.tar.gz`

### 4. 跳过 yosys 构建

```bash
YOSYS_ENABLED=0 bash scripts/build-centos8.sh
```

## pyosys 编译要点

pyosys 是 yosys 的 Python 绑定，编译时需要特殊配置：

### Makefile.conf

```makefile
ENABLE_ABC := 0        # 不编译 ABC（需要子模块）
ENABLE_PYOSYS := 1     # 启用 Python 绑定
ENABLE_LIBYOSYS := 1   # 启用共享库
```

### 编译命令

```bash
source activate yosys-build
cd /wa/project/yosys

# 环境变量
export BOOST_PYTHON_LIB="-lboost_python312 -lpython3.12"
export CPPFLAGS="-I$CONDA_PREFIX/include"

# 编译
make -j$(nproc) libyosys.so share

# strip 调试符号 (~670MB → ~22MB)
strip -S libyosys.so
```

### 手动安装 pyosys

`pip wheel` 构建有兼容性问题，使用手动安装：

```bash
PYOSYS_DIR=$(python3 -c 'import site; print(site.getsitepackages()[0])')/pyosys
mkdir -p $PYOSYS_DIR
cp misc/__init__.py $PYOSYS_DIR/
cp libyosys.so $PYOSYS_DIR/
cp -r share $PYOSYS_DIR/

# 验证
python3 -c "from pyosys import libyosys as ys; d = ys.Design(); print('OK')"
```

## 依赖关系

### conda 依赖 (编译用)

| 包 | 用途 |
|---|---|
| boost | Boost.Python 库 |
| boost-cpp | Boost C++ 头文件 |
| bison | yosys Verilog 解析器生成 |
| flex | yosys Verilog 词法分析器生成 |
| pip | Python 包管理 |

### Python 依赖 (运行用)

| 包 | 用途 |
|---|---|
| mcp | MCP 协议服务 |
| tree-sitter-language-pack | Verilog/SystemVerilog 语法解析 |
| pyslang | slang 编译器前端 |
| pyyaml | 配置文件加载 |
| pyinstaller | 可执行文件打包 |

## 常见问题

### Q: BOOST_PYTHON_LIB 检测失败

yosys Makefile 的自动检测不兼容 conda 环境，需要手动指定：

```bash
BOOST_PYTHON_LIB="-lboost_python312 -lpython3.12"
```

### Q: abc 子模块缺失

构建机无法访问 GitHub，需要手动下载：

1. 访问 https://github.com/YosysHQ/abc/tree/e55d316
2. Code → Download ZIP
3. 解压到 `/wa/project/yosys/abc/`

### Q: PyInstaller 打包缺少 typer

mcp 包的 CLI 模块依赖 typer：

```bash
pip install typer
```

### Q: libyosys.so 体积过大

未 strip 的库约 670MB，strip 后约 22MB：

```bash
strip -S libyosys.so
```
