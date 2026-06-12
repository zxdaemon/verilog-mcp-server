## ADDED Requirements

### Requirement: FSM 检测器使用驱动/负载关系定位 case 语句
`FSMDetector._build_fsm()` SHALL 通过 `SignalDef.drivers` 找时序块中赋值的寄存器、通过 `SignalDef.loads` 找组合块中引用了该寄存器的 case 表达式，替代原有的纯文本正则 `cases?\s*\(\s*(\w+)\s*\)` 模式匹配。

#### Scenario: 状态寄存器候选识别
- **WHEN** 时序 always 块中 `state <= next_state` 且信号 `state` 的 `drivers` 包含此赋值
- **THEN** `state` 被识别为状态寄存器候选，且 `next_state` 被识别为次态信号

#### Scenario: case 表达式与状态寄存器关联
- **WHEN** 信号 `state` 的 `loads` 中包含来自组合 always 块的 case 表达式引用
- **THEN** 该组合块被识别为 `state` 的状态转移逻辑块

### Requirement: 支持 casez/casex 关键字
FSM 检测器 SHALL 识别 `casez` 和 `casex` 语句，与 `case` 同等对待。

#### Scenario: casez 语句中的状态转移
- **WHEN** 组合块包含 `casez (state) 3'b1??: next_state = S1; ...`
- **THEN** 系统正确提取状态 `3'b1??` 和转移 `→ S1`

### Requirement: 不依赖 next_ 命名约定的状态寄存器识别
FSM 检测器 SHALL 通过以下规则识别状态寄存器，不依赖 `next_` 前缀：
1. 时序 always 块中非 reset 赋值的寄存器（从 `drivers` 获取）
2. 该寄存器在组合块中作为 case 表达式出现（从 `loads` 获取）

#### Scenario: 非标准命名的状态寄存器
- **WHEN** 时序块 `cur_st <= nxt_st` 且 `cur_st` 在组合块中被 `case(cur_st)` 引用
- **THEN** `cur_st` 被正确识别为状态寄存器（即使命名不以 `state` 或 `next_` 开头）
