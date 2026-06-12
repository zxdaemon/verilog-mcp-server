## ADDED Requirements

### Requirement: rtl_eda_status 工具
MCP Server SHALL 注册 `rtl_eda_status` 工具，返回当前已启用和可用的 EDA 工具列表。包含：工具名、是否启用、是否可用（PATH 中检测到）、上次运行时间、缓存状态。

#### Scenario: 查询 EDA 工具状态
- **WHEN** 调用 `rtl_eda_status()`
- **THEN** 返回 `{tools: [{name: "slang", enabled: true, available: true, last_run: "..."}, {name: "dc_shell", enabled: true, available: false}]}`

### Requirement: rtl_synthesis_report 工具
MCP Server SHALL 注册 `rtl_synthesis_report` 工具，返回综合报告摘要。包含：模块层次树、资源统计（LUT/FF/Memory/DSP）、时钟域列表、FSM 列表、组合逻辑环告警。

#### Scenario: 查询综合报告
- **WHEN** 调用 `rtl_synthesis_report()`
- **THEN** 返回 `{hierarchy: {...}, resources: {lut: 1234, ff: 567, memory: 8}, clock_domains: [...], fsms: [...], combinational_loops: [...]}`

### Requirement: rtl_timing_paths 工具
MCP Server SHALL 注册 `rtl_timing_paths` 工具，接受 `clock_domain` 和 `max_paths` 参数（可选），返回时序路径报告。包含：关键路径列表（起点、终点、延迟、slack）、时钟偏斜信息。

#### Scenario: 查询时序路径
- **WHEN** 调用 `rtl_timing_paths(clock_domain="clk_fast", max_paths=10)`
- **THEN** 返回前 10 条 `clk_fast` 域的关键路径

### Requirement: rtl_clock_tree_advanced 工具
MCP Server SHALL 注册 `rtl_clock_tree_advanced` 工具，返回增强的时钟树分析。基于 Yosys/DC 综合后数据，包含：时钟源、分频器链、门控时钟单元、时钟偏斜、时钟域交叉点。

#### Scenario: 查询增强时钟树
- **WHEN** 调用 `rtl_clock_tree_advanced()`
- **THEN** 返回 `{sources: [...], dividers: [...], gated_clocks: [...], skews: [...], cdc_points: [...]}`

### Requirement: rtl_cdc_advanced 工具
MCP Server SHALL 注册 `rtl_cdc_advanced` 工具，返回增强的 CDC 分析报告。基于 Yosys/SpyGlass/PT 数据，包含：跨时钟域信号列表、同步器类型（双触发器/FIFO/握手）、未同步信号告警、CDC 路径详情。

#### Scenario: 查询增强 CDC 报告
- **WHEN** 调用 `rtl_cdc_advanced()`
- **THEN** 返回 `{signals: [{name: "data_cross", from_clock: "clk_a", to_clock: "clk_b", synchronizer: "double_flop", risk: "low"}, ...]}`

### Requirement: 工具返回 EDA 数据来源
所有 EDA 增强工具 SHALL 在返回结果中标注数据来源（`source: yosys | dc | pt | slang | tree-sitter`），让用户了解分析结果的可靠性级别。

#### Scenario: 数据来源标注
- **WHEN** `rtl_synthesis_report()` 返回 FSM 列表
- **THEN** 每个 FSM 包含 `source: "yosys"`，表示来自综合器提取
