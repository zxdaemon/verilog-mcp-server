## 1. Mermaid 格式化器

- [ ] 1.1 在 `analysis/hierarchy.py` 的 `HierarchyBuilder` 上添加 `format_mermaid(top_module, max_depth)` 方法
- [ ] 1.2 实现 `_sanitize_id()` 辅助函数，转义 Mermaid 语法特殊字符
- [ ] 1.3 在 `analysis/fsm_detector.py` 的 `FSM` dataclass 上添加 `format_mermaid()` 方法
- [ ] 1.4 在 `analysis/fsm_detector.py` 的 `FSMDetector` 上添加 `format_mermaid(module_name)` 方法
- [ ] 1.5 在 `analysis/fan_in.py` 的 `DataflowTracer` 上添加 `format_mermaid(result, title)` 静态方法
- [ ] 1.6 增强 `analysis/clock_tree.py` 的 `format_mermaid()` 添加主题声明和样式

## 2. GraphData 中间模型与转换器

- [ ] 2.1 创建 `analysis/visualizer.py`，定义 `GraphNode`、`GraphEdge`、`GraphData` dataclass
- [ ] 2.2 实现 `hierarchy_to_graph(root: HierarchyNode) -> GraphData`
- [ ] 2.3 实现 `fsm_to_graph(fsm: FSM) -> GraphData`
- [ ] 2.4 实现 `trace_to_graph(result: TraceResult) -> GraphData`
- [ ] 2.5 实现 `clock_tree_to_graph(result: ClockTreeResult) -> GraphData`

## 3. HTML 交互图谱生成器

- [ ] 3.1 在 `analysis/visualizer.py` 中实现 `HtmlVisualizer` 类
- [ ] 3.2 实现 HTML 模板（vis.js CDN、内联数据、工具栏、详情面板、图例）
- [ ] 3.3 实现默认输出路径逻辑（`.verilog_mcp/visualizations/`）
- [ ] 3.4 实现分组配色（module=蓝, signal=绿, state=橙, clock=紫, cycle=红）

## 4. 统一 MCP 工具

- [ ] 4.1 创建 `tools/visualize.py`，实现 `register_tools(mcp, index_store)` 函数
- [ ] 4.2 实现 `rtl_visualize` MCP 工具，支持 target/diagram_type/output_format/max_depth 参数
- [ ] 4.3 实现 auto 检测逻辑（模块有子例化→hierarchy，有 FSM→fsm，信号名→dataflow）
- [ ] 4.4 修改 `tools/__init__.py` 导出 `register_visualize`
- [ ] 4.5 修改 `server.py` 的 `create_app()` 注册 visualize tools

## 5. 测试

- [ ] 5.1 创建 `tests/test_visualization.py`
- [ ] 5.2 编写 HierarchyBuilder Mermaid 格式化器单元测试
- [ ] 5.3 编写 FSM Mermaid 格式化器单元测试
- [ ] 5.4 编写 DataflowTracer Mermaid 格式化器单元测试
- [ ] 5.5 编写 GraphData 转换函数测试（hierarchy_to_graph, fsm_to_graph, trace_to_graph）
- [ ] 5.6 编写 HtmlVisualizer 生成测试（文件存在、包含 vis-network、数据正确）
- [ ] 5.7 编写 rtl_visualize 工具集成测试（auto 检测、各图类型、各输出格式）

## 6. 最终验证

- [ ] 6.1 运行 `pytest tests/test_visualization.py -v`，确认所有测试通过
- [ ] 6.2 用实际 RTL 项目调用 `rtl_visualize("top", "hierarchy", "mermaid")`，验证 Mermaid 可渲染
- [ ] 6.3 用实际 RTL 项目调用 `rtl_visualize("top", "hierarchy", "html")`，浏览器打开验证交互
- [ ] 6.4 验证 `rtl_visualize` 的 auto 检测对不同目标的正确性
- [ ] 6.5 确认所有现有 MCP 工具接口不变：`pytest tests/ -v`
