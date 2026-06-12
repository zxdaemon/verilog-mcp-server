## Why

当前分析引擎（clock_analyzer、always_classify、fsm_detector、fan_in/fan_out）严重依赖正则表达式和启发式规则解析 RTL 代码，而索引层已拥有完整的 tree-sitter AST。`SignalDef.drivers` 和 `SignalDef.loads` 字段自定义以来从未被填充，分析引擎各自维护独立的正则解析逻辑。这导致：信号赋值关系不能被可靠提取、多行表达式被截断、位选择和拼接被错误拆分、FSM 检测依赖命名约定、时钟识别规则在三处独立重复。修复应在索引阶段用 AST 提取驱动/负载关系，统一分析层的信号识别逻辑。

## What Changes

- **新增** AST-based 驱动/负载提取：在 `signal_extractor.py` 中用 tree-sitter 遍历 always 块和 assign 语句的 AST 子节点，填充 `SignalDef.drivers` 和 `SignalDef.loads`，替代分析引擎中各自的正则
- **新增** 统一信号分类器 `analysis/signal_classifier.py`：合并 `clock_analyzer.py`、`always_classify.py`、`fsm_detector.py` 三处独立维护的 `_CLOCK_PATTERNS` / `_RESET_PATTERNS` 和时钟候选判断逻辑
- **新增** AST 表达式遍历器 `analysis/expr_walker.py`：用 tree-sitter 递归遍历 expression 节点提取 `simple_identifier` 信号引用，替换 `fan_in.py:300` 和 `clock_analyzer.py:289` 中的字符串分割/正则
- **修改** FSM 检测器：使用 tree-sitter `case_statement` / `case_item` AST 节点替代正则 `cases?\s*\(...\)` 匹配，支持 `casez`/`casex`，状态寄存器识别不依赖 `next_` 命名约定
- **修改** always 块提取：在 `signal_extractor.py` 中识别 `always_comb_construct`、`always_ff_construct`、`always_latch_construct` 节点类型并设置正确 `block_type`，不再仅依赖敏感列表推断

## Capabilities

### New Capabilities
- `ast-driver-load-extraction`: 索引阶段用 tree-sitter AST 提取信号驱动源和负载端，填充 `SignalDef.drivers` 和 `SignalDef.loads`
- `shared-signal-classifier`: 统一的时钟/复位信号识别模块，所有分析引擎共享同一个实现
- `ast-expression-walker`: 基于 tree-sitter 的表达式信号引用提取，替换正则字符串分割
- `ast-fsm-detection`: 使用 tree-sitter case_statement AST 节点的 FSM 检测，支持 casez/casex，不依赖命名约定
- `sv-always-keywords`: 识别 SystemVerilog 的 always_comb、always_ff、always_latch 关键字

### Modified Capabilities
<!-- None — all changes are new capabilities or internal implementation improvements -->

## Impact

- Affected code:
  - `indexer/signal_extractor.py` — 新增驱动/负载 AST 提取方法，新增 always_comb/ff/latch 识别
  - `analysis/signal_classifier.py` — 新文件，统一时钟/复位识别
  - `analysis/expr_walker.py` — 新文件，AST 表达式遍历
  - `analysis/clock_analyzer.py` — 删除自有 `_CLOCK_PATTERNS`/`_RESET_PATTERNS`，改用 signal_classifier；信号提取改用 expr_walker
  - `analysis/always_classify.py` — 删除自有 `_is_clock_signal`，改用 signal_classifier；赋值/读取信号提取改用 expr_walker
  - `analysis/fsm_detector.py` — 删除自有 `_CLOCK_PATTERNS`；case 匹配改用 tree-sitter AST 节点
  - `analysis/fan_in.py` — `_extract_signal_names` 改用 expr_walker
  - `analysis/fan_out.py` — 敏感列表解析改用 AST 节点
  - `database/models.py` — `SignalDef.drivers`/`SignalDef.loads` 将开始被填充（数据模型不变）
- No API changes, no new dependencies, no breaking changes to MCP tool interfaces
- Existing tests for affected analysis engines will need updates to match new internal implementation
