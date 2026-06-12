## ADDED Requirements

### Requirement: 知识图谱节点类型体系
`FusionEngine` SHALL 定义统一的知识图谱节点类型，覆盖 tree-sitter、slang、Yosys、DC/PT 四源数据：
- `module` — 模块定义
- `instance` — 模块例化（含 generate 展开后的实例）
- `signal` — 信号/线网
- `port` — 端口
- `assignment` — 赋值语句
- `always_block` — always 块
- `clock_domain` — 时钟域（含频率、来源）
- `fsm_state` — FSM 状态
- `fsm_transition` — FSM 转移
- `parameter` — 参数（含求值后的值）
- `macro` — 宏定义
- `generate_block` — generate 块

#### Scenario: 多源模块节点
- **WHEN** `top` 模块在 tree-sitter、slang、Yosys 中都有定义
- **THEN** 融合后生成一个 `top` 节点，包含四源的属性合并

### Requirement: 知识图谱边类型体系
`FusionEngine` SHALL 定义统一的知识图谱边类型：
- `contains` — 模块包含信号/端口/实例
- `instantiates` — 实例例化模块类型
- `drives` — 信号驱动信号
- `connects_to` — 端口连接信号
- `clocks` — 时钟域驱动寄存器
- `resets` — 复位信号驱动寄存器
- `transitions_to` — FSM 状态转移
- `references` — 信号引用参数/宏
- `expands_from` — generate 实例从 generate 块展开

#### Scenario: 信号驱动边
- **WHEN** `assign b = a + 1` 在 slang 中解析为 `a` 驱动 `b`
- **THEN** 生成边 `(a) --drives--> (b)`

### Requirement: 数据来源标记与置信度
每个节点和边 SHALL 标记数据来源（`source: tree-sitter | slang | yosys | dc | pt | vcs | lint`）和置信度（`confidence: high | medium | low`）。综合/仿真后数据置信度为 high，语法分析数据为 medium。

#### Scenario: Yosys 与 tree-sitter 的 FSM 冲突
- **WHEN** tree-sitter 识别到 FSM 有 4 个状态，Yosys 综合后识别到 3 个状态（一个状态被优化掉）
- **THEN** 保留 Yosys 的 3 状态结果（high confidence），tree-sitter 的 4 状态结果存入 `alternatives`

### Requirement: 冲突消解策略
当多源数据冲突时，`FusionEngine` SHALL 按优先级选择：综合后数据 > 仿真数据 > 语法分析数据（`yosys/dc/pt > vcs > slang > tree-sitter`）。冲突信息记录在节点/边的 `conflict_info` 字段中。

#### Scenario: 信号位宽冲突
- **WHEN** tree-sitter 报告信号位宽为 `[WIDTH-1:0]`，slang 求值后为 `[31:0]`
- **THEN** 保留 slang 的 `[31:0]`，tree-sitter 的原始文本存入 `alternatives.raw_width`

### Requirement: 增量融合
`FusionEngine` SHALL 支持增量融合：当单个文件变更时，仅重新融合该文件相关的节点和边，不影响图谱其他部分。

#### Scenario: 单个文件变更
- **WHEN** `cpu.v` 修改后重新索引
- **THEN** 仅删除和重建 `cpu.v` 相关的节点和边，其他模块的图谱不变
