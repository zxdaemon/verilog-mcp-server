## Why

tree-sitter 是纯语法解析器，不做预处理（宏不展开、参数不求值、generate 块不展开），这导致层次树、信号追踪、FSM 检测等分析只能基于源码表面结构，精度受限。slang 是业界公认最完整的开源 SystemVerilog 编译器前端，支持完整的 elaboration（generate 展开、参数求值、宏处理）。其官方 Python 绑定 `pyslang` 可直接通过 `pip install` 获得，无需用户额外安装任何二进制。将 pyslang 作为内置语义解析器集成到 MCP Server 中，可将索引从"语法级"提升到"语义级"，同时保持零额外安装负担。

## What Changes

- **新增核心依赖**：`pyproject.toml` 中添加 `pyslang`（`>=11.0.0`）作为核心 Python 依赖，用户 `pip install` 时自动获得
- **新增 pyslang 解析器**：`indexer/pyslang_parser.py` 封装 `pyslang.SyntaxTree` 和 `pyslang.Compilation`，提供 `parse_file()` 和 `elaborate_design()` 接口
- **新增 pyslang 提取器**：`indexer/pyslang_extractor.py` 从 pyslang elaboration 结果提取：generate 展开后的实例列表、参数求值后的信号位宽、宏定义/使用信息、完整层次树（含数组例化名）
- **增强数据模型**：`database/models.py` 新增 `ElaboratedInstanceDef`（含展开路径、原始 generate 条件）、`ResolvedSignalDef`（含求值后位宽）、`MacroExpansionInfo`
- **融合索引构建**：`indexer/builder.py` 在现有 tree-sitter 流程后，增加 pyslang elaboration 步骤，提取增强数据并存入 `IndexStore`
- **增强 MCP 工具**：`rtl_get_module` 返回参数求值后的信号位宽；`rtl_hierarchy` 支持 generate 展开后的实例名；新增 `rtl_elab_report` 显示 elaboration 差异
- **其他 EDA 工具保持外部调用**：Yosys/DC/PT/SpyGlass 仍通过系统 PATH 调用，在后续独立 change 中实现

## Capabilities

### New Capabilities
- `pyslang-semantic-parser`: pyslang 内置语义解析 — 通过 `pip install` 即可获得，封装 `SyntaxTree.fromFile` 和 `Compilation` API，提供 elaboration 能力
- `pyslang-elaboration-extraction`: pyslang elaboration 信息提取 — 从 elaborated AST 中提取 generate 展开实例、参数求值结果、宏展开映射
- `enhanced-hierarchy-with-pyslang`: pyslang 增强层次树 — 基于 elaboration 结果构建含 generate 展开实例、参数化模块精确类型的层次树
- `elab-data-model`: elaboration 增强数据模型 — `ElaboratedInstanceDef`、`ResolvedSignalDef`、`MacroExpansionInfo` 等数据类型

### Modified Capabilities
- `project-packaging`: `pyproject.toml` 新增 `pyslang` 核心依赖，版本约束 `>=11.0.0`
- `incremental-update`: 增量构建时需检测 elaboration 相关变更（parameter 值变化、generate 条件变化），触发 pyslang 重解析
- `sqlite-backend`: 新增 `elaborated_instances`、`resolved_signals`、`macro_expansions` 三张表

## Impact

- `pyproject.toml` — 新增 `pyslang>=11.0.0` 依赖
- `indexer/pyslang_parser.py` **新建** — pyslang 解析封装
- `indexer/pyslang_extractor.py` **新建** — elaboration 信息提取
- `indexer/builder.py` — 集成 pyslang elaboration 步骤到索引构建流程
- `database/models.py` — 新增 elaboration 相关数据模型
- `database/sqlite_backend.py` — 新增 elaboration 数据表
- `tools/level1_search.py` — `rtl_get_module` 和 `rtl_hierarchy` 返回 pyslang 增强数据
- `tools/level3_analysis.py` — 时钟域/FSM 分析可使用 pyslang 求值后的信号位宽
- `config.yaml` — 新增 `pyslang` 配置段（启用开关、elaboration 选项）
