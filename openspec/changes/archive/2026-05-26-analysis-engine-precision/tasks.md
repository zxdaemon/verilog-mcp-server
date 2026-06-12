## 1. SystemVerilog always 关键字识别

- [x] 1.1 在 `signal_extractor.py` 的 `extract_always_blocks()` 中新增对 `always_comb_construct`、`always_ff_construct`、`always_latch_construct` 节点类型的处理
- [x] 1.2 `always_comb_construct` → `block_type="combinational"`, sensitivity_list=`"@*"`, 提取块体文本
- [x] 1.3 `always_ff_construct` → `block_type="sequential"`, 从 event_control 子节点提取敏感列表
- [x] 1.4 `always_latch_construct` → `block_type="latch"`, 从 event_control 子节点（如存在）或记录 `"@*"`
- [x] 1.5 保持原有 `always_construct` 处理逻辑不变（向后兼容）

## 2. 统一信号分类器

- [x] 2.1 创建 `analysis/signal_classifier.py`，定义 `SignalClassifier` 类
- [x] 2.2 实现 `is_clock(signal_name, module_def) -> bool`：合并三处 `_CLOCK_PATTERNS` 规则
- [x] 2.3 实现 `is_reset(signal_name) -> bool`：合并 `_RESET_PATTERNS` 规则
- [x] 2.4 实现 `infer_reset_polarity(signal_name, edge) -> str`：合并极性推断规则
- [x] 2.5 更新 `clock_analyzer.py`：删除自有 `_CLOCK_PATTERNS`/`_RESET_PATTERNS`/`_is_clock_candidate`/`_is_reset_candidate`/`_infer_reset_polarity`，改为注入并使用 `SignalClassifier`
- [x] 2.6 更新 `always_classify.py`：删除自有 `_is_clock_signal`，改为注入并使用 `SignalClassifier`
- [x] 2.7 更新 `fsm_detector.py`：删除自有 `_CLOCK_PATTERNS`，改为注入并使用 `SignalClassifier`

## 3. AST 表达式遍历器

- [x] 3.1 创建 `analysis/expr_walker.py`，定义 `ExprWalker` 类
- [x] 3.2 实现 `extract_signal_refs(expr_text: str) -> list[str]`：用 tree-sitter 解析表达式片段，递归遍历收集 `simple_identifier` 和 `hierarchical_identifier`
- [x] 3.3 实现关键字过滤：排除 Verilog/SystemVerilog 关键字和数字常量
- [x] 3.4 更新 `fan_in.py`：`_extract_signal_names()` 改为调用 `ExprWalker.extract_signal_refs()`
- [x] 3.5 更新 `clock_analyzer.py`：`_extract_assigned_signals()` 中信号提取改为调用 `ExprWalker.extract_signal_refs()`
- [x] 3.6 更新 `always_classify.py`：`_extract_assigned_signals()` 和 `_extract_read_signals()` 中信号提取改为调用 `ExprWalker.extract_signal_refs()`

## 4. AST-based 驱动/负载提取

- [x] 4.1 在 `signal_extractor.py` 的 `SignalExtractor` 中新增 `extract_drivers_and_loads(always_block_node, source_text) -> tuple[list[DriverInfo], list[LoadInfo]]`
- [x] 4.2 实现 `nonblocking_assignment` 节点遍历：LHS → driver，RHS expression → loads（用 ExprWalker）
- [x] 4.3 实现 `blocking_assignment` 节点遍历：同上
- [x] 4.4 实现 `if_statement` 条件表达式中的信号引用 → loads
- [x] 4.5 实现 `case_statement` 表达式中的信号引用 → loads
- [x] 4.6 实现 `event_control`（敏感列表）中的信号引用 → loads
- [x] 4.7 实现 `continuous_assign` 的处理：net_lvalue → driver, expression → loads
- [x] 4.8 在 `IndexBuilder.build()` 中集成：信号提取后、`add_module` 前调用 `extract_drivers_and_loads()`，将结果写入对应 `SignalDef`
- [x] 4.9 过滤 for 循环变量：当赋值节点的祖先为 `for_statement` 时，不将循环变量标记为信号驱动

## 5. FSM 检测器重构

- [x] 5.1 修改 `_find_state_reg_candidates()`：使用 `SignalDef.drivers` 找时序块中非 reset 赋值的寄存器，而非仅依赖 `next_` 前缀
- [x] 5.2 修改 `_build_fsm()`：使用 `SignalDef.loads` 找组合块中 case 表达式引用状态寄存器的位置，替代纯正则 `cases?\s*\((\w+)\s*\)`
- [x] 5.3 保留 `_extract_case_items()` 和 `_extract_transitions()` 的正则逻辑（处理 case body 文本结构，正则已足够）
- [x] 5.4 支持 `casez`/`casex` 关键字：在定位到 case 块的组合块文本中，正则扩展为 `case[zx]?\s*\(`
- [x] 5.5 删除 `fsm_detector.py` 中 `_find_case_in_text()` 的纯正则 case 定位逻辑

## 6. 测试与验证

- [x] 6.1 为 `SignalClassifier` 编写单元测试：时钟/复位候选判断、极性推断的典型场景
- [x] 6.2 为 `ExprWalker` 编写单元测试：基本表达式、拼接、三目、含常量、含关键字的场景
- [x] 6.3 为 AST 驱动/负载提取编写测试：assign 驱动、always 块驱动、条件表达式负载、敏感列表负载
- [x] 6.4 为 `always_comb`/`always_ff`/`always_latch` 提取编写测试
- [x] 6.5 更新现有 `test_level3_tools.py` 中受影响的测试用例，确保通过
- [x] 6.6 运行全量测试套件确认无回归：`uv run pytest tests/ -v`
