## ADDED Requirements

### Requirement: 基于状态寄存器识别的通用 FSM 检测
`FSMDetector` SHALL 新增 `_detect_fsm_by_register()` 方法，不依赖 case 语句，而是通过识别状态寄存器 + 状态转移逻辑来检测 FSM。检测逻辑：
1. 扫描时序 always 块，提取被非复位赋值的寄存器（状态寄存器候选）
2. 检查该寄存器是否在组合逻辑块中被读取（作为条件或赋值右值）
3. 若组合逻辑对该寄存器有 ≥2 个不同分支结果，判定为 FSM
4. 从分支中提取状态值和转移目标

#### Scenario: One-hot 编码 FSM（无 case 语句）
- **WHEN** 模块中存在时序块 `state_reg <= next_state`，且组合块中 `if (state_reg[0]) next_state = 4'b0010; else if (state_reg[1]) next_state = 4'b0100;`
- **THEN** `state_reg` 被识别为状态寄存器，提取出 one-hot 编码的状态和转移关系

#### Scenario: 二进制编码 if-else FSM
- **WHEN** 模块中存在时序块 `st <= nst`，组合块中 `if (st == 2'b00) nst = 2'b01; else if (st == 2'b01) nst = 2'b10;`
- **THEN** `st` 被识别为状态寄存器，提取出状态 `S0=00`、`S1=01`、`S2=10` 和转移关系

### Requirement: 状态寄存器候选过滤
通用 FSM 检测 SHALL 排除明显非 FSM 的寄存器：仅有一个赋值目标、无分支行为、或状态值为连续递增/递减（计数器模式）。

#### Scenario: 计数器不被误判为 FSM
- **WHEN** 模块中存在 `counter <= counter + 1` 且 `counter` 在组合逻辑中仅参与算术运算
- **THEN** `counter` 不被识别为状态寄存器

#### Scenario: 移位寄存器不被误判为 FSM
- **WHEN** 模块中存在 `shift_reg <= {shift_reg[2:0], shift_in}`
- **THEN** `shift_reg` 不被识别为状态寄存器

### Requirement: 新旧检测算法并存
`FSMDetector.detect()` SHALL 同时运行原有 case+next_state 检测和新增的通用寄存器检测，合并结果去重。同一个 FSM 被两种算法同时检测到时，优先使用 case 模式的结果（通常更完整）。

#### Scenario: 标准 case 模式 FSM
- **WHEN** 模块中同时满足 case+next_state 模式和寄存器识别模式
- **THEN** 仅返回一个 FSM 结果，使用 case 模式提取的状态名和转移表

#### Scenario: 无 case 语句的 if-else FSM
- **WHEN** 模块仅满足寄存器识别模式，不满足 case+next_state 模式
- **THEN** 返回通用 FSM 检测结果，状态名使用自动生成的 `S0`、`S1`... 或二进制值
