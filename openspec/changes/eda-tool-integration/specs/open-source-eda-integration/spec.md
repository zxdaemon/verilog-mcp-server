## ADDED Requirements

### Requirement: SlangAdapter 调用与解析
`SlangAdapter` SHALL 生成 slang 命令行调用，参数包括：项目文件列表（`-f filelist.f` 或单个文件）、顶层模块（`--top`）、JSON AST 输出（`--json`）。解析 slang JSON 输出，提取：generate 展开后的层次树、参数求值后的信号位宽、宏展开信息、完整 interface 定义。

#### Scenario: slang 生成层次树
- **WHEN** 调用 `SlangAdapter.run()` 处理包含 `generate for (i=0; i<4; i++)` 的项目
- **THEN** 解析输出包含 `u_mod[0]`、`u_mod[1]`、`u_mod[2]`、`u_mod[3]` 四个展开实例

#### Scenario: slang 参数求值
- **WHEN** 源码中有 `parameter WIDTH = 32; reg [WIDTH-1:0] data;`
- **THEN** 解析输出中信号 `data` 的位宽为 `[31:0]`（已求值）

### Requirement: YosysAdapter 综合报告解析
`YosysAdapter` SHALL 生成 Yosys Tcl 脚本，执行以下命令序列：`read_verilog -sv` → `hierarchy` → `proc` → `fsm_detect` → `fsm_extract` → `check` → `clk2fflogic` → `opt` → `write_json`。解析 Yosys JSON 网表和日志，提取：FSM 列表（状态数、编码方式）、组合逻辑环告警、门控时钟信号、LUT/FF/Memory 资源统计。

#### Scenario: Yosys FSM 提取
- **WHEN** Yosys 综合后 `fsm_detect` 识别到状态机
- **THEN** 解析输出包含 FSM 名称、状态数、状态列表、转移条件

#### Scenario: Yosys 组合逻辑环检测
- **WHEN** 设计中存在组合逻辑环
- **THEN** `check` 命令输出告警，解析器提取环涉及的信号列表

### Requirement: VerilatorAdapter lint 报告解析
`VerilatorAdapter` SHALL 调用 `verilator --lint-only` 生成 lint 报告。解析报告中的警告和错误，提取：文件路径、行号、严重程度（warning/error）、问题描述、问题类别（UNUSED/SYNCASYNCASGN/WIDTH/etc）。

#### Scenario: Verilator 未使用信号检测
- **WHEN** Verilator 报告 `Warning-UNUSED: Signal 'foo' is never used`
- **THEN** 提取信号名 `foo`、文件路径、行号、类别 `UNUSED`

### Requirement: 开源工具零依赖原则
开源 EDA 工具适配器 SHALL 通过系统 PATH 检测工具可用性，不将工具作为 Python 包依赖。适配器代码在工具不可用时优雅跳过，不影响系统其他功能。

#### Scenario: 无 slang 环境
- **WHEN** 系统 PATH 中无 `slang` 且配置中启用了 slang
- **THEN** `SlangAdapter.check_available()` 返回 `False`，系统正常工作
