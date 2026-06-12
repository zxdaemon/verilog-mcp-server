## ADDED Requirements

### Requirement: DcAdapter Design Compiler 综合报告
`DcAdapter` SHALL 生成 DC Tcl 脚本，执行 `analyze` → `elaborate` → `compile` → 生成报告。报告包括：`report_hierarchy`（综合后层次树）、`report_area`（资源使用）、`report_clock`（时钟域）、`report_constraint`（约束）。解析文本报告，提取结构化数据。

#### Scenario: DC 层次报告
- **WHEN** DC 综合后 `report_hierarchy` 包含 `top → cpu → alu`
- **THEN** 解析输出层次树 `top → cpu → alu`，含每个模块的面积和单元数

#### Scenario: DC 时钟域报告
- **WHEN** DC 综合后 `report_clock` 列出 `clk_fast (500MHz)` 和 `clk_slow (100MHz)`
- **THEN** 解析输出两个时钟域的名称、频率、源端口

### Requirement: PtAdapter PrimeTime 时序报告
`PtAdapter` SHALL 生成 PrimeTime Tcl 脚本，执行 `read_verilog` → `read_lib` → `read_sdc` → `update_timing` → `report_timing`。解析时序路径报告，提取：路径起点、路径终点、总延迟、setup slack、hold slack、关键路径上的单元列表、时钟偏斜。

#### Scenario: PT 关键路径分析
- **WHEN** `report_timing` 显示从 `reg_a/CK` 到 `reg_b/D` 的路径延迟 3.2ns，slack -0.5ns
- **THEN** 提取路径起点 `reg_a/CK`、终点 `reg_b/D`、延迟 `3.2ns`、slack `-0.5ns`

#### Scenario: PT 时钟偏斜报告
- **WHEN** `report_clock_timing -type skew` 显示 `clk` 的 skew 为 0.15ns
- **THEN** 提取时钟名 `clk`、偏斜值 `0.15ns`、最大/最小到达时间

### Requirement: VcsAdapter 设计结构查询
`VcsAdapter` SHALL 通过两种方式获取设计结构信息：
1. 解析 VCS 编译日志（`vlogan`/`vcs` 输出），提取模块层次和端口信息
2. 生成 UCLI 脚本，在仿真启动后查询设计对象（`scope` / `show` 命令）

解析结果提取：模块层次树、信号列表、端口方向、参数值。

#### Scenario: VCS 编译日志解析
- **WHEN** VCS 编译日志包含 `Compiling module 'cpu' (cpu.v, 12)`
- **THEN** 提取模块名 `cpu`、文件 `cpu.v`、行号 `12`

### Requirement: LintAdapter SpyGlass/VC Lint 报告解析
`LintAdapter` SHALL 解析 SpyGlass XML/JSON 报告和 VC Lint 结构化报告。提取：规则名、严重程度（error/warning/info）、文件路径、行号、问题描述、修复建议、类别（lint/cdc/rdc/dft）。

#### Scenario: SpyGlass CDC 报告
- **WHEN** SpyGlass 报告 `CDC-1: Cross-domain path from 'clk_a' to 'clk_b'`
- **THEN** 提取规则 `CDC-1`、类别 `cdc`、源时钟 `clk_a`、目标时钟 `clk_b`

#### Scenario: VC Lint 报告
- **WHEN** VC Lint 报告 `LINT_UNUSED: Signal 'bar' is never read`
- **THEN** 提取规则 `LINT_UNUSED`、信号名 `bar`、类别 `lint`

### Requirement: 商业工具 Tcl 脚本安全生成
`DcAdapter` 和 `PtAdapter` 生成的 Tcl 脚本 SHALL 对项目路径使用 `shlex.quote` 或 Tcl 的 `list` 命令转义，防止命令注入。脚本中不直接拼接用户输入。

#### Scenario: 路径含特殊字符
- **WHEN** 项目路径为 `/path/with spaces/project`
- **THEN** Tcl 脚本中路径正确转义，不因空格导致语法错误
