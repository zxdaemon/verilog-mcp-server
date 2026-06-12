## ADDED Requirements

### Requirement: rtl_hierarchy 返回 generate 展开实例
`rtl_hierarchy` MCP 工具 SHALL 在 pyslang 数据可用时，返回层次树包含 generate 展开后的实例名。实例节点包含 `is_generated` 标志和 `generate_condition` 字段。

#### Scenario: 含 generate 展开的层次树
- **WHEN** 调用 `rtl_hierarchy(module="top")` 且 pyslang 数据可用
- **THEN** 返回的层次树中包含 `top.genblk[0].u_cpu`、`top.genblk[1].u_cpu` 等展开实例

### Requirement: rtl_get_module 返回参数求值后信息
`rtl_get_module` MCP 工具 SHALL 在 pyslang 数据可用时，返回信号列表包含 `resolved_width`（求值后位宽）。参数列表包含 `resolved_value`（求值后值）。

#### Scenario: 参数求值后的模块详情
- **WHEN** 调用 `rtl_get_module(name="fifo")` 且 pyslang 数据可用
- **THEN** 返回的 `signals` 中每个信号含 `width`（原始文本）和 `resolved_width`（求值后）
- **AND** `parameters` 中每个参数含 `value`（原始文本）和 `resolved_value`（求值后）

### Requirement: 新增 rtl_elab_report 工具
MCP Server SHALL 注册 `rtl_elab_report` 工具，返回当前项目的 elaboration 摘要报告。包含：generate 块数量、展开实例总数、参数化模块数量、宏定义数量、tree-sitter 与 pyslang 的模块数量差异。

#### Scenario: elaboration 摘要报告
- **WHEN** 调用 `rtl_elab_report()`
- **THEN** 返回 `{generate_blocks: 5, elaborated_instances: 42, parameterized_modules: 8, macros: 12, tree_sitter_modules: 10, pyslang_modules: 15}`

### Requirement: 层次树可视化支持 generate 实例
`analysis/visualizer.py` 的 `hierarchy_to_graph()` SHALL 在生成层次图时，为 generate 展开的实例使用特殊样式（如不同颜色或虚线边框），并在 tooltip 中显示 generate 条件。

#### Scenario: 可视化 generate 实例
- **WHEN** 调用 `rtl_visualize(type="hierarchy")`
- **THEN** generate 展开的实例在图中以特殊样式显示，hover 时显示原始 generate 条件
