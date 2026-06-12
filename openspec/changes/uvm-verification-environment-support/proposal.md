## Why

当前 Verilog MCP Server 专注于 RTL 设计代码（module/interface/package）的解析与分析，但现代芯片验证工作大量基于 UVM（Universal Verification Methodology）验证环境。验证工程师需要理解 UVM 组件层次、TLM 连接关系、config_db 配置传播和 sequence 驱动关系，这些需求与 RTL 分析同等重要。扩展 UVM 解析能力将使 MCP Server 成为覆盖"设计+验证"双域的完整 HDL 分析工具。

## What Changes

- **新增 SV class 解析能力**：提取 `class_declaration`（类名、继承父类、参数化类型、成员变量、方法），补充现有仅支持 module/interface/package 的提取器
- **新增 function/task 提取器**：提取 class 内和 package 内的 `function_declaration`/`task_declaration`（名、参数、返回类型、virtual/pure virtual 修饰）
- **新增 UVM 组件层次构建器**：通过分析 `type_id::create()`/`new()` 调用和 `uvm_component` 继承链，构建 UVM 组件树（env → agent → sequencer/driver/monitor → scoreboard）
- **新增 UVM TLM 连接分析器**：识别 `uvm_blocking_put_port`/`uvm_analysis_port` 等 TLM 端口声明和 `.connect()` 调用，构建 TLM 连接拓扑
- **新增 UVM config_db 追踪器**：识别 `uvm_config_db#(type)::set()`/`::get()` 调用，追踪配置键值在组件层次中的传播路径
- **新增 UVM MCP 工具**：`rtl_uvm_hierarchy`、`rtl_uvm_tlm_connections`、`rtl_uvm_config_trace`、`rtl_uvm_component_detail`
- **扩展索引存储**：在 SQLite 中新增 `classes`、`methods`、`uvm_components` 表，支持 class 级查询
- **扩展项目扫描器**：将 `.sv` 文件中 class 定义纳入索引范围

## Capabilities

### New Capabilities
- `class-extraction`: SystemVerilog class 定义提取 — 类名、extends 继承链、参数化类型、成员变量、方法列表、访问修饰符
- `function-task-extraction`: function/task 声明提取 — 函数/任务名、参数列表、返回类型、virtual/pure virtual/static 修饰、所属 class/package
- `uvm-component-hierarchy`: UVM 组件层次树构建 — 基于 `uvm_component` 继承识别组件类，通过 `create`/`new` 调用构建父子关系树
- `uvm-tlm-connection-analysis`: UVM TLM 连接拓扑分析 — 识别 TLM 端口类型声明、`.connect()` 调用、构建 port→export→imp 连接图
- `uvm-config-db-tracing`: UVM config_db 配置追踪 — 识别 `uvm_config_db::set`/`get` 调用，提取字段名、类型、作用路径、追踪配置传播
- `uvm-mcp-tools`: UVM 专用 MCP 工具集 — `rtl_uvm_hierarchy`、`rtl_uvm_tlm_connections`、`rtl_uvm_config_trace`、`rtl_uvm_component_detail`

### Modified Capabilities
- `project-packaging`: 扩展文件扫描范围，将 UVM 验证文件（通常以 `_env`/`_agent`/`_test`/`_seq` 结尾的 `.sv` 文件）纳入默认索引范围
- `sqlite-backend`: 新增 `classes`、`methods`、`uvm_components` 三张表及对应的 CRUD 操作

## Impact

- `indexer/module_extractor.py` → 或拆分出 `indexer/class_extractor.py`，新增 class 提取逻辑
- `indexer/` 目录新增 `class_extractor.py`、`function_extractor.py`、`uvm_extractor.py`
- `database/models.py` → 新增 `ClassDef`、`MethodDef`、`UvmComponentDef` 等数据模型
- `database/sqlite_backend.py` → 新增 class/method/uvm 相关表和 CRUD
- `database/index_store.py` → 新增 class/method 缓存和查询接口
- `analysis/` 目录新增 `uvm_hierarchy.py`、`uvm_tlm.py`、`uvm_config_db.py`
- `tools/` 目录新增 `uvm_tools.py`，注册 UVM 专用 MCP 工具
- `indexer/project_scanner.py` → 扩展默认文件扩展名/排除规则，避免遗漏 UVM 文件
- `server.py` → 注册新的 UVM 工具
- **零新外部依赖**：继续使用 tree-sitter-systemverilog 解析 AST，UVM 语义通过 AST 遍历识别
