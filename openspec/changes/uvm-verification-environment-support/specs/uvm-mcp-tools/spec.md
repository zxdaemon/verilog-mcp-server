## ADDED Requirements

### Requirement: rtl_uvm_hierarchy 工具
MCP Server SHALL 注册 `rtl_uvm_hierarchy` 工具，接受参数 `test_class: str | None`（可选），返回 UVM 组件层次树。返回格式为结构化数据，支持文本缩进和 Mermaid flowchart 两种输出格式。

#### Scenario: 返回组件层次树
- **WHEN** 调用 `rtl_uvm_hierarchy(test_class="my_basic_test")`
- **THEN** 返回 JSON 结构：`{test: "my_basic_test", children: [{type: "my_env", name: "env", children: [...]}]}`

#### Scenario: Mermaid 格式输出
- **WHEN** 调用 `rtl_uvm_hierarchy(test_class="my_test", format="mermaid")`
- **THEN** 返回 Mermaid flowchart 文本，可用 Claude Code 直接渲染

### Requirement: rtl_uvm_tlm_connections 工具
MCP Server SHALL 注册 `rtl_uvm_tlm_connections` 工具，接受参数 `component_path: str | None`（可选），返回 TLM 连接图。返回格式包含端口声明列表和 connect 关系列表。

#### Scenario: 返回 TLM 连接详情
- **WHEN** 调用 `rtl_uvm_tlm_connections(component_path="env.my_agent")`
- **THEN** 返回 `{ports: [...], connections: [{from: "...", to: "...", type: "..."}]}`

### Requirement: rtl_uvm_config_trace 工具
MCP Server SHALL 注册 `rtl_uvm_config_trace` 工具，接受参数 `field_name: str | None`（可选），返回 config_db 配置追踪报告。包含 set 列表、get 列表、传播路径和未匹配警告。

#### Scenario: 返回配置追踪报告
- **WHEN** 调用 `rtl_uvm_config_trace(field_name="delay")`
- **THEN** 返回 `{sets: [...], gets: [...], propagation_paths: [...], warnings: [...]}`

### Requirement: rtl_uvm_component_detail 工具
MCP Server SHALL 注册 `rtl_uvm_component_detail` 工具，接受参数 `class_name: str`，返回指定 UVM 组件类的详细信息。包含：继承链、成员变量、方法列表、TLM 端口声明、config_db get 调用。

#### Scenario: 返回组件类详情
- **WHEN** 调用 `rtl_uvm_component_detail(class_name="my_driver")`
- **THEN** 返回 `{name: "my_driver", extends: "uvm_driver", members: [...], methods: [...], tlm_ports: [...], config_gets: [...]}`

### Requirement: 工具注册与 server 集成
`tools/uvm_tools.py` SHALL 定义 4 个工具的注册函数，`server.py` SHALL 在启动时调用注册函数。工具使用现有 `IndexStore` 查询接口获取 class/method/uvm 数据。

#### Scenario: 服务器启动时 UVM 工具可用
- **WHEN** MCP Client 查询可用工具列表
- **THEN** 工具列表中包含 `rtl_uvm_hierarchy`、`rtl_uvm_tlm_connections`、`rtl_uvm_config_trace`、`rtl_uvm_component_detail`
