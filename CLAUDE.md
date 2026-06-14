# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概述

Verilog/SystemVerilog RTL 语义分析 MCP 服务器。使用 tree-sitter 解析 HDL 源文件，结合 pyslang（slang 编译器前端）进行语义级 elaboration，通过 MCP 工具暴露模块搜索、信号追踪、层次树构建、FSM 检测、时钟域分析和可视化等功能。

## 命令

```bash
# 安装（可编辑模式）
pip install -e .

# 启动 MCP 服务器（stdio 传输）
verilog-mcp-server

# 启动时构建索引
verilog-mcp-server --build -p /path/to/rtl/project

# 指定 filelist + 顶层模块
verilog-mcp-server --build -f project.f --top soc

# 或通过模块方式启动
python -m verilog_mcp_server --build -p /path/to/rtl/project

# 运行测试
pytest tests/ -v
```

## 架构

```
verilog_mcp_server/
├── __init__.py / __main__.py # 包入口
├── server.py                 # FastMCP 应用 + CLI (--filelist/--top/--version)
├── config.yaml               # 默认配置
│
├── indexer/                  # tree-sitter 解析 + 数据提取
│   ├── builder.py            # 全量/增量索引构建（并行解析支持）
│   ├── project_scanner.py    # 文件发现、.f 文件展开、incdirs/defines 传递
│   ├── verilog_parser.py     # tree-sitter 封装（parse + AST 遍历辅助）
│   ├── module_extractor.py   # module_declaration 提取
│   ├── port_extractor.py     # ANSI + 非 ANSI 端口提取
│   ├── signal_extractor.py   # 信号 + assign + always 块 + testbench 检测
│   ├── instance_extractor.py # 例化（含门级原语 + defparam）
│   ├── type_extractor.py     # struct/enum/typedef
│   ├── package_extractor.py  # package 定义 + import 声明
│   ├── sva_extractor.py      # SVA 断言（immediate/concurrent/property/sequence）
│   ├── macro_extractor.py    # 宏定义 + 条件编译
│   ├── function_task_extractor.py # function/task 提取
│   ├── filelist_parser.py    # .f 文件解析（+incdir+/+define+/+libdir+）
│   ├── pyslang_parser.py     # pyslang 编译 + elaboration
│   └── pyslang_extractor.py  # pyslang 数据提取（generate 展开、resolved 信号）
│
├── database/                 # SQLite + 内存缓存
│   ├── models.py             # 数据类：ModuleDef, PortDef, FunctionDef, SvaDef, PackageDef 等
│   ├── index_store.py        # 索引存储（模块/类型/package/function 查询）
│   ├── sqlite_backend.py     # SQLite CRUD
│   └── errors.py
│
├── analysis/                 # 分析引擎
│   ├── hierarchy.py          # 层次树（优先 pyslang 数据，含 generate 展开）
│   ├── fan_in.py / fan_out.py # 信号扇入/扇出追踪
│   ├── fsm_detector.py       # 状态机检测
│   ├── clock_analyzer.py     # 时钟域分析
│   ├── clock_tree.py         # 时钟域层次映射
│   ├── always_classify.py    # always 块分类
│   ├── cross_ref.py          # 交叉引用
│   ├── dataflow.py           # 端口数据流追踪
│   └── visualizer.py         # 图谱生成（Mermaid + vis.js HTML）
│
├── tools/                    # MCP 工具注册
│   ├── level1_search.py      # Level 1 查询（含 package/function 搜索）
│   ├── level2_relation.py    # Level 2 关联分析
│   ├── level3_analysis.py    # Level 3 智能分析（含 SVA 查询）
│   ├── visualize.py          # 统一可视化
│   └── elab_tools.py         # pyslang elaboration 报告
│
├── templates/visualizer.html # vis.js HTML 模板
└── scripts/                  # 构建脚本
    ├── build-centos8.sh      # CentOS 8.4 PyInstaller 构建
    └── tree_sitter_cache_hook.py # PyInstaller runtime hook
```

## 关键设计决策

- **双引擎解析**：tree-sitter（语法结构）+ pyslang（语义 elaboration、参数求值、generate 展开）
- **层次构建**：优先使用 pyslang elaboration 数据（含 generate 展开），tree-sitter 回退
- **并行解析**：≥10 文件时自动启用 ProcessPoolExecutor
- **SQLite 持久化 + 内存缓存**，启动时自动加载，支持增量构建（mtime+SHA256 变更检测）
- **stdlib 传输**，由 MCP 客户端（Claude Desktop、Claude Code 等）调用
- **三级工具设计**：Level 1 简单查询 → Level 2 跨模块分析 → Level 3 智能检测
- **可视化**：Mermaid（文本内联）+ vis.js（交互式 HTML）
- **Filelist 支持**：`.f` 文件的 `+incdir+`、`+define+` 自动传递给 pyslang 预处理器
- **独立打包**：PyInstaller 构建 CentOS 8.4 兼容可执行文件，自带 glibc parser 缓存
- **数据模型**：dataclass + `to_dict()`/`from_dict()` (JSON) + `to_row()`/`from_row()` (SQLite)
