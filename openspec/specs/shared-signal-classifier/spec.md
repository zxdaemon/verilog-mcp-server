## ADDED Requirements

### Requirement: SignalClassifier 模块存在
项目 SHALL 在 `analysis/signal_classifier.py` 中提供 `SignalClassifier` 类，集中实现时钟和复位信号的启发式识别逻辑。该类构造函数接受 `IndexStore` 实例。

#### Scenario: 模块导入
- **WHEN** 执行 `from analysis.signal_classifier import SignalClassifier`
- **THEN** 成功导入 `SignalClassifier` 类

### Requirement: 时钟候选判断
`SignalClassifier.is_clock(signal_name, module_def)` SHALL 返回 `bool`，基于以下启发式规则：
1. 信号名包含已知时钟模式（`clk`、`clock`、`clkp`、`clkn`、`sys_clk`、`ref_clk`、`mclk`、`pclk`、`hclk`、`aclk`）
2. 信号是模块的 input 端口且不匹配已知复位模式
3. 信号出现在模块中 2 个及以上 always 块的敏感列表中

#### Scenario: 命名匹配时钟信号
- **WHEN** 调用 `is_clock("sys_clk", module_def)` 且信号名包含已知时钟模式
- **THEN** 返回 `True`

#### Scenario: input 端口且非复位信号
- **WHEN** 调用 `is_clock("core_clk_2x", module_def)` 且该信号是 input 端口、不匹配复位模式
- **THEN** 返回 `True`

#### Scenario: 非时钟信号
- **WHEN** 调用 `is_clock("data_valid", module_def)` 且该信号不匹配时钟模式、非 input 端口、不在多个 always 敏感列表中
- **THEN** 返回 `False`

### Requirement: 复位候选判断
`SignalClassifier.is_reset(signal_name)` SHALL 返回 `bool`，基于信号名是否包含已知复位模式（`rst`、`rst_n`、`reset`、`reset_n`、`rstn`、`nrst` 等）。

#### Scenario: 命名匹配复位信号
- **WHEN** 调用 `is_reset("rst_n")`
- **THEN** 返回 `True`

#### Scenario: 非复位信号
- **WHEN** 调用 `is_reset("data_out")`
- **THEN** 返回 `False`

### Requirement: 复位极性推断
`SignalClassifier.infer_reset_polarity(signal_name, edge)` SHALL 返回 `"high"` 或 `"low"`。规则：信号名以 `_n`/`_b` 结尾 → low；信号名包含 `rst_n` → low；边沿为 `negedge` → low；否则 high。

#### Scenario: 低有效复位信号
- **WHEN** 调用 `infer_reset_polarity("rst_n", "posedge")`
- **THEN** 返回 `"low"`

#### Scenario: negedge 触发
- **WHEN** 调用 `infer_reset_polarity("rst", "negedge")`
- **THEN** 返回 `"low"`

### Requirement: 分析引擎统一使用 SignalClassifier
`clock_analyzer.py`、`always_classify.py`、`fsm_detector.py` 中的时钟/复位判断逻辑 SHALL 改为调用 `SignalClassifier`，删除各自独立维护的 `_CLOCK_PATTERNS`、`_RESET_PATTERNS`、`_is_clock_signal`、`_is_clock_candidate` 等重复实现。

#### Scenario: clock_analyzer 使用统一分类器
- **WHEN** `ClockAnalyzer` 分析模块时钟域
- **THEN** 其调用 `SignalClassifier.is_clock()` 判断时钟候选，调用 `SignalClassifier.infer_reset_polarity()` 推断极性
