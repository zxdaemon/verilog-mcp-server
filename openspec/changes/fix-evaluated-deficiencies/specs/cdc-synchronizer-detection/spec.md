## ADDED Requirements

### Requirement: 双触发器同步器识别
`ClockAnalyzer._detect_synchronizer()` SHALL 识别双触发器同步器模式：信号跨时钟域后，在目标时钟域中连续经过两个时序 always 块（同一时钟），且第一个同步触发器的输出仅被第二个同步触发器读取。

#### Scenario: 标准双触发器同步器
- **WHEN** 模块中存在信号 `async_sig` 被 `clk_b` 域的 `sync_reg1 <= async_sig` 和 `sync_reg2 <= sync_reg1` 两级采样
- **THEN** `sync_reg2` 被标记为"已同步"，`async_sig` 的 CDC 风险等级为"low"（已识别同步器）

#### Scenario: 无同步器的 CDC 信号
- **WHEN** 信号 `raw_data` 出现在多个时钟域的 always 块敏感列表中，且无连续两级同时钟触发器采样
- **THEN** `raw_data` 被标记为"未同步"，CDC 风险等级为"high"

### Requirement: 握手同步器识别
`ClockAnalyzer._detect_synchronizer()` SHALL 识别握手同步器模式：跨时钟域信号对（请求/应答）在各自时钟域中存在对应的锁存/采样逻辑，且存在状态反馈回路。

#### Scenario: 请求-应答握手同步器
- **WHEN** 模块中存在 `req` 从 `clk_a` 域发到 `clk_b` 域，且 `ack` 从 `clk_b` 域返回 `clk_a` 域，各自经过两级同步
- **THEN** `req` 和 `ack` 均被标记为"已同步（握手）"

### Requirement: CDC 检测结果分级输出
`rtl_cross_domain_signals` 工具 SHALL 在结果中为每个跨时钟域信号标注风险等级（`high`/`medium`/`low`）和同步器类型（`none`/`double-flop`/`handshake`/`unknown`）。

#### Scenario: 风险分级报告
- **WHEN** 模块中存在 3 个跨时钟域信号：一个无同步器、一个有双触发器同步器、一个有握手同步器
- **THEN** 报告分别标记为 `high/none`、`low/double-flop`、`low/handshake`

### Requirement: 同步器识别不引入新依赖
同步器识别算法 SHALL 仅基于已索引的 AST 信息（always 块敏感列表、赋值语句、信号驱动/负载关系），不引入新的外部库或形式验证工具。

#### Scenario: 纯索引数据分析
- **WHEN** 调用 `ClockAnalyzer.detect_cross_domain_signals()` 且索引中无同步器信息
- **THEN** 分析完全基于 `ModuleDef.always_blocks`、`SignalDef.drivers` 和 `SignalDef.loads`
