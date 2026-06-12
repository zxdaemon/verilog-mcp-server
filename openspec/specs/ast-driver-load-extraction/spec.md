## ADDED Requirements

### Requirement: AST-based 驱动提取
`indexer/signal_extractor.py` 的 `SignalExtractor` SHALL 提供方法，在索引构建时用 tree-sitter AST 遍历 always 块和 assign 语句，为每个被赋值的信号生成 `DriverInfo` 记录并填充到对应 `SignalDef.drivers` 列表。

#### Scenario: 时序 always 块中的非阻塞赋值
- **WHEN** 处理 `always @(posedge clk) begin data <= input_val; end`
- **THEN** 系统提取驱动 `DriverInfo(type="always_block", source="always @(posedge clk)", line=<line>)` 并添加到信号 `data` 的 `drivers` 列表

#### Scenario: 组合 always 块中的阻塞赋值
- **WHEN** 处理 `always @(*) begin result = a + b; end`
- **THEN** 系统提取驱动 `DriverInfo(type="always_block", source="always @(*)", line=<line>)` 并添加到信号 `result` 的 `drivers` 列表

#### Scenario: assign 连续赋值
- **WHEN** 处理 `assign foo = bar & baz;`
- **THEN** 系统提取驱动 `DriverInfo(type="assign", source="assign foo = bar & baz", line=<line>)` 并添加到信号 `foo` 的 `drivers` 列表

### Requirement: AST-based 负载提取
`indexer/signal_extractor.py` SHALL 在提取驱动的同时，从 always 块和 assign 语句中提取每个被赋值信号的 RHS 表达式和条件表达式中引用的信号，生成 `LoadInfo` 记录并填充到对应 `SignalDef.loads` 列表。

#### Scenario: always 块条件表达式中的信号引用
- **WHEN** 处理 `always @(posedge clk) begin if (enable) data <= input_val; end`
- **THEN** 系统提取负载 `LoadInfo(type="always_block", target="always @(posedge clk): condition signal 'enable'", line=<line>)` 并添加到信号 `enable` 的 `loads` 列表

#### Scenario: assign 右侧表达式中的信号引用
- **WHEN** 处理 `assign foo = bar & baz;`
- **THEN** 系统提取负载分别添加到信号 `bar` 和 `baz` 的 `loads` 列表

#### Scenario: always 块敏感列表中的信号引用
- **WHEN** 处理 `always @(posedge clk or negedge rst_n)`
- **THEN** 系统提取负载分别添加到信号 `clk` 和 `rst_n` 的 `loads` 列表

### Requirement: 索引构建器集成
`indexer/builder.py` 的 `IndexBuilder.build()` SHALL 在提取信号后、添加模块到 index_store 前，调用信号提取器的驱动/负载提取方法，将结果写入对应 `SignalDef` 的 `drivers` 和 `loads` 字段。

#### Scenario: 完整索引流程包含驱动/负载
- **WHEN** 执行 `rtl_build_index`
- **THEN** 构建完成后，每个模块的 `SignalDef` 中 `drivers` 和 `loads` 字段均被正确填充（可能为空列表表示无驱动或无负载）
