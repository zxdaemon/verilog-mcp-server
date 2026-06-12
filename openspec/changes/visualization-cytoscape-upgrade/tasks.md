## 1. Mermaid 统一生成

- [x] 1.1 在 `analysis/visualizer.py` 中实现 `graph_to_mermaid(graph_data) -> str`，支持 hierarchy/fsm/dataflow/clock 四种类型
- [x] 1.2 删除 `analysis/hierarchy.py` 中的 `HierarchyBuilder.format_mermaid()` 方法
- [x] 1.3 删除 `analysis/fsm_detector.py` 中的 `FSM.format_mermaid()` 和 `FSMDetector.format_mermaid()` 方法
- [x] 1.4 删除 `analysis/fan_in.py` 中的 `DataflowTracer.format_mermaid()` 静态方法
- [x] 1.5 删除 `analysis/clock_tree.py` 中的 `ClockTreeBuilder.format_mermaid()` 方法
- [x] 1.6 更新 `tools/visualize.py`，Mermaid 输出改为 `xxx_to_graph() → graph_to_mermaid()` 路径

## 2. Cytoscape.js HTML 模板

- [x] 2.1 重写 `templates/visualizer.html`，使用 Cytoscape.js + dagre 替换 vis.js
- [x] 2.2 实现亮色主题 CSS 变量体系（`--bg-root`, `--accent` 等）
- [x] 2.3 实现 dagre 层次布局（hierarchy: TB, dataflow: LR）和 cose 力导向布局（fsm, clock）
- [x] 2.4 实现节点分组样式（module=蓝, signal=绿, state=琥珀, clock=紫, cycle=红）
- [x] 2.5 在 toolbar 添加搜索输入框，实现 debounce 过滤 + 高亮 + fit
- [x] 2.6 在画布右下角实现 MiniMap 缩略图
- [x] 2.7 在 toolbar 添加 PNG 导出按钮，使用 `cy.png()` API
- [x] 2.8 保持现有钻取导航逻辑（双击 → 过滤子树，Back/Reset → 返回/恢复，面包屑更新）
- [x] 2.9 保持现有信息面板（单击节点 → 右侧 Glass 面板显示详情）

## 3. 离线资源管理

- [x] 3.1 在 `HtmlVisualizer` 中添加资源检查逻辑：`.verilog_mcp/assets/` 下检查 cytoscape.min.js + dagre.min.js
- [x] 3.2 实现首次启动自动下载（cdnjs: cytoscape@3.30 + dagre@0.8）
- [x] 3.3 HTML 模板使用本地文件优先加载，fallback CDN

## 4. 测试

- [x] 4.1 更新 `tests/test_visualization.py` 中 Mermaid 测试以匹配新路径
- [x] 4.2 新增 HTML 生成测试（验证文件包含 cytoscape.js 引用）
- [x] 4.3 新增 `graph_to_mermaid()` 单元测试（四种图类型）
- [x] 4.4 运行 `pytest tests/ -v`，确认所有新增测试通过，无回归
