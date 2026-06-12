## ADDED Requirements

### Requirement: ExprWalker 模块存在
项目 SHALL 在 `analysis/expr_walker.py` 中提供表达式信号引用提取功能，使用 tree-sitter 解析表达式文本并返回其中引用的信号名列表。

#### Scenario: 模块导入
- **WHEN** 执行 `from analysis.expr_walker import ExprWalker`
- **THEN** 成功导入 `ExprWalker` 类

### Requirement: 基本信号引用提取
`ExprWalker.extract_signal_refs(expr_text)` SHALL 返回 `list[str]`，包含表达式文本中所有 `simple_identifier` 和 `hierarchical_identifier`，按在源码中出现顺序排列（去重保持首次出现顺序）。

#### Scenario: 简单赋值表达式
- **WHEN** 调用 `extract_signal_refs("a + b")`
- **THEN** 返回 `["a", "b"]`

#### Scenario: 含常量和运算符的表达式
- **WHEN** 调用 `extract_signal_refs("data[7:0] & 8'hFF")`
- **THEN** 返回 `["data"]`（数字常量 `8'hFF` 被过滤）

#### Scenario: 拼接表达式
- **WHEN** 调用 `extract_signal_refs("{carry, sum}")`
- **THEN** 返回 `["carry", "sum"]`

#### Scenario: 三目运算符
- **WHEN** 调用 `extract_signal_refs("sel ? a : b")`
- **THEN** 返回 `["sel", "a", "b"]`

### Requirement: 关键字过滤
`ExprWalker.extract_signal_refs()` SHALL 过滤掉 Verilog/SystemVerilog 关键字（如 `posedge`、`negedge`、`or`、`and`、`not`、`begin`、`end` 等）和数字常量（如 `8'hFF`、`32'd1`、`'b0`）。

#### Scenario: 敏感列表文本
- **WHEN** 调用 `extract_signal_refs("posedge clk or negedge rst_n")`
- **THEN** 返回 `["clk", "rst_n"]`（`posedge`、`negedge`、`or` 被过滤）

### Requirement: 分析引擎集成 ExprWalker
`fan_in.py` 的 `_extract_signal_names()`、`clock_analyzer.py` 的赋值信号提取、`always_classify.py` 的赋值/读取信号提取逻辑 SHALL 改为调用 `ExprWalker.extract_signal_refs()`，删除各自的正则分割实现。

#### Scenario: fan_in 信号追踪使用 AST 提取
- **WHEN** `_trace_assign_rhs` 需要从 assign RHS 提取驱动信号
- **THEN** 调用 `ExprWalker.extract_signal_refs(assign.rhs)` 而非 `re.split(r'[\s+\-*/&|^%<>()\[\]:]+', part)`
