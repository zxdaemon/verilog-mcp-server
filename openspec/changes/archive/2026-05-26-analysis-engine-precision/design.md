## Context

当前架构在索引层（indexer/）使用 tree-sitter 精确解析 Verilog/SystemVerilog AST，但在分析层（analysis/）退化为正则表达式和启发式规则。核心矛盾在于 `SignalDef.drivers` 和 `SignalDef.loads` 字段定义但从未在索引阶段填充，导致分析引擎被迫在运行时各自重新解析 always 块文本。此外，时钟/复位信号识别逻辑在三个文件中独立维护。

此设计定义如何在索引阶段用 AST 填充驱动/负载关系，并在分析层统一信号识别和表达式遍历，消除正则依赖。

## Goals / Non-Goals

**Goals:**
- 在 `signal_extractor.py` 中用 tree-sitter AST 遍历填充 `SignalDef.drivers` 和 `SignalDef.loads`
- 创建共享的 `analysis/signal_classifier.py` 统一时钟/复位识别
- 创建 `analysis/expr_walker.py` 提供 AST-based 表达式信号引用提取
- 将 FSM 检测器的 case 语句匹配从正则改为 tree-sitter AST 节点
- 识别 SystemVerilog `always_comb`/`always_ff`/`always_latch` 关键字

**Non-Goals:**
- 不修改 `database/models.py` 的数据模型（DriverInfo/LoadInfo 结构不变）
- 不改变任何 MCP tool 的外部接口（server.py 的 tool 注册不变）
- 不涉及 generate 块展开、interface 端口识别（属于后续 Phase）
- 不实现参数/常量求值

## Decisions

### D1: 驱动/负载提取嵌入 signal_extractor，在 indexer 阶段调用

**选择：** 在 `SignalExtractor` 中新增 `extract_drivers_and_loads(always_block_node, source_text) -> tuple[list[DriverInfo], list[LoadInfo]]` 方法，在 `IndexBuilder.build()` 中对每个 always 块调用并填充到对应 signal。

**替代方案：**
- 在 `analysis/` 层做 AST 遍历 → 放弃。分析层不应直接依赖 AST 节点（tree-sitter 的 Node 对象在索引后已不可用）。
- 创建独立的 `indexer/driver_extractor.py` → 可行但过度拆分。驱动/负载提取与信号提取紧密耦合（需要同一个 always 块节点的 AST 上下文），放在同一个 extractor 中更内聚。

**为什么这是对的：** 索引构建时 tree-sitter 的完整 AST 可用；提取结果序列化为 `DriverInfo`/`LoadInfo` dataclass 后存入 `SignalDef`，后续分析引擎只需读取 dataclass 字段，无需接触 tree-sitter。

### D2: 驱动/负载的 AST 遍历策略 — 基于赋值语句节点类型

**选择：** 在 always 块和 assign 语句中，通过 tree-sitter 的以下节点类型定位驱动和负载：

| 节点类型 | 驱动 (driver) | 负载 (load) |
|----------|--------------|------------|
| `nonblocking_assignment` | 提取 LHS 信号名 | 提取 RHS 中所有 `simple_identifier` |
| `blocking_assignment` | 提取 LHS 信号名 | 提取 RHS 中所有 `simple_identifier` |
| `continuous_assign` (assign) | 提取 net_lvalue | 提取 expression 中所有 `simple_identifier` |
| `if_statement` 中的条件 | — | 条件表达式中的信号 = 负载 |
| `case_statement` 的表达式 | — | case 表达式中的信号 = 负载 |
| `event_control` (敏感列表) | — | 敏感列表中的信号 = 负载 |

**替代方案：**
- 仅匹配 `<=`/`=` 的 LHS → 不够。`if (en) data <= ...` 中 `en` 是负载，需要处理条件表达式中的信号引用。
- 对所有 `expression` 节点做全遍历提取信号 → 太激进。会把 `for (i=0; ...)` 中的 `i` 也标记为信号负载，产生噪声。

**为什么这是对的：** 按赋值/条件语句类型分类提取，既保证覆盖驱动和负载的主要场景，又避免无差别扫描带来的误报。for 循环变量等通过上下文过滤（其父节点是 `for_statement` 时不作为信号负载）。

### D3: 统一时钟识别 — 新建 analysis/signal_classifier.py

**选择：** 提取所有引擎共享的时钟/复位判断逻辑到独立模块：

```python
# analysis/signal_classifier.py
class SignalClassifier:
    def is_clock(self, signal_name: str, module: ModuleDef) -> bool: ...
    def is_reset(self, signal_name: str) -> bool: ...
    def infer_reset_polarity(self, signal_name: str, edge: str) -> str: ...
```

保持现有的启发式规则（命名模式 + 端口类型 + 多 always 块引用频次），但集中维护。

**替代方案：** 将时钟/复位模式做成 config.yaml 可配置 → 过度设计。这些模式在实践中足够通用，极少需要修改。

**为什么这是对的：** 消除三处独立维护的 `_CLOCK_PATTERNS`（clock_analyzer, always_classify, fsm_detector），修改一次即可影响所有引擎。

### D4: 表达式信号引用提取 — 新建 analysis/expr_walker.py

**选择：** 提供 `extract_signal_names(expression_text: str) -> list[str]` 函数，但改为使用 tree-sitter 解析表达式片段而非正则：

```python
# analysis/expr_walker.py
def extract_signal_refs(expr_text: str) -> list[str]:
    """解析表达式文本，返回所有信号引用（simple_identifier/hierarchical_identifier）"""
```

内部实现：用 tree-sitter 的 `parse()` 将表达式片段作为完整 expression 解析，然后递归遍历所有子节点，收集 `simple_identifier` 和 `hierarchical_identifier`，过滤数字常量和关键字。

**重要考量：** 调用方传入的是表达式文本字符串（从 `ModuleDef.assignments[].rhs` 或 `AlwaysBlockInfo.statements[]` 中获取），而非 tree-sitter Node 对象。需要在 walker 内部做一次轻量的 tree-sitter parse。代价是每个表达式一次微解析，但表达式文本通常很短（<200 字符），开销可忽略。

### D5: FSM 检测改用 AST 节点 — 前提条件

**选择：** FSM 检测器的实现需同时访问 AST 节点（`case_statement`、`case_item`）和索引数据（`AlwaysBlockInfo`）。但在当前架构中，`AlwaysBlockInfo` 只存储了文本 `statements`，丢失了 AST 结构。

**方案：** 先通过 D1（驱动/负载提取）将 always 块内的赋值信息结构化存入 `SignalDef.drivers/loads`。FSM 检测器在此基础上：
1. 用 `drivers` 找出时序 always 块中非复位赋值的寄存器 → 状态寄存器候选
2. 用 `loads` 找出组合 always 块中读取 `case(state_reg)` 的信号 → 状态转移源
3. 在组合块的 `statements` 文本中用正则提取 case items 和转移（保留当前 `_extract_case_items` 的正则，因为它处理的是 case body 的文本结构，正则在此处是最简方案；关键改进是 case 语句的*定位*不再依赖正则 `cases?\(...)`, 而是通过 loads 关系确认 case 表达式匹配状态寄存器）

**为什么不完全改为 AST：** `AlwaysBlockInfo.statements` 存储的是截断到 4096 字符的文本而非 AST 子树。要在索引阶段保留 AST 结构需要修改数据模型（如存储 tree-sitter 的 S-expression 或字节偏移），这属于数据模型层面的变更，超出本次范围。当前改进是通过 D1 的 drives/loads 结构间接提升 case 定位精度。

## Risks / Trade-offs

- **Risk:** AST driver/load 提取逻辑可能漏掉非标准 always 块结构 → **Mitigation:** 保留 `AlwaysBlockInfo.statements` 文本字段作为 fallback，分析引擎在 drivers/loads 为空时可回退到当前正则逻辑
- **Risk:** `expr_walker.py` 对每个表达式做 tree-sitter 微解析可能影响大项目的索引构建速度 → **Mitigation:** 表达式文本短小，tree-sitter 解析成本 O(n)；可在 builder 中加进度日志，如果成为瓶颈则缓存常用表达式结果
- **Trade-off:** 统一信号分类器保持启发式规则（命名模式），不会 100% 准确。为完全准确需要 formal property 级别的分析，超出本项目范围
