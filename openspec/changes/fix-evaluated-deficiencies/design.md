## Context

代码库近期评估识别出 6 类系统性不足，分布在测试层、文档层、索引层和分析引擎层：

- **测试层**：`test_extract_instances` 因传入 root_node 而非 module_declaration 节点导致遍历失败；`test_no_ports_module` 因非 ANSI header 无 `module_ansi_header` 节点导致 None 解引用崩溃
- **文档层**：README 列出不存在的 `rtl_list_modules` 工具，`rtl_hierarchy` 分类错误，Level3 工具列表缺失
- **索引层**：`indexer/__init__.py` 的 `__all__` 导出列表包含不存在的 `VerilogParser`
- **分析引擎层**：`rtl_port_dataflow` 仅能实现 fan-in 模式穿透、FSM 检测依赖 case+next_state 模式、CDC 检测为纯启发式无同步器识别

当前架构：四层分层（indexer → database → analysis → tools），tree-sitter 解析，SQLite 持久化。

## Goals / Non-Goals

**Goals:**
- 修复全部测试失败，确保 100% 测试通过率
- 同步 README 与代码实际状态
- 消除索引层导出不一致
- 实现 `rtl_port_dataflow` 的完整跨层级双向追踪
- 扩展 FSM 检测支持非 case 编码风格（one-hot 直接赋值、二进制编码 if-else 链）
- 引入同步器识别提升 CDC 检测精度

**Non-Goals:**
- 不新增 tree-sitter 语法节点类型（沿用现有 AST 结构）
- 不修改 MCP 工具接口签名（保持向后兼容）
- 不引入新的外部依赖
- 不重构现有索引存储结构

## Decisions

### 1. 测试修复策略

**选择**: `test_extract_instances` 改为从 source_file AST 中先找到 `module_declaration` 节点再传入提取器；`test_no_ports_module` 在 helper 中增加 `module_declaration` 节点查找的 fallback（先找 `module_ansi_header`，再找 `module_nonansi_header`，都找不到时跳过测试并 warn）。

**替代方案**: 修改提取器支持 source_file 节点 → 拒绝，提取器语义是"从 module body 提取"，不应为测试特例改变语义。

### 2. `rtl_port_dataflow` 跨层级追踪

**选择**: 在 `DataflowTracer` 中新增 `trace_port_dataflow(module_name, port_name, direction)` 方法。`direction="input"` 时从端口向内追踪 fan-in（穿透子模块例化的输出端口）；`direction="output"` 时向外追踪 fan-out（穿透子模块例化的输入端口）。追踪深度通过 `max_depth` 参数控制。

**替代方案**: 在 tools 层直接拼接 fan_in + fan_out 结果 → 拒绝，拼接无法处理端口穿透（例化边界处需要映射形式端口 ↔ 实际信号），必须在 tracer 层实现。

### 3. FSM 非 case 编码检测

**选择**: 新增 `FSMDetector._detect_fsm_by_register()` 方法，不依赖 case 语句，改为：
1. 扫描所有时序 always 块，提取被赋值的寄存器（状态寄存器候选）
2. 检查该寄存器是否在组合逻辑中被读取（条件判断或赋值右值）
3. 若组合逻辑对该寄存器有分支行为（if-else 或 case），判定为 FSM
4. 从分支条件/赋值中提取状态转移

**替代方案**: 基于正则扫描 `if (state == ...)` 模式 → 拒绝，正则不可靠，tree-sitter AST 遍历更准确。

### 4. CDC 同步器识别

**选择**: 在 `ClockAnalyzer` 中新增 `_detect_synchronizer(module_def, signal_name)` 方法，识别两种常见同步器：
1. **双触发器同步器**：信号跨时钟域后进入两个连续的时序 always 块（同一目标时钟域），第一个触发器输出仅被第二个触发器读取
2. **握手同步器**：包含请求-应答信号对（`req`/`ack`），在各自时钟域中有对应的锁存/采样逻辑

CDC 检测结果中标记已同步信号 vs 未同步信号。

**替代方案**: 基于完整形式验证的 CDC 检查 → 拒绝，需要 SAT/SMT 求解器，与项目轻量级定位不符。

## Risks / Trade-offs

- **FSM 检测误报**：基于寄存器+分支的检测可能将普通计数器误判为 FSM → 增加状态数阈值过滤（≥2 个不同状态才判定为 FSM）
- **同步器识别漏报**：仅覆盖双触发器和握手两种常见模式，其他同步器（如异步 FIFO）无法识别 → 在文档中明确标注限制
- **端口穿透性能**：跨层级追踪可能在大设计（>1000 模块）中消耗较长时间 → 默认 max_depth=5，可配置
- **测试覆盖**：新增检测逻辑需要大量测试用例覆盖边界情况 → 为每个新增功能配套测试
