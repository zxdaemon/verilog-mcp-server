## Why

当前 `rtl_visualize` 使用 vis.js（已停维，2021 年最后一版）渲染交互式 HTML 图谱。在大规模 RTL 设计（300-1000+ 模块，如 OpenC910）中力导向布局性能不足，且缺少搜索过滤、MiniMap 导航、PNG 导出等关键交互功能。另外 Mermaid 生成分散在 4 个分析引擎中各写一遍，逻辑重复且不一致。

## What Changes

- 用 Cytoscape.js 替换 vis.js 作为 HTML 渲染引擎，支持 WebGL 加速和更好的大图性能
- 亮色主题替代暗蓝主题，便于截图贴文档
- 新增节点搜索过滤、MiniMap、PNG 导出功能
- 统一 Mermaid 生成路径：从 `GraphData` 推导，删除各引擎中的重复 `format_mermaid()`
- 本地化静态资源（cytoscape.min.js + dagre.min.js），支持离线使用
- **BREAKING**: `rtl_visualize` 的 HTML 输出格式不向后兼容（新格式为 Cytoscape.js，老格式为 vis.js）

## Capabilities

### New Capabilities

- `visualization-cytoscape`: Cytoscape.js 渲染引擎 + 亮色主题 + 搜索/MiniMap/PNG 导出 + 离线资源
- `visualization-mermaid-unified`: 从 GraphData 统一生成 Mermaid，替代各引擎分散实现

### Modified Capabilities

无。现有 MCP 工具接口（`rtl_visualize` 参数签名）保持不变。

## Impact

- `templates/visualizer.html` — 完全重写为 Cytoscape.js + 亮色主题
- `analysis/visualizer.py` — 新增 `graph_to_mermaid()`，`HtmlVisualizer` 更新资源下载逻辑
- `analysis/hierarchy.py` — 删除 `format_mermaid()`
- `analysis/fsm_detector.py` — 删除 `FSM.format_mermaid()` 和 `FSMDetector.format_mermaid()`
- `analysis/fan_in.py` — 删除 `DataflowTracer.format_mermaid()`
- `analysis/clock_tree.py` — 删除 `format_mermaid()`
- `tools/visualize.py` — 更新 import，Mermaid 调用改为 `graph_to_mermaid()`
- `tests/test_visualization.py` — 更新测试
- `.verilog_mcp/assets/` — 新增本地静态资源目录
