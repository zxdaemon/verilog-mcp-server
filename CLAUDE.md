# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概述

Verilog/SystemVerilog RTL 语义分析 MCP 服务器。使用 tree-sitter 解析 HDL 源文件，通过 MCP 工具暴露模块搜索、信号追踪、层次树构建、FSM 检测和时钟域分析等功能。

## 命令

```bash
# 安装（可编辑模式）
pip install -e .

# 启动 MCP 服务器（stdio 传输 — 由 MCP 客户端调用）
verilog-mcp-server

# 启动时构建索引（已有索引时自动增量更新）
verilog-mcp-server --build -p /path/to/rtl/project

# 或通过模块方式启动
python -m verilog_mcp_server --build -p /path/to/rtl/project

# 运行测试（pytest）
pytest tests/ -v
```

## 架构

```
verilog_mcp_server/        # Python 包（pip install 后可独立使用）
├── __init__.py            # 包入口，导出 main/create_app/load_config
├── __main__.py            # python -m verilog_mcp_server 支持
├── server.py              # FastMCP 应用创建、CLI 参数解析、stdio 服务器启动
├── config.yaml            # 默认配置（索引路径、文件扩展名、排除规则、缓存设置）
│
├── indexer/               # 用 tree-sitter 解析 RTL 文件，提取结构化数据
│   ├── builder.py         # 协调索引构建（全量/增量：扫描 → 解析 → 提取 → 存储，支持 mtime+SHA256 变更检测）
│   ├── project_scanner.py # 发现 .v/.sv/.svh 文件，应用排除规则
│   ├── verilog_parser.py  # tree-sitter 封装（parse_file、AST 辅助函数、节点遍历）
│   ├── module_extractor.py# 查找 module_declaration 节点，提取模块名和位置
│   ├── port_extractor.py  # 从 ANSI 端口声明中提取方向/类型/宽度
│   ├── signal_extractor.py# 提取 wire/reg/logic、assign 语句、always 块
│   ├── instance_extractor.py # 提取模块例化及端口连接
│   └── type_extractor.py  # 提取 struct/enum/typedef 定义
│
├── database/              # SQLite 持久化 + 内存缓存
│   ├── models.py          # 数据类：ModuleDef、PortDef、SignalDef、InstanceDef 等
│   ├── index_store.py     # 索引存储（SQLite 后端 + 内存缓存）
│   ├── sqlite_backend.py  # SQLite CRUD 操作
│   └── errors.py          # 领域异常定义
│
├── analysis/              # 供 Level 2 和 Level 3 工具调用的分析引擎
│   ├── hierarchy.py       # 递归模块层次树构建
│   ├── dataflow.py        # 跨模块信号追踪（扇入/扇出）
│   ├── fan_in.py          # 信号 Fan-in 追踪引擎
│   ├── fan_out.py         # 信号 Fan-out 追踪引擎
│   ├── cross_ref.py       # "何处使用"查询、例化端口连接详情
│   ├── expr_walker.py     # 表达式信号引用提取
│   ├── signal_classifier.py # 时钟/复位信号统一识别
│   ├── fsm_detector.py    # 通过 case/next_state 模式检测状态机
│   ├── clock_analyzer.py  # 时钟域分组、复位检测、跨时钟域信号
│   ├── clock_tree.py      # 时钟域结构图构建
│   └── always_classify.py # 分类 always 块（时序/组合/锁存器）
│
└── tools/                 # MCP 工具注册（基于装饰器，绑定到 FastMCP）
    ├── level1_search.py   # rtl_search_module、rtl_get_module、rtl_module_ports 等
    ├── level2_relation.py # rtl_trace_signal、rtl_signal_fan_in/out、rtl_where_used 等
    └── level3_analysis.py # rtl_detect_fsm、rtl_clock_domains、rtl_always_classify 等
```

## 关键设计决策

- **全部使用 tree-sitter-systemverilog 解析**（可在 config.yaml 中配置，但 SV 解析器可同时处理 Verilog 和 SystemVerilog）。不使用基于正则的解析。
- **SQLite 持久化 + 内存缓存**，数据库文件默认 `.verilog_mcp/cache.db`（工作目录下隐藏文件夹）。启动时自动加载，支持增量构建（仅重新解析变更文件）。
- **传输方式为 stdio** — 这是一个 MCP 服务器，而非 HTTP 服务器。由 MCP 客户端（Claude Desktop、Claude Code 等）调用。
- **三级工具设计**：Level 1 = 简单查询（读索引）、Level 2 = 跨模块分析（调用分析引擎）、Level 3 = 智能检测（FSM、时钟域、always 分类）。
- **所有数据模型为 dataclass**，位于 `database/models.py`，配合 `to_dict()`/`from_dict()`（JSON 导出）和 `to_row()`/`from_row()`（SQLite 行存储）实现序列化。
