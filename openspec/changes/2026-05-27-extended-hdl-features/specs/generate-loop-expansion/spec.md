## MODIFIED Requirements

### Requirement: 展开 for-generate 循环

`indexer/verilog_parser.py` 的 `iter_module_body_deep` SHALL 在遍历 generate 块时展开可静态计算的 for-generate 循环。

#### Scenario: 固定次数 for 循环

- **WHEN** generate 块包含 `for(genvar i = 0; i < 4; i++) begin : gen loop_var = i; end`
- **THEN** 展开为 4 个具名实例：`genblk0.loop_var`, `genblk1.loop_var`, `genblk2.loop_var`, `genblk3.loop_var`

#### Scenario: 循环体包含例化

- **WHEN** for 循环体包含 `sub u_sub (.a(data[i]));`
- **THEN** 展开为 `genblk0.u_sub`, `genblk1.u_sub` 等具名例化

### Requirement: 展开上限

`indexer/verilog_parser.py` SHALL 限制 generate 循环展开次数。

#### Scenario: 超出展开上限

- **WHEN** for 循环次数超过 256（可配置）
- **THEN** 不展开，保留原始 generate 结构，并记录 warning

### Requirement: genvar 替换

`indexer/verilog_parser.py` SHALL 在展开时将 genvar 替换为具体整数值。

#### Scenario: genvar 用于信号名

- **WHEN** 循环体包含 `logic [7:0] data_i;`（genvar 名为 i）
- **THEN** 展开后信号名为 `genblk0_data_0`, `genblk1_data_1` 等

#### Scenario: genvar 用于位选择

- **WHEN** 循环体包含 `assign out[i] = in[i];`
- **THEN** 展开后 genvar 替换为 `assign out[0] = in[0];`, `assign out[1] = in[1];` 等
