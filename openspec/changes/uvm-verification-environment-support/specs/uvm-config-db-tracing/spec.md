## ADDED Requirements

### Requirement: Config DB set 调用识别
`UvmConfigDbTracer` SHALL 扫描 AST 中的 `method_call` 节点，识别 `uvm_config_db#(type)::set(scope, field_name, value)` 调用模式。提取：泛型类型、作用路径 scope、字段名 field_name、value 表达式文本。

#### Scenario: 标准 set 调用
- **WHEN** 源码中有 `uvm_config_db#(int)::set(this, "*", "delay", 100);`
- **THEN** 提取类型 `int`，scope `"*"`，field_name `"delay"`，value `100`

#### Scenario: 跨层级 set 调用
- **WHEN** 源码中有 `uvm_config_db#(bit)::set(null, "env.agent", "enable_check", 1'b1);`
- **THEN** 提取 scope `"env.agent"`，field_name `"enable_check"`，value `1'b1`

### Requirement: Config DB get 调用识别
`UvmConfigDbTracer` SHALL 识别 `uvm_config_db#(type)::get(scope, field_name, variable)` 调用模式。提取：泛型类型、作用路径 scope、字段名 field_name、接收变量名。

#### Scenario: 标准 get 调用
- **WHEN** 源码中有 `uvm_config_db#(int)::get(this, "", "delay", delay_val);`
- **THEN** 提取类型 `int`，scope `""`，field_name `"delay"`，变量 `delay_val`

### Requirement: Config DB 传播路径追踪
`UvmConfigDbTracer` SHALL 基于 set/get 调用对，追踪配置传播路径。对于每个 field_name，查找所有 set 调用（配置源）和所有 get 调用（配置目标），建立 set → get 映射关系。

#### Scenario: 配置传播匹配
- **WHEN** `env` 中 set `"delay"` 到 scope `"*"`，`agent` 和 `driver` 中分别 get `"delay"`
- **THEN** 建立传播路径 `env.set("delay", "*") → agent.get("delay")` 和 `env.set("delay", "*") → driver.get("delay")`

### Requirement: Config DB 未匹配检测
`UvmConfigDbTracer` SHALL 检测未匹配的 config_db 调用：有 set 无 get（可能冗余配置）、有 get 无 set（可能缺失配置）。

#### Scenario: 有 set 无 get
- **WHEN** `env` 中 set `"unused_field"`，但没有任何组件 get `"unused_field"`
- **THEN** 报告 `"unused_field"` 为有 set 无 get

#### Scenario: 有 get 无 set
- **WHEN** `driver` 中 get `"missing_field"`，但没有任何组件 set `"missing_field"`
- **THEN** 报告 `"missing_field"` 为有 get 无 set

### Requirement: Config DB MCP 工具
`rtl_uvm_config_trace` MCP 工具 SHALL 接受 `field_name` 参数（可选），返回 config_db 配置追踪结果。包含 set 列表、get 列表、传播路径、未匹配警告。

#### Scenario: 查询特定字段配置
- **WHEN** 调用 `rtl_uvm_config_trace(field_name="delay")`
- **THEN** 返回 `"delay"` 的所有 set/get 调用和传播路径

#### Scenario: 查询全部配置
- **WHEN** 调用 `rtl_uvm_config_trace()`
- **THEN** 返回所有 config_db 字段的完整追踪报告，含未匹配警告
