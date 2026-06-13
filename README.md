# Verilog MCP Server

Verilog/SystemVerilog RTL 语义分析 MCP 服务器。基于 tree-sitter 解析 HDL 源文件，结合 pyslang（slang 编译器前端）进行语义级 elaboration，通过 MCP 协议暴露模块搜索、信号追踪、层次树构建、FSM 检测、时钟域分析和可视化等工具。

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 查看版本
verilog-mcp-server --version

# 启动 MCP 服务器（stdio 传输，由 MCP 客户端调用）
verilog-mcp-server

# 启动时构建索引
verilog-mcp-server --build -p /path/to/rtl/project

# 指定 filelist 文件（自动提取 +incdir+ 和 +define+）
verilog-mcp-server --build -f project.f

# 指定顶层模块
verilog-mcp-server --build -f project.f --top soc

# 强制全量重建
verilog-mcp-server --rebuild -p /path/to/rtl/project
```

### CLI 参数

| 参数 | 说明 |
|------|------|
| `--version` | 显示版本号 |
| `-p, --paths` | 要索引的项目路径（覆盖配置） |
| `-f, --filelist` | 指定 .f 文件列表路径（支持多个） |
| `-t, --top` | 指定顶层模块名 |
| `--build` | 启动时构建索引（增量更新） |
| `--rebuild` | 启动时强制全量重建 |
| `--cache` | 缓存文件路径 |
| `--log-level` | 日志级别 (DEBUG/INFO/WARNING/ERROR) |

### MCP 客户端配置

```json
{
  "mcpServers": {
    "verilog": {
      "command": "verilog-mcp-server",
      "args": ["--build", "-f", "/path/to/project.f", "--top", "soc"]
    }
  }
}
```

### 离线可执行文件

CentOS 8.4 兼容的独立可执行文件（无需 Python 环境）：

```bash
# 在 CentOS 8.4 上构建
bash scripts/build-centos8.sh

# 或使用预构建的 tar.gz
tar xzf verilog-mcp-server-linux-x86_64.tar.gz
./verilog-mcp-server --build -f project.f --top soc
```

## MCP 工具

### Level 1 — 基础查询

| 工具 | 说明 |
|------|------|
| `rtl_search_module` | 模糊搜索模块名 |
| `rtl_get_module` | 获取模块完整定义（端口、信号、参数、例化、always 块、assign、package/import、SVA 断言、testbench 标记） |
| `rtl_module_ports` | 查询模块端口列表（方向/类型/位宽/signed，支持 ANSI 和非 ANSI 风格） |
| `rtl_list_instances` | 列出模块中所有子模块例化 |
| `rtl_search_signal` | 按名称搜索跨模块信号 |
| `rtl_search_package` | 模糊搜索 package 定义（名称、类型、参数） |
| `rtl_search_function` | 模糊搜索 function/task 定义（端口、返回类型） |
| `rtl_hierarchy` | 递归层次树（优先使用 pyslang 数据，含 generate 展开） |

### Level 2 — 关联分析

| 工具 | 说明 |
|------|------|
| `rtl_trace_signal` | 信号跨模块数据流追踪（fan-in 回溯驱动源 / fan-out 追踪负载） |
| `rtl_signal_fan_in` | 信号扇入分析 — 列出所有驱动源 |
| `rtl_signal_fan_out` | 信号扇出分析 — 列出所有负载 |
| `rtl_where_used` | 交叉引用 — 查找模块/信号的例化位置和使用点 |
| `rtl_instance_connections` | 例化端口连接详情 — 形式端口与实际信号映射 |
| `rtl_hierarchy_tree` | 模块层次树（文本格式） |
| `rtl_hierarchy_instances` | 层次实例列表（扁平化所有例化） |

### Level 3 — 智能分析

| 工具 | 说明 |
|------|------|
| `rtl_detect_fsm` | 状态机检测 — 状态编码、转移表、Mealy/Moore 分类 |
| `rtl_clock_domains` | 时钟域分析 — 时钟信号、复位、分频、跨域信号 |
| `rtl_reset_domains` | 复位域分析 — 复位信号来源和同步/异步复位分类 |
| `rtl_always_classify` | always 块分类 — 时序/组合/锁存器判断 |
| `rtl_cross_domain_signals` | 跨时钟域信号检测 — CDC 风险信号识别 |
| `rtl_clock_tree` | 时钟树结构图 — 时钟传播路径和分频层次 |
| `rtl_port_dataflow` | 端口到内部信号的数据流追踪 |
| `rtl_sva_properties` | SVA 断言查询 — property/sequence/assert 列表 |

### Elaboration（pyslang 增强）

| 工具 | 说明 |
|------|------|
| `rtl_elab_report` | pyslang elaboration 报告 — 顶层模块、generate 展开数、resolved 信号数、诊断信息 |
| `rtl_elab_instances` | elaborated 实例列表 — 含 generate 展开后的完整层次路径 |
| `rtl_resolved_signals` | 参数求值后信号列表 — 原始位宽 vs resolved 位宽对比 |

### 可视化

| 工具 | 说明 |
|------|------|
| `rtl_visualize` | 统一可视化入口，支持 4 种图类型 |

**图类型：**

| 类型 | 说明 | 输出 |
|------|------|------|
| `hierarchy` | 模块层次树，双击钻取子模块，面包屑导航 | Mermaid / HTML |
| `fsm` | 状态转移图（椭圆=状态, 边=条件） | Mermaid / HTML |
| `dataflow` | 信号数据流追踪图 | Mermaid / HTML |
| `clock` | 时钟域结构图（按时钟域分组） | Mermaid / HTML |
| `auto` | 自动检测目标类型 | — |

HTML 输出使用 vis.js 交互式网络图，支持缩放/拖拽/点击详情/层次展开。

## 架构

```
verilog_mcp_server/
├── server.py              # FastMCP 应用创建、CLI、stdio 启动
├── config.yaml            # 默认配置
│
├── indexer/               # tree-sitter 解析 + 数据提取
│   ├── builder.py         # 全量/增量索引构建（支持并行解析）
│   ├── project_scanner.py # 文件发现、.f 文件展开（+incdir+/+define+ 传递）
│   ├── verilog_parser.py  # tree-sitter 封装
│   ├── module_extractor.py
│   ├── port_extractor.py  # 端口提取（ANSI + 非 ANSI）
│   ├── signal_extractor.py # 信号 + testbench 检测
│   ├── instance_extractor.py # 例化（含门级原语 + defparam）
│   ├── type_extractor.py
│   ├── package_extractor.py # package 定义 + import 声明
│   ├── sva_extractor.py     # SVA 断言
│   ├── macro_extractor.py   # 宏定义
│   ├── function_task_extractor.py # function/task 提取
│   ├── filelist_parser.py   # .f 文件解析（+incdir+/+define+/+libdir+）
│   ├── pyslang_parser.py    # pyslang 编译 + elaboration
│   └── pyslang_extractor.py # pyslang 数据提取
│
├── database/              # SQLite + 内存缓存
│   ├── models.py          # 数据类：ModuleDef, PortDef, SignalDef, PackageDef,
│   │                      #   FunctionDef, SvaDef, MacroDef, InstanceDef 等
│   ├── index_store.py     # 索引存储（模块/类型/package/function 查询）
│   ├── sqlite_backend.py  # SQLite CRUD
│   └── errors.py
│
├── analysis/              # 分析引擎
│   ├── hierarchy.py       # 模块层次树（优先 pyslang 数据）
│   ├── fan_in.py          # 信号扇入追踪
│   ├── fan_out.py         # 信号扇出追踪
│   ├── fsm_detector.py    # 状态机检测
│   ├── clock_analyzer.py  # 时钟域分析
│   ├── clock_tree.py      # 时钟域层次映射
│   ├── always_classify.py # always 块分类
│   ├── cross_ref.py       # 交叉引用
│   ├── expr_walker.py     # 表达式信号引用提取
│   ├── signal_classifier.py
│   └── visualizer.py      # 图谱生成（Mermaid + vis.js HTML）
│
├── tools/                 # MCP 工具注册
│   ├── level1_search.py   # Level 1 — 查询（含 package/function 搜索）
│   ├── level2_relation.py # Level 2 — 关联分析
│   ├── level3_analysis.py # Level 3 — 智能分析（含 SVA 查询）
│   ├── visualize.py       # 统一可视化
│   └── elab_tools.py      # pyslang elaboration 报告
│
├── templates/
│   └── visualizer.html    # vis.js HTML 模板
│
└── scripts/
    ├── build-centos8.sh             # CentOS 8.4 构建脚本
    └── tree_sitter_cache_hook.py    # PyInstaller runtime hook
```

## 技术栈

- **解析**: tree-sitter + pyslang（slang 编译器前端）
  - tree-sitter：语法级解析，提取源码结构
  - pyslang：语义级 elaboration，generate 展开、参数求值、完整层次树
  - 层次构建优先使用 pyslang 数据，tree-sitter 作为 fallback
- **存储**: SQLite (WAL 模式) + 内存缓存
- **协议**: MCP stdio（由 Claude Desktop / Claude Code 调用）
- **可视化**: Mermaid（文本图）+ vis.js（交互式 HTML）
- **打包**: PyInstaller 独立可执行文件（CentOS 8.4 兼容）
- **并行**: `ProcessPoolExecutor` 多进程解析（≥10 文件自动启用）

## pyslang 集成

pyslang 是 slang（业界公认最完整的开源 SystemVerilog 编译器前端）的官方 Python 绑定。

### 配置

```yaml
pyslang:
  enabled: true
  include_dirs: []       # include 搜索路径（自动合并 .f 文件的 +incdir+）
  defines: {}            # 预定义宏（自动合并 .f 文件的 +define+）
  top_module: ""         # 指定顶层模块
```

### 提供的能力

- **generate 展开实例追踪**：`rtl_elab_instances` 显示 genblk 展开后的完整层次路径
- **参数求值后位宽**：`rtl_get_module` 信号列表显示 resolved 位宽
- **完整层次树**：`rtl_hierarchy` 优先使用 pyslang 数据（含 generate 展开）
- **Elaboration 报告**：`rtl_elab_report` 显示诊断信息

### 降级处理

- pyslang 未安装时：自动跳过，tree-sitter 索引不受影响
- pyslang 解析失败时：记录警告，不阻塞索引构建
- 增量构建：仅当变更涉及 parameter/generate/模块接口时触发 pyslang 重跑

## Filelist 支持

支持标准 EDA `.f` 文件列表格式：

```bash
verilog-mcp-server --build -f project.f
```

`.f` 文件中的 `+incdir+` 和 `+define+` 自动传递给 pyslang 预处理器：

```
# project.f
+incdir+./include
+incdir+./rtl
+define+SIM
+define+BUS_WIDTH=32
./rtl/top.sv
./rtl/cpu.sv
-f sub_module.f
```

## 运行测试

```bash
pytest tests/ -v
```
