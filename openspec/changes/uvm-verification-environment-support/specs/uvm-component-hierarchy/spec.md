## ADDED Requirements

### Requirement: UvmExtractor 识别组件创建调用
`UvmExtractor` SHALL 扫描 AST 中的 `method_call` 节点，识别 `type_id::create(...)` 调用模式。提取：组件类型名、实例名字符串、父组件引用。

#### Scenario: 标准 create 调用
- **WHEN** 源码中有 `my_driver drv = my_driver::type_id::create("drv", this);`
- **THEN** 提取组件类型 `my_driver`，实例名 `drv`，父组件 `this`

#### Scenario: 嵌套组件创建
- **WHEN** 源码中有 `my_agent agent = my_agent::type_id::create("agent", this);` 和 `agent.my_driver drv = my_driver::type_id::create("drv", agent);`
- **THEN** 分别提取 `agent`（父 `this`）和 `drv`（父 `agent`）

### Requirement: UvmHierarchyBuilder 构建组件树
`UvmHierarchyBuilder` SHALL 基于 `UvmExtractor` 提取的创建调用和 `ClassExtractor` 提取的 class 继承信息，构建完整的 UVM 组件层次树。树节点包含：组件类型、实例名、父节点引用、子节点列表。

#### Scenario: 简单 UVM 环境层次
- **WHEN** `my_test` 创建 `my_env`，`my_env` 创建 `my_agent`，`my_agent` 创建 `my_driver` 和 `my_monitor`
- **THEN** 层次树为 `my_test → my_env → my_agent → [my_driver, my_monitor]`

#### Scenario: 多 agent 环境
- **WHEN** `my_env` 创建 `agent_a` 和 `agent_b`，各自包含 driver/monitor
- **THEN** `my_env` 下有两个 `my_agent` 子节点，分别有自己的 driver/monitor 子树

### Requirement: UVM 组件根节点识别
`UvmHierarchyBuilder` SHALL 将继承 `uvm_test` 的 class 作为层次树的根节点。若存在多个 test 类，返回多棵树。

#### Scenario: 单 test 环境
- **WHEN** 项目中只有一个类继承 `uvm_test`
- **THEN** 返回单棵组件树，根节点为该 test 类

#### Scenario: 多 test 环境
- **WHEN** 项目中有 `test_base extends uvm_test` 和 `test_derived extends test_base`
- **THEN** 返回两棵树，分别对应两个 test 类

### Requirement: 组件树 MCP 工具
`rtl_uvm_hierarchy` MCP 工具 SHALL 接受 `test_class` 参数（可选），返回对应 UVM 组件层次树。若未指定 test_class，返回所有 test 类的层次树列表。

#### Scenario: 查询特定 test 的组件树
- **WHEN** 调用 `rtl_uvm_hierarchy(test_class="my_basic_test")`
- **THEN** 返回 `my_basic_test` 的完整组件层次树，含组件类型、实例名、深度

#### Scenario: 查询所有 test 的组件树
- **WHEN** 调用 `rtl_uvm_hierarchy()` 且不传 test_class
- **THEN** 返回所有发现的 `uvm_test` 子类的组件树列表
