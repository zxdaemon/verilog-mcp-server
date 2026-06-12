## ADDED Requirements

### Requirement: generate 块内例化提取
`indexer/instance_extractor.py` SHALL 递归遍历 `generate_construct`、`loop_generate_construct`、`if_generate_construct`、`case_generate_construct` 节点，提取其内部所有 `module_instantiation` 子节点，生成 `InstanceDef` 记录。

#### Scenario: for-generate 块中的例化
- **WHEN** 源文件包含 `generate for (genvar i=0; i<4; i++) begin : gen label u_ff (.clk, .d(d[i]), .q(q[i])); end endgenerate`
- **THEN** 系统提取例化 `u_ff`（module_type 为 `label` 的实例），记录到所在模块的 `instances` 列表

#### Scenario: if-generate 块中的例化
- **WHEN** 源文件包含 `generate if (USE_FEATURE) begin : feat_blk sub u_inst (...); end endgenerate`
- **THEN** 系统提取例化 `u_inst`，记录到所在模块的 `instances` 列表

### Requirement: generate 块内信号声明提取
`indexer/signal_extractor.py` SHALL 递归遍历 generate 构造节点，提取其内部所有 `net_declaration` 和 `data_declaration` 子节点，生成 `SignalDef` 记录。

#### Scenario: generate 块中的 wire 声明
- **WHEN** 源文件在 generate 块内包含 `wire [7:0] gen_signal;`
- **THEN** 系统提取信号 `gen_signal`（var_type="wire", width_range="[7:0]"），添加到所在模块的 `signals` 列表
