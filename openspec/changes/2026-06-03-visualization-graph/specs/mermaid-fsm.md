## ADDED Requirements

### Requirement: FSM 提供 Mermaid 状态图输出

`analysis/fsm_detector.py` 的 `FSM` dataclass SHALL 提供 `format_mermaid() -> str` 方法，输出 Mermaid stateDiagram-v2 语法的状态转移图。

`FSMDetector` 类 SHALL 提供 `format_mermaid(module_name) -> str` 方法，检测模块中所有 FSM 并拼接各自的 Mermaid 输出。

#### Scenario: 基本状态图输出

- **WHEN** FSM 包含状态 `IDLE`、`RUN`、`DONE`，转移 `IDLE -> RUN` (条件 `start`)、`RUN -> DONE` (条件 `finish`)
- **THEN** 返回以 `stateDiagram-v2` 开头的字符串
- **AND** 包含 `[*] --> IDLE` 初始转移
- **AND** 包含 `IDLE --> RUN : start` 和 `RUN --> DONE : finish` 带条件标签的转移

#### Scenario: 多 FSM 输出

- **WHEN** 模块包含两个 FSM（如 `main_fsm` 和 `err_fsm`）
- **THEN** 返回两个独立的 `stateDiagram-v2` 块，用空行分隔

#### Scenario: 无转移的状态图

- **WHEN** FSM 只有状态定义，无转移（异常情况）
- **THEN** 输出仅包含状态声明，不含转移边
