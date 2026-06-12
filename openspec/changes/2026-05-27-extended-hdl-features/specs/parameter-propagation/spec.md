## ADDED Requirements

### Requirement: 参数值传播

`analysis/param_propagator.py` SHALL 从顶层模块开始 BFS 遍历例化树，传播参数实际值。

#### Scenario: 参数通过例化传递

- **WHEN** 顶层 `top` 例化 `sub #(.WIDTH(16)) u_sub()`，`sub` 有 `parameter WIDTH = 8`
- **THEN** `u_sub` 的 `WIDTH` 实际值为 16

#### Scenario: 使用默认值

- **WHEN** 例化 `sub u_sub()` 未覆盖参数，`sub` 有 `parameter WIDTH = 8`
- **THEN** `u_sub` 的 `WIDTH` 实际值为 8

### Requirement: 简单算术表达式求值

`analysis/param_propagator.py` SHALL 支持参数值中的简单算术表达式求值。

#### Scenario: 参数引用其他参数

- **WHEN** `parameter DEPTH = 16, ADDR_WIDTH = $clog2(DEPTH)`
- **THEN** `ADDR_WIDTH` 求值为 4（如果 $clog2 已实现）

#### Scenario: 加减乘除

- **WHEN** `parameter SIZE = WIDTH * 2 + 1`
- **THEN** 如果 `WIDTH` 已知为 8，则 `SIZE` 求值为 17

### Requirement: 未解析参数标记

`analysis/param_propagator.py` SHALL 对无法求值的参数标记为 unresolved。

#### Scenario: 条件表达式

- **WHEN** `parameter X = COND ? A : B` 且 `COND` 不是常量
- **THEN** `X` 标记为 "unresolved"，保留原始文本

### Requirement: Defparam 合并

`analysis/param_propagator.py` SHALL 在参数传播时考虑 defparam 覆盖。

#### Scenario: defparam 优先级最高

- **WHEN** 例化参数列表值为 4，defparam 值为 16
- **THEN** 最终参数值为 16（defparam > 例化参数 > 默认值）

### Requirement: 参数值查询

`database/index_store.py` SHALL 提供参数传播结果的查询方法。

#### Scenario: 查询模块实例的参数实际值

- **WHEN** 调用 `index_store.get_propagated_params("top.u_sub")`
- **THEN** 返回 `{"WIDTH": "16", "DEPTH": "8", ...}`
