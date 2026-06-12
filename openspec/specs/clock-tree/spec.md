## ADDED Requirements

### Requirement: rtl_clock_tree tool 存在

系统 SHALL 提供 `rtl_clock_tree` MCP tool，参数为 `top_module: str`（必需）、`max_depth: int = 10`、`output_format: str = "text"`、`gated_clock_patterns: str = ""`。返回值 SHALL 为格式化后的字符串。

#### Scenario: 基本时钟树构建

- **WHEN** 调用 `rtl_clock_tree("soc", max_depth=5)`
- **THEN** 返回 ASCII 树状图，显示所有时钟域、各域下的模块树、每域的复位信号

#### Scenario: Mermaid 格式输出

- **WHEN** 调用 `rtl_clock_tree("soc", output_format="mermaid")`
- **THEN** 返回以 `flowchart TD` 开头的 Mermaid 描述，包含每个时钟域的 `subgraph`

### Requirement: 时钟信号名跨层次追踪

系统 SHALL 通过 `InstanceDef.port_connections` 将子模块本地时钟信号名映射为父模块实际信号名，逐级追溯到顶层以生成统一的根时钟名。

#### Scenario: 信号名穿透

- **WHEN** 顶层 `soc` 用信号 `sys_clk` 连接子模块 `u_cpu` 的 `clk` 端口，`u_cpu` 内部用 `cpu_clk` 连接 `u_alu` 的 `clk` 端口
- **THEN** `u_alu` 的本地时钟名 `clk` 被映射为根时钟名 `sys_clk`，与 `soc`、`u_cpu` 归入同一时钟域

### Requirement: 门控时钟单元识别

系统 SHALL 支持通过模块类型名模式匹配识别门控时钟单元。默认模式列表 SHALL 包含 `gated_clk_cell`。

#### Scenario: 门控单元检测

- **WHEN** 模块层次中存在模块类型名匹配 `gated_clk_cell` 的实例
- **THEN** 该实例在输出中被标记为 `⚙ [clock gating]`
- **AND** 通过该门控单元派生的下游模块显示为 `[gated from <时钟名>]`

### Requirement: 无时钟模块提示

系统 SHALL 在输出中列出所有未检测到时钟域的模块（纯组合逻辑或纯 assign 模块），标注 `(无 always 块)`。

#### Scenario: 无时钟模块列表

- **WHEN** 设计包含纯组合逻辑模块（无 always 块）
- **THEN** 输出底部列出这些模块的实例路径
