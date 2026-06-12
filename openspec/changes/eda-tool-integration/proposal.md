## Why

当前 Verilog MCP Server 基于 tree-sitter 纯语法分析，无法处理预处理（宏展开、参数求值、generate 展开），导致时钟树分析、CDC 检测、FSM 提取、组合逻辑环检测等关键分析精度不足。开源 EDA 工具（slang、Yosys、Verilator）和商业 EDA 工具（Design Compiler、VCS、PrimeTime、SpyGlass）能够提供综合/仿真/时序级别的精确设计视图。集成 EDA 工具作为增强分析后端，可将系统从"语法级索引"升级为"多源融合知识图谱"，显著提升分析深度和准确性。

## What Changes

- **新增 EDA 工具编排层**：`EdaToolOrchestrator` 统一管理和调用各类 EDA 工具，支持配置化启用/禁用，自动检测工具可用性
- **开源 EDA 集成**：
  - **slang** — 深度 SV 前端解析，提供 generate 展开、参数求值、宏展开后的完整 AST
  - **Yosys** — 综合后网表分析，提供 FSM 自动提取、组合逻辑环检测、门控时钟识别、资源统计
  - **Verilator** — lint 检查和信号依赖图生成
- **商业 EDA 集成**：
  - **Design Compiler** — Tcl 脚本调用，提取综合后层次树、资源报告、时钟域报告
  - **VCS** — UCLI/Tcl 接口查询设计结构，解析编译日志和覆盖率数据库
  - **PrimeTime** — Tcl 脚本生成时序路径报告，提取关键路径和时钟偏斜
  - **SpyGlass / VC Lint** — 解析 lint/CDC/RDC 结构化报告
- **知识图谱融合层**：将 tree-sitter、slang、Yosys、商业 EDA 四源数据融合为统一知识图谱，节点类型扩展至综合/时序级别
- **图存储引擎升级**：在 SQLite 基础上新增内存图（networkx）支持多跳关系查询（时钟传播路径、组合环检测等）
- **新增 MCP 工具**：`rtl_eda_status`、`rtl_synthesis_report`、`rtl_timing_paths`、`rtl_clock_tree_advanced`、`rtl_cdc_advanced`

## Capabilities

### New Capabilities
- `eda-tool-orchestration`: EDA 工具调用编排层 — 统一配置管理、工具可用性检测、Tcl/命令行脚本生成、输出捕获与解析
- `open-source-eda-integration`: 开源 EDA 工具集成 — slang AST 提取、Yosys 网表分析、Verilator lint 检查
- `commercial-eda-integration`: 商业 EDA 工具集成 — Design Compiler、VCS、PrimeTime、SpyGlass/VC Lint 的报告生成与解析
- `knowledge-graph-fusion`: 多源知识图谱融合 — 合并 tree-sitter/slang/Yosys/DC 四源数据，统一节点/边类型体系，冲突消解策略
- `graph-storage-engine`: 图存储引擎 — 基于 networkx 的内存图构建，支持多跳查询、路径搜索、环检测
- `eda-mcp-tools`: EDA 增强 MCP 工具集 — `rtl_eda_status`、`rtl_synthesis_report`、`rtl_timing_paths`、`rtl_clock_tree_advanced`、`rtl_cdc_advanced`

### Modified Capabilities
- `project-packaging`: 扩展 `config.yaml` 支持 EDA 工具路径配置、工具启用开关、报告输出目录配置
- `sqlite-backend`: 新增 `eda_outputs` 表存储 EDA 工具输出的结构化数据（综合报告、时序报告、lint 报告）

## Impact

- `verilog_mcp_server/eda/` **新建目录**，包含：
  - `orchestrator.py` — EDA 工具编排器
  - `slang_adapter.py` — slang 调用与输出解析
  - `yosys_adapter.py` — Yosys 调用与输出解析
  - `verilator_adapter.py` — Verilator lint 报告解析
  - `dc_adapter.py` — Design Compiler Tcl 脚本生成与报告解析
  - `vcs_adapter.py` — VCS 结构查询与报告解析
  - `pt_adapter.py` — PrimeTime 时序报告解析
  - `lint_adapter.py` — SpyGlass/VC Lint 报告解析
  - `fusion_engine.py` — 知识图谱融合引擎
- `verilog_mcp_server/database/` — 新增 `eda_outputs` 表、图存储接口
- `verilog_mcp_server/analysis/` — 新增 `graph_query.py` 图查询引擎
- `verilog_mcp_server/tools/` — 新增 `eda_tools.py` 注册 EDA 增强 MCP 工具
- `config.yaml` — 新增 `eda_integration` 配置段
- **零新 Python 依赖**：EDA 工具通过系统 PATH 调用，networkx 为可选依赖（不可用时有向图查询回退到现有递归遍历）
