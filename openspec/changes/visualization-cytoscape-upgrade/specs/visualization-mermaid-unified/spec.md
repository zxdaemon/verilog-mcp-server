## ADDED Requirements

### Requirement: 从 GraphData 统一生成 Mermaid

系统 SHALL 提供 `graph_to_mermaid(graph_data: GraphData) -> str` 函数，从通用图数据模型生成 Mermaid 文本。

支持的图类型和 Mermaid 语法：
- hierarchy → `flowchart TD`
- fsm → `stateDiagram-v2`
- dataflow → `flowchart LR`
- clock → `flowchart TD`

#### Scenario: 生成层次图 Mermaid

- **WHEN** 调用 `graph_to_mermaid(hierarchy_graph_data)`
- **THEN** 返回以 `flowchart TD` 开头的 Mermaid 文本，节点标签为模块名

#### Scenario: 生成 FSM Mermaid

- **WHEN** 调用 `graph_to_mermaid(fsm_graph_data)`
- **THEN** 返回以 `stateDiagram-v2` 开头的 Mermaid 文本，包含状态和转移

### Requirement: 删除各引擎中的重复 Mermaid 实现

系统 SHALL 删除以下方法：
- `HierarchyBuilder.format_mermaid()` (hierarchy.py)
- `FSM.format_mermaid()` (fsm_detector.py)
- `FSMDetector.format_mermaid()` (fsm_detector.py)
- `DataflowTracer.format_mermaid()` (fan_in.py)
- `ClockTreeBuilder.format_mermaid()` (clock_tree.py)

`tools/visualize.py` 中的 Mermaid 输出路径 SHALL 改为先调用 `xxx_to_graph()` 构建 GraphData，再调用 `graph_to_mermaid()` 生成 Mermaid 文本。

#### Scenario: rtl_visualize 输出 Mermaid (hierarchy)

- **WHEN** 调用 `rtl_visualize("top", "hierarchy", "mermaid")`
- **THEN** 返回的 Mermaid 文本与原来 `HierarchyBuilder.format_mermaid()` 输出语义一致

#### Scenario: rtl_visualize 输出 Mermaid (fsm)

- **WHEN** 调用 `rtl_visualize("my_fsm", "fsm", "mermaid")`
- **THEN** 返回的 Mermaid 文本与原来 `FSMDetector.format_mermaid()` 输出语义一致
