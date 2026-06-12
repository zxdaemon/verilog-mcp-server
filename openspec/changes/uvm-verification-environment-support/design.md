## Context

当前 Verilog MCP Server 的索引层和分析层完全围绕 RTL 设计代码构建：
- **索引层**：`ModuleExtractor` 从 AST 中查找 `module_declaration` 节点；`SignalExtractor` 提取 wire/reg/logic；`InstanceExtractor` 提取子模块例化
- **分析层**：HierarchyBuilder 构建 module 层次树；FSMDetector 检测状态机；ClockAnalyzer 分析时钟域
- **数据层**：SQLite 存储 module/interface/package 定义

UVM 验证环境的核心是 **SystemVerilog class**（继承 `uvm_component`/`uvm_object`），通过 `type_id::create()` 构建层次，通过 TLM 端口连接通信，通过 `uvm_config_db` 传递配置。当前系统对 class 级别代码完全不可见。

tree-sitter-systemverilog 解析器**已经能够解析** `class_declaration`、`function_declaration`、`task_declaration`、`method_call` 等 AST 节点。我们需要在现有 AST 基础上增加 class/function 语义提取层和 UVM 模式识别层。

## Goals / Non-Goals

**Goals:**
- 提取 SV class 定义（类名、继承链、参数化类型、成员变量、方法）
- 提取 function/task 声明（名、参数、返回类型、修饰符）
- 识别 UVM 组件类（继承 `uvm_component` 或子类）
- 通过 `create`/`new` 调用构建 UVM 组件层次树
- 识别 UVM TLM 端口声明和 `.connect()` 调用
- 识别 `uvm_config_db::set`/`get` 调用
- 提供 4 个 UVM 专用 MCP 工具

**Non-Goals:**
- 不解析 UVM 宏展开后的代码（基于源码级 AST 分析）
- 不执行 UVM 仿真（静态分析，不运行 testbench）
- 不处理 UVM 报告机制（`uvm_info`/`uvm_error` 等）
- 不解析 UVM RAL（Register Abstraction Layer）
- 不引入 UVM 库作为依赖（零新外部依赖）

## Decisions

### 1. 提取器架构：复用现有遍历模式

**选择**: 新增 `ClassExtractor`、`FunctionExtractor`、`UvmExtractor` 三个提取器，复用现有的 `iter_module_body_deep` 和 AST 辅助函数风格。每个提取器接受 `source_file` 级 AST 节点（而非 module 级），因为 class 定义在 module 外。

**替代方案**: 创建统一的 "declaration extractor" 同时提取 module/class/interface → 拒绝，当前 module 提取器已经成熟且经过充分测试，统一重构风险高，增量添加更安全。

### 2. UVM 组件识别策略

**选择**: 两层识别：
1. **继承识别**：扫描 `class_declaration` 的 `extends` 子句，检查父类名是否匹配 `uvm_component`、`uvm_env`、`uvm_agent` 等已知 UVM 基类模式
2. **宏识别**：扫描 `macro_call` 节点，识别 `` `uvm_component_utils `` 和 `` `uvm_object_utils `` 宏调用（这些宏调用的存在是 UVM 组件/对象的强信号）

**替代方案**: 仅依赖继承链 → 拒绝，实际项目中常有 `uvm_component` 的多层封装基类，只认最顶层会漏掉中间层。

### 3. UVM 组件层次构建：静态分析 `create` 调用

**选择**: 在 `UvmExtractor` 中扫描 `function_call` 节点，识别 `type_id::create(...)` 和 `new(...)` 调用模式。提取：
- 被创建的实例名（`create` 的第一个字符串参数 `"inst_name"`）
- 父组件引用（`create` 的第二个参数 `this` 或显式父组件变量）
- 组件类型（`create` 调用前的类名）

**替代方案**: 基于 factory override 动态解析 → 拒绝，factory override 依赖运行时配置，静态分析无法准确还原。

### 4. 数据模型：ClassDef 与 ModuleDef 并列

**选择**: 新增 `ClassDef` dataclass（含 `name`、`extends`、`type_params`、`members`、`methods`、`is_uvm_component`、`uvm_base_class` 字段），与 `ModuleDef` 同级存储。SQLite 新增 `classes` 表，JSON 序列化存储嵌套数据（与 ModuleDef 相同策略）。

**替代方案**: 将 class 视为 "特殊 module" 复用 ModuleDef → 拒绝，class 和 module 的语义差异大（继承 vs 实例化、方法 vs always 块），硬塞进 ModuleDef 会导致模型混乱。

### 5. TLM 连接分析：基于变量名 + 类型推断

**选择**: 识别 TLM 端口分为两步：
1. 从 `data_declaration` 中提取类型为 `uvm_blocking_put_port`/`uvm_nonblocking_get_port`/`uvm_analysis_port`/`uvm_blocking_put_export`/`uvm_analysis_imp` 等的成员变量
2. 从 `method_call` 节点中识别 `.connect(...)` 调用，建立 port → target 的连接关系

连接目标解析为 "组件路径 + 端口名"（如 `"env.agent.driver.put_port"`），不要求运行时解析到具体对象。

**替代方案**: 基于完整类型推导的 TLM 连接 → 拒绝，SystemVerilog 的泛型参数推导在静态分析中过于复杂，基于变量名和类型声明已能满足 90% 场景。

### 6. config_db 追踪：提取三元组

**选择**: 识别 `uvm_config_db#(type)::set(scope, field_name, value)` 和 `::get(scope, field_name, variable)` 调用，提取：
- `field_name`：配置字段名（通常为字符串常量）
- `type`：泛型参数类型
- `scope`：作用路径（如 `"*"`、`"env.agent"`）
- `operation`：set 或 get

存储为 `UvmConfigEntry` 列表，支持按 field_name 和 scope 查询。

**替代方案**: 追踪 value 的常量传播 → 拒绝，value 可能是复杂表达式，常量传播实现成本高，且对理解配置拓扑帮助有限。

## Risks / Trade-offs

- **UVM 版本差异**：UVM 1.1d 与 UVM 1.2 在 API 上有差异（如 `uvm_config_db` vs 旧版 `set_config_*`）→ 优先支持 UVM 1.2（当前主流），对旧版 API 做最佳 effort 识别
- **宏调用解析限制**：tree-sitter 将 `` `uvm_component_utils(my_class) `` 解析为 `macro_call` 节点，但宏名和参数提取依赖源码文本，不受宏展开影响 → 这正是我们需要的（不需要展开）
- **多层继承的基类识别**：如果项目有 `my_base_agent extends uvm_agent extends uvm_component`，扫描 extends 链需要递归查找所有 class 定义 → 在 `UvmExtractor` 中构建 class 继承映射表，二次遍历完成基类推导
- **create 调用的父组件解析**：`type_id::create(name, parent)` 中 `parent` 参数可能是 `this`、成员变量或表达式 → 支持 `this`（当前类实例）和简单成员变量引用（`env.agent`），复杂表达式标记为 "unknown"
- **性能影响**：class 提取增加 AST 遍历开销 → UVM 验证文件通常远少于 RTL 文件，且增量构建机制确保仅变更文件被重新解析

## Open Questions

1. 是否需要支持 UVM 1.1d 的 `set_config_int`/`get_config_int` 等旧版 API？
2. 是否需要识别 `uvm_sequence`/`uvm_sequencer`/`uvm_driver` 三者的 `seq_item_port`/`seq_item_export` 自动连接？
3. 是否需要支持 UVM phase 的 ` objection ` 机制识别？
