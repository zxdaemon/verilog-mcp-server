## ADDED Requirements

### Requirement: DataflowTracer 提供 Mermaid 格式输出

`analysis/fan_in.py` 的 `DataflowTracer` 类 SHALL 提供静态方法 `format_mermaid(result: TraceResult, title: str) -> str`，输出 Mermaid flowchart 语法的信号数据流图。

Mermaid 输出 SHALL 以 `flowchart TD` 开头，包含：
- 每个 TraceNode 为一个节点，标签格式为 `signal_name @ module_name [role]`
- 父子追踪关系为有向边（`-->`）
- 按 module_name 分 `subgraph` 组

#### Scenario: Fan-in 追踪 Mermaid 输出

- **WHEN** 对信号 `data` 执行 fan-in 追踪，追踪到 `data @ soc [assign_rhs]` 和 `data @ cpu [port_input_up]`
- **THEN** 返回以 `flowchart TD` 开头的字符串
- **AND** 包含按模块分组的 subgraph
- **AND** 包含信号间的有向边，标注 role

#### Scenario: 多分支追踪

- **WHEN** 信号有多个驱动源（fan-in 分支）
- **THEN** Mermaid 输出包含分叉的有向边，每个驱动源一个分支

#### Scenario: 跨模块追踪

- **WHEN** 信号跨越多个模块层次
- **THEN** 每个模块的节点在独立的 subgraph 中
