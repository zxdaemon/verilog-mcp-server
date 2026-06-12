## ADDED Requirements

### Requirement: PyslangExtractor 提取 generate 展开实例
`PyslangExtractor` SHALL 从 pyslang elaborated design 中提取所有 generate 展开后的实例。每个实例记录：展开后的实例名（如 `top.genblk1[0].u_cpu`）、原始模块名、父实例路径、generate 条件表达式（如有）。

#### Scenario: for-generate 展开实例
- **WHEN** 源码有 `generate for (i=0; i<4; i++) begin: genblk cpu u_cpu(...); end endgenerate`
- **THEN** 提取 4 个实例：`top.genblk[0].u_cpu`、`top.genblk[1].u_cpu`、`top.genblk[2].u_cpu`、`top.genblk[3].u_cpu`

#### Scenario: if-generate 展开实例
- **WHEN** 源码有 `generate if (WIDTH > 8) begin: wide_mode ... end else begin: narrow_mode ... end endgenerate`
- **THEN** 提取实际展开的实例（如 `top.wide_mode.u_adder`），记录条件 `WIDTH > 8`

### Requirement: PyslangExtractor 提取参数求值后的信号位宽
`PyslangExtractor` SHALL 从 pyslang elaborated design 中提取所有信号的求值后位宽。对于 `parameter WIDTH = 32; reg [WIDTH-1:0] data;`，提取 `data` 的实际位宽 `[31:0]`。

#### Scenario: 参数化位宽求值
- **WHEN** 模块声明 `parameter WIDTH = 32; reg [WIDTH-1:0] data;`
- **THEN** 提取信号 `data` 的 `resolved_width` 为 `"[31:0]"`

#### Scenario: 表达式位宽求值
- **WHEN** 模块声明 `parameter A = 8; parameter B = 16; reg [A+B-1:0] bus;`
- **THEN** 提取信号 `bus` 的 `resolved_width` 为 `"[23:0]"`

### Requirement: PyslangExtractor 提取宏展开映射
`PyslangExtractor` SHALL 提取 `define 宏定义及其展开使用位置。记录：宏名、宏定义位置、各展开使用位置、展开后的文本。

#### Scenario: 宏定义与展开
- **WHEN** 源码中有 `` `define ADD(a,b) (a+b) `` 和 `` assign c = `ADD(x,y); ``
- **THEN** 提取宏 `ADD` 的定义位置，以及展开使用位置，展开后文本为 `(x+y)`

### Requirement: PyslangExtractor 提取完整层次树
`PyslangExtractor` SHALL 从 pyslang elaborated design 中提取完整的模块层次树，包含：顶层模块、所有例化（含 generate 展开）、参数化模块的实例特定参数值。

#### Scenario: 参数化模块实例
- **WHEN** `cpu #(.WIDTH(64)) u_cpu(...)` 被例化
- **THEN** 提取实例 `u_cpu` 的实际参数 `WIDTH = 64`

#### Scenario: 多层次 generate 展开
- **WHEN** 嵌套 generate（外层 for，内层 if）
- **THEN** 提取所有展开后的实例，路径如 `top.outer[0].inner.u_mod`
