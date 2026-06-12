## 1. 数据模型与引擎

- [x] 1.1 创建 `analysis/clock_tree.py`，定义 `ClockModuleInfo`、`ClockDomainGroup`、`ClockTreeResult` dataclass
- [x] 1.2 实现 `ClockTreeBuilder.__init__()` — 接收 IndexStore 和 gated_clock_patterns
- [x] 1.3 实现 `ClockTreeBuilder._trace_clock_to_root()` — 沿 instance_path 向上查 port_connections 映射时钟名
- [x] 1.4 实现 `ClockTreeBuilder._is_gated_clock_cell()` — 模块名模式匹配
- [x] 1.5 实现 `ClockTreeBuilder._build_module_tree_for_domain()` — 将时钟域内扁平模块列表重建为层次树
- [x] 1.6 实现 `ClockTreeBuilder.build()` — DFS 遍历层次树 → 分析时钟 → 按时钟名分组 → 构建每域树
- [x] 1.7 实现 `ClockTreeBuilder.format_text_tree()` — ASCII 树状图格式化
- [x] 1.8 实现 `ClockTreeBuilder.format_mermaid()` — Mermaid flowchart 格式化
- [x] 1.9 更新 `analysis/__init__.py` 导出 `ClockTreeBuilder`

## 2. MCP Tool 注册

- [x] 2.1 在 `tools/level3_analysis.py` 的 `register_tools()` 中创建 `ClockTreeBuilder` 实例
- [x] 2.2 注册 `rtl_clock_tree` tool（含 docstring 和异常处理）

## 3. 测试

- [x] 3.1 编写 `TestClockTree` 测试类 — 构建多层多时钟域的 fake IndexStore
- [x] 3.2 测试时钟名穿透追踪（child.clk → parent.sys_clk）
- [x] 3.3 测试时钟域分组正确性
- [x] 3.4 测试 ASCII 输出包含预期树字符和模块名
- [x] 3.5 测试 Mermaid 输出包含 `flowchart TD` 和 `subgraph`
- [x] 3.6 测试门控时钟检测
- [x] 3.7 测试顶层模块不存在时的错误处理

## 4. 验证

- [x] 4.1 `uv run pytest tests/test_level3_tools.py -v` — 确认全部测试通过
- [x] 4.2 对 openc910 执行 `rtl_clock_tree("soc")` 验证输出正确性
- [x] 4.3 执行 `rtl_clock_tree("soc", output_format="mermaid")` 验证 Mermaid 输出可渲染
- [x] 4.4 `uv run pytest tests/ -v` 确认无回归
