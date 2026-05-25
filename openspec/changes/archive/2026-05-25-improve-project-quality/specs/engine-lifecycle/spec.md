## ADDED Requirements

### Requirement: Level 3 引擎在 register_tools 时创建

`tools/level3_analysis.py` 的 `register_tools()` SHALL 在函数体顶部（tool 装饰器定义之前）创建所有分析引擎实例：

- `fsm_detector = FSMDetector(index_store)`
- `clock_analyzer = ClockAnalyzer(index_store)`
- `always_classifier = AlwaysClassifier(index_store)`

每次 MCP tool 调用 SHALL 复用这些已创建的实例，而非新建。

#### Scenario: FSM 检测不重复创建引擎

- **WHEN** MCP 客户端连续调用 `rtl_detect_fsm` 两次
- **THEN** 两次调用使用同一个 `FSMDetector` 实例（由 `register_tools` 创建）

### Requirement: Level 2 引擎创建模式不变

`tools/level2_relation.py` 的 `register_tools()` 已采用提前创建模式，SHALL 保持当前行为不变。

#### Scenario: Level 2 引擎实例仍为一次创建

- **WHEN** 服务器启动时执行 `create_app(config)`
- **THEN** `HierarchyBuilder`、`DataflowTracer`、`CrossReference` 各创建一次
