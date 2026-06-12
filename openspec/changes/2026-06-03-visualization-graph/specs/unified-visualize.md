## ADDED Requirements

### Requirement: rtl_visualize 统一可视化 MCP 工具

`tools/visualize.py` SHALL 注册 `rtl_visualize` MCP 工具，参数为 `target: str`（必需）、`diagram_type: str = "auto"`、`output_format: str = "mermaid"`、`max_depth: int = 10`。返回值 SHALL 为字符串。

#### Scenario: auto 检测 — 模块层次图

- **WHEN** 调用 `rtl_visualize("soc")`，其中 `soc` 是有子例化的模块
- **THEN** 自动选择 `hierarchy` 图类型
- **AND** 返回 Mermaid flowchart 格式的层次图

#### Scenario: auto 检测 — FSM 状态图

- **WHEN** 调用 `rtl_visualize("traffic_ctrl")`，其中 `traffic_ctrl` 无子例化但有 FSM
- **THEN** 自动选择 `fsm` 图类型
- **AND** 返回 Mermaid stateDiagram 格式的状态图

#### Scenario: auto 检测 — 信号数据流

- **WHEN** 调用 `rtl_visualize("data_bus")`，其中 `data_bus` 是信号名
- **THEN** 自动选择 `dataflow` 图类型
- **AND** 返回 Mermaid flowchart 格式的数据流图

#### Scenario: 手动指定图类型

- **WHEN** 调用 `rtl_visualize("soc", diagram_type="clock")`
- **THEN** 使用 `clock` 图类型而非 auto 检测
- **AND** 返回时钟域 Mermaid 图

#### Scenario: HTML 输出格式

- **WHEN** 调用 `rtl_visualize("soc", output_format="html")`
- **THEN** 生成交互式 HTML 文件
- **AND** 返回 HTML 文件路径

#### Scenario: 目标不存在

- **WHEN** 调用 `rtl_visualize("nonexistent_module")`
- **THEN** 返回错误信息，提示目标不存在于索引中
