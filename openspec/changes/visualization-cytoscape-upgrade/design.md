## Context

当前可视化系统基于 vis.js（已停维），Mermaid 生成分散在 4 个分析引擎中。需要升级渲染引擎以支持大规模 RTL 设计（300-1000+ 模块），同时统一 Mermaid 生成路径。

约束：
- HTML 输出必须是单文件，无构建步骤（MCP server 直接生成）
- `rtl_visualize` MCP 工具签名保持不变
- 亮色主题（用户偏好）

参考：Understand-Anything 项目的交互图谱设计模式（MiniMap、搜索栏、Glass 面板）。

## Goals / Non-Goals

**Goals:**
- 将 vis.js 替换为 Cytoscape.js，支持 WebGL 渲染和更好的大图性能
- 新增搜索过滤、MiniMap、PNG 导出功能
- 亮色主题，CSS 变量体系
- 本地化静态资源（cytoscape.min.js + dagre.min.js），离线可用
- 统一 Mermaid 生成到 `graph_to_mermaid()`，删除 4 处重复实现

**Non-Goals:**
- 不实现 Web Dashboard（React/构建步骤）
- 不替换 Mermaid 图表格式（保持 Mermaid 文本输出不变）
- 不实现语义搜索或 fuzzy search（仅文本过滤）
- 不影响 MCP 工具签名
- 不实现多主题切换

## Decisions

### D1: 替换为 Cytoscape.js

**选择**: Cytoscape.js 3.x

vis.js 已停维（2021 年最后一版），`vis-network@9.x` 对 WebGL 支持有限（edge label 在 WebGL 模式下丢失），在大规模 RTL 设计（600+ 节点）的 forceAtlas2 布局几乎不可用。

Cytoscape.js 在生物信息学领域广泛用于同规模图可视化，有成熟的大图优化。内置 Canvas + WebGL 双渲染器，dagre 和 fcose 布局直接可用。

**备选**:
- 保持 vis.js + 服务端简化 — 治标不治本，天花板明显
- ReactFlow — 需要 React 构建步骤，不适合单文件 HTML 输出

### D2: dagre + fcose 布局组合

**选择**: hierarchy/dataflow 用 dagre（层次布局），fsm/clock 用 fcose（力导向）

dagre 是 Cytoscape.js 官方推荐的层次布局扩展，支持 TB（上→下）和 LR（左→右）方向。fcose 是 CoSE 算法的优化版，适合没有明确层次关系的图（FSM、时钟域）。

### D3: 亮色主题

**选择**: 白底 + 蓝色强调（`#2563eb`），CSS 变量体系

对齐 GitHub/VS Code light 风格的视觉设计。节点颜色保持语义分组（模块=蓝、信号=绿、状态=琥珀、时钟=紫、循环=红）。

### D4: 本地资源 + CDN fallback

**选择**: 首次启动时下载 cytoscape.min.js + dagre.min.js 到 `.verilog_mcp/assets/`

HTML 模板优先加载本地文件，失败时 fallback CDN (cdnjs)。`HtmlVisualizer.generate()` 调用前确保资源存在。

### D5: Mermaid 统一生成

**选择**: 在 `visualizer.py` 中新增 `graph_to_mermaid(graph_data: GraphData) -> str`

各分析引擎先构建 `GraphData`，再调用 `graph_to_mermaid()` 输出 Mermaid。删除各引擎中重复的 `format_mermaid()` 方法。`tools/visualize.py` 中 Mermaid 输出路径改为：`graph_data = xxx_to_graph(...); return graph_to_mermaid(graph_data)`。

## Risks / Trade-offs

- **[低] dagre 对超大图 (>500 节点) 也可能慢**: hierarchy 类型有钻取限制深度，实际渲染节点数受深度约束，初始只显示 depth≤3
- **[低] 离线资源首次下载慢**: 启动时后台下载，不阻塞 MCP 响应
- **[低] 老 HTML 文件不兼容**: 不向后兼容 — 新版本生成全新格式 HTML，老文件保留在 `.verilog_mcp/visualizations/`
