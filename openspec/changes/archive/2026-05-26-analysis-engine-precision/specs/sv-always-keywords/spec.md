## ADDED Requirements

### Requirement: always_comb 识别
`indexer/signal_extractor.py` 的 `extract_always_blocks()` SHALL 识别 tree-sitter 的 `always_comb_construct` 节点类型，将其 `block_type` 设置为 `"combinational"`，敏感列表统一记录为 `"@*"`（表示自动敏感列表），`statements` 包含完整块体文本。

#### Scenario: always_comb 块提取
- **WHEN** 源文件包含 `always_comb begin result = a + b; end`
- **THEN** 生成 `AlwaysBlockInfo(block_type="combinational", sensitivity_list="@*", statements=["result = a + b;"])`

### Requirement: always_ff 识别
`indexer/signal_extractor.py` 的 `extract_always_blocks()` SHALL 识别 tree-sitter 的 `always_ff_construct` 节点类型，从其 event_control 子节点提取敏感列表，`block_type` 设置为 `"sequential"`。

#### Scenario: always_ff 块提取
- **WHEN** 源文件包含 `always_ff @(posedge clk or negedge rst_n) begin data <= din; end`
- **THEN** 生成 `AlwaysBlockInfo(block_type="sequential", sensitivity_list="@(posedge clk or negedge rst_n)", statements=["data <= din;"])`

### Requirement: always_latch 识别
`indexer/signal_extractor.py` 的 `extract_always_blocks()` SHALL 识别 tree-sitter 的 `always_latch_construct` 节点类型，从其 event_control 子节点提取敏感列表，`block_type` 设置为 `"latch"`。

#### Scenario: always_latch 块提取
- **WHEN** 源文件包含 `always_latch begin if (en) q <= d; end`
- **THEN** 生成 `AlwaysBlockInfo(block_type="latch", sensitivity_list="@*", statements=["if (en) q <= d;"])`

### Requirement: 向后兼容
原有的 `always @(posedge clk)` / `always @(*)` 风格块（`always_construct` 节点类型）SHALL 继续按现有逻辑提取，行为不变。

#### Scenario: 传统 always 块不受影响
- **WHEN** 源文件包含 `always @(posedge clk) begin data <= din; end`
- **THEN** 行为与改进前完全一致，`block_type` 由敏感列表推断为 `"sequential"`
