# AGENTS.md

Agent guidance for the Verilog MCP Server project.

## Project Overview

Verilog/SystemVerilog RTL semantic analysis MCP server. Uses tree-sitter for syntax-level parsing of HDL source files and pyslang (slang compiler frontend) for semantic-level elaboration. Exposes tools via MCP protocol for module search, signal tracing, hierarchy tree construction, FSM detection, clock domain analysis, and visualization.

## Build & Development Commands

```bash
# Install in editable mode
pip install -e .

# Run the MCP server (stdio transport, called by MCP clients)
verilog-mcp-server

# Start with index building
verilog-mcp-server --build -p /path/to/rtl/project

# Specify filelist + top module
verilog-mcp-server --build -f project.f --top soc

# Force full rebuild
verilog-mcp-server --rebuild -p /path/to/rtl/project

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_module_extractor.py -v

# Build standalone executable (CentOS 8.4)
bash scripts/build-centos8.sh
```

## CentOS 8 构建详细指南

### 前提条件

1. **操作系统**: CentOS 8.4 (glibc 2.28)
2. **Python 环境**: miniconda3 Python 3.10+ (推荐 3.12)
3. **依赖包**: tree-sitter-language-pack, pyslang, mcp, pyyaml, pyinstaller
4. **yosys (可选)**: 如果需要 yosys 功能，确保 `yosys` 在 PATH 中

### 构建步骤

#### 1. 环境准备
```bash
# 检查 Python 版本
python3 --version

# 检查 pip
python3 -m pip --version

# 如果使用 miniconda3，确保 Python 环境正常
conda install python=3.12 --force-reinstall
```

#### 2. 运行构建脚本
```bash
# 进入项目目录
cd /wa/project/verilog_mcp_server

# 运行构建脚本
bash scripts/build-centos8.sh

# 如果需要 yosys，确保在 PATH 中
export PATH=$PATH:/path/to/yosys/bin
bash scripts/build-centos8.sh

# 跳过 yosys 构建
YOSYS_ENABLED=0 bash scripts/build-centos8.sh
```

#### 3. 构建产物
构建完成后，产物位于：
```
dist/verilog-mcp-server-linux-x86_64.tar.gz
```

解压后得到单个可执行文件：
```bash
tar -xzf dist/verilog-mcp-server-linux-x86_64.tar.gz
./verilog-mcp-server --version
```

### 常见问题解决

#### 1. Python 环境问题
**问题**: `ImportError: undefined symbol: XML_SetReparseDeferralEnabled`
**解决**:
```bash
# 重新安装 Python
conda install python=3.12 --force-reinstall

# 或者创建新的 conda 环境
conda create -n build python=3.10
conda activate build
```

#### 2. pip 权限问题
**问题**: `Permission denied: '/usr/local/lib/python3.6'`
**解决**:
```bash
# 使用 --user 标志
pip install --user <package>

# 或者使用 miniconda3 环境
conda install pip
```

#### 3. PyInstaller 找不到
**问题**: `No module named pyinstaller`
**解决**:
```bash
# 直接安装 pyinstaller
pip install pyinstaller

# 使用 pyinstaller 命令而不是 python -m pyinstaller
pyinstaller --clean verilog-mcp-server.spec
```

#### 4. yosys 未包含
**问题**: 构建的可执行文件不包含 yosys 功能
**解决**:
```bash
# 确保 yosys 在 PATH 中
which yosys

# 或者指定 yosys 路径
export YOSYS_PATH=/path/to/yosys
bash scripts/build-centos8.sh
```

### 构建脚本说明

构建脚本 `scripts/build-centos8.sh` 执行以下步骤：

1. **检查系统依赖** (跳过)
2. **准备 yosys** (检测 PATH 中的 yosys)
3. **跳过 venv** (使用系统 Python)
4. **安装依赖** (tree-sitter-language-pack, pyslang, mcp, pyinstaller)
5. **PyInstaller 打包** (生成单个可执行文件)
6. **打包** (创建 tar.gz 压缩包)

### 构建产物特性

- **单个可执行文件**: 包含 Python 解释器和所有依赖
- **跨平台兼容**: 仅限 CentOS 8.4 (glibc 2.28)
- **文件大小**: 约 70-80MB
- **无外部依赖**: 可在无 Python 环境的 CentOS 8 上运行

## Architecture

```
verilog_mcp_server/
├── server.py                 # FastMCP app + CLI (--filelist/--top/--version)
├── config.yaml               # Default configuration
│
├── indexer/                  # tree-sitter parsing + data extraction
│   ├── builder.py            # Full/incremental index build (parallel parsing)
│   ├── project_scanner.py    # File discovery, .f file expansion, incdirs/defines
│   ├── verilog_parser.py     # tree-sitter wrapper (parse + AST traversal)
│   ├── module_extractor.py   # module_declaration extraction
│   ├── port_extractor.py     # ANSI + non-ANSI port extraction
│   ├── signal_extractor.py   # Signals + assign + always blocks + testbench detection
│   ├── instance_extractor.py # Instantiation (gate primitives + defparam)
│   ├── type_extractor.py     # struct/enum/typedef
│   ├── package_extractor.py  # Package definitions + import declarations
│   ├── sva_extractor.py      # SVA assertions (immediate/concurrent/property/sequence)
│   ├── macro_extractor.py    # Macro definitions + conditional compilation
│   ├── function_task_extractor.py # function/task extraction
│   ├── filelist_parser.py    # .f file parsing (+incdir+/+define+/+libdir+)
│   ├── pyslang_parser.py     # pyslang compilation + elaboration
│   └── pyslang_extractor.py  # pyslang data extraction (generate expansion, resolved signals)
│
├── database/                 # SQLite + in-memory cache
│   ├── models.py             # Dataclasses: ModuleDef, PortDef, FunctionDef, SvaDef, PackageDef, etc.
│   ├── index_store.py        # Index storage (module/type/package/function queries)
│   ├── sqlite_backend.py     # SQLite CRUD
│   └── errors.py
│
├── analysis/                 # Analysis engines
│   ├── hierarchy.py          # Hierarchy tree (prefers pyslang data, with generate expansion)
│   ├── fan_in.py / fan_out.py # Signal fan-in/fan-out tracing
│   ├── fsm_detector.py       # FSM detection
│   ├── clock_analyzer.py     # Clock domain analysis
│   ├── clock_tree.py         # Clock domain hierarchy mapping
│   ├── always_classify.py    # Always block classification
│   ├── cross_ref.py          # Cross-references
│   ├── dataflow.py           # Port dataflow tracing
│   └── visualizer.py         # Graph generation (Mermaid + vis.js HTML)
│
├── tools/                    # MCP tool registration
│   ├── level1_search.py      # Level 1 queries (package/function search)
│   ├── level2_relation.py    # Level 2 cross-module analysis
│   ├── level3_analysis.py    # Level 3 intelligent detection (SVA queries)
│   ├── visualize.py          # Unified visualization
│   └── elab_tools.py         # pyslang elaboration reports
│
├── templates/visualizer.html # vis.js HTML template
└── scripts/                  # Build scripts
    ├── build-centos8.sh      # CentOS 8.4 PyInstaller build
    └── tree_sitter_cache_hook.py # PyInstaller runtime hook
```

## Key Design Decisions

- **Dual-engine parsing**: tree-sitter (syntax structure) + pyslang (semantic elaboration, parameter evaluation, generate expansion)
- **Hierarchy building**: Prefers pyslang elaboration data (with generate expansion), tree-sitter as fallback
- **Parallel parsing**: Auto-enables ProcessPoolExecutor for ≥10 files
- **SQLite persistence + in-memory cache**: Auto-loads at startup, supports incremental builds (mtime+SHA256 change detection)
- **stdio transport**: Called by MCP clients (Claude Desktop, Claude Code, etc.)
- **Three-level tool design**: Level 1 simple queries → Level 2 cross-module analysis → Level 3 intelligent detection
- **Visualization**: Mermaid (text inline) + vis.js (interactive HTML)
- **Filelist support**: `.f` files' `+incdir+` and `+define+` auto-passed to pyslang preprocessor
- **Standalone packaging**: PyInstaller builds CentOS 8.4 compatible executables with bundled glibc parser cache

## Code Conventions

### Language & Style
- Python 3.10+ with type hints
- Chinese comments and docstrings (project targets Chinese-speaking RTL engineers)
- English for code identifiers (functions, classes, variables)
- `from __future__ import annotations` in all modules

### Data Models
- Use `@dataclass` with `SerializableModel` base class from `database/models.py`
- All models implement `to_dict()`/`from_dict()` (JSON) and `to_row()`/`from_row()` (SQLite)
- Nested structures are serialized as JSON strings in SQLite

### Naming Patterns
- Files: `snake_case.py`
- Classes: `PascalCase` (e.g., `ModuleDef`, `PortExtractor`, `IndexBuilder`)
- Functions/methods: `snake_case` (e.g., `extract_modules`, `build_index`)
- MCP tools: `rtl_` prefix (e.g., `rtl_search_module`, `rtl_hierarchy`)
- Test files: `test_<module_name>.py`

### Testing Patterns
- Tests in `tests/` directory
- pytest with `conftest.py` for fixtures
- Test Verilog files inline or in test directory (e.g., `test_fsm.v`)
- Each extractor has corresponding test file (e.g., `test_module_extractor.py`)
- Integration tests for MCP tools (e.g., `test_level1_tools.py`)

### Error Handling
- Custom exceptions in `database/errors.py`
- pyslang failures degrade gracefully (skip, log warning, don't block indexing)
- pyslang not installed → auto-skip, tree-sitter index unaffected

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | ≥1.0.0 | MCP protocol server (FastMCP) |
| `tree-sitter-language-pack` | ≥0.12.0 | Verilog/SystemVerilog grammar parsing |
| `pyslang` | ≥11.0.0,<12.0.0 | slang compiler frontend for semantic elaboration |
| `pyyaml` | ≥6.0 | YAML configuration loading |

### Optional Dependencies
- `pyslang`: Can be absent; enables semantic elaboration, generate expansion, resolved signal widths
- `PyInstaller`: For standalone executable packaging only

## MCP Tool Levels

| Level | Purpose | Examples |
|-------|---------|----------|
| 1 - Search | Simple queries | `rtl_search_module`, `rtl_get_module`, `rtl_module_ports`, `rtl_search_signal`, `rtl_search_package`, `rtl_search_function`, `rtl_hierarchy` |
| 2 - Relation | Cross-module analysis | `rtl_trace_signal`, `rtl_signal_fan_in`, `rtl_signal_fan_out`, `rtl_where_used`, `rtl_instance_connections` |
| 3 - Analysis | Intelligent detection | `rtl_detect_fsm`, `rtl_clock_domains`, `rtl_reset_domains`, `rtl_always_classify`, `rtl_cross_domain_signals`, `rtl_sva_properties` |
| Visualization | Graph generation | `rtl_visualize` (hierarchy/fsm/dataflow/clock → Mermaid or vis.js HTML) |
| Elaboration | pyslang reports | `rtl_elab_report`, `rtl_elab_instances`, `rtl_resolved_signals` |

## Configuration

Default config in `verilog_mcp_server/config.yaml`. Key sections:

```yaml
server:
  name: verilog-analyzer
  log_level: INFO

index:
  paths: []                    # Project paths to index
  extensions: [".v", ".sv", ".svh"]
  exclude_dirs: [node_modules, .git, build, ...]
  language_map: {".v": "verilog", ".sv": "systemverilog", ".svh": "systemverilog"}

pyslang:
  enabled: true
  include_dirs: []             # Auto-merged from .f files
  defines: {}                  # Auto-merged from .f files
  top_module: ""

cache:
  path: ".verilog_mcp/cache.db"
  auto_load: true
  auto_save: true
```

## CentOS 8 打包环境 (Build Host)

- IP: `192.168.50.21`
- Account: `weijj`
- Password: `wjj12345`
- Remote project path: `/wa/project/verilog_mcp_server`

## Working with This Codebase

0. **查看和解析代码时优先使用 CodeGraph**: 需要阅读源码、理解函数调用关系、搜索符号定义时，优先使用 CodeGraph 工具（`codegraph_explore`、`codegraph_node`、`codegraph_search`、`codegraph_callers`），而非手动 `read`/`grep`/`find`。CodeGraph 能提供带行号的源码、调用链路和依赖关系，效率更高。仅在 CodeGraph 不可用或需要读取非代码文件（如 config.yaml、.f 文件）时才回退到 `read` 工具。

1. **Adding a new extractor**: Create `indexer/<name>_extractor.py`, add data model to `database/models.py`, register in `indexer/builder.py`, write tests in `tests/test_<name>_extractor.py`

2. **Adding a new MCP tool**: Add to appropriate level file in `tools/` (level1/2/3), register with `@mcp.tool()` decorator, prefix with `rtl_`

3. **Adding a new analysis**: Create `analysis/<name>.py`, expose via `tools/level3_analysis.py`, write tests

4. **Modifying data models**: Update `SerializableModel` subclass, ensure `to_dict()`/`from_dict()`/`to_row()`/`from_row()` still work, update SQLite schema in `sqlite_backend.py` if needed
