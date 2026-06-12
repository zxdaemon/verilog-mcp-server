## ADDED Requirements

### Requirement: HtmlVisualizer 生成交互式 HTML 图谱

`analysis/visualizer.py` SHALL 提供 `HtmlVisualizer` 类，其 `generate(graph_data, output_path) -> str` 方法生成自包含 HTML 文件，返回文件路径。

HTML 文件 SHALL 包含：
- vis.js 库（通过 CDN `https://unpkg.com/vis-network/standalone/umd/vis-network.min.js` 加载）
- 内联的节点和边数据（JSON 格式）
- 工具栏（Fit、Zoom In、Zoom Out 按钮）
- 点击节点显示详情的侧面板
- 分组颜色图例

#### Scenario: 基本 HTML 生成

- **WHEN** 调用 `HtmlVisualizer.generate(graph_data)` 传入包含 5 个节点、4 条边的 GraphData
- **THEN** 生成的 HTML 文件存在且大小 > 1KB
- **AND** 文件包含 `vis-network` 引用
- **AND** 文件包含内联的节点 JSON 数据

#### Scenario: 自定义输出路径

- **WHEN** 调用 `HtmlVisualizer.generate(graph_data, output_path="/tmp/test.html")`
- **THEN** 文件生成在 `/tmp/test.html`
- **AND** 返回路径为 `/tmp/test.html`

#### Scenario: 默认输出路径

- **WHEN** 调用 `HtmlVisualizer.generate(graph_data)` 不指定 output_path
- **THEN** 文件生成在 `.verilog_mcp/visualizations/` 目录下
- **AND** 文件名基于图标题和时间戳生成

### Requirement: GraphData 中间数据模型

`analysis/visualizer.py` SHALL 定义 `GraphNode`、`GraphEdge`、`GraphData` 三个 dataclass，作为分析结果到可视化的通用中间表示。

#### Scenario: HierarchyNode 转换为 GraphData

- **WHEN** 调用 `hierarchy_to_graph(root)` 传入包含 3 个子节点的 HierarchyNode
- **THEN** 返回的 GraphData 包含 4 个 nodes 和 3 个 edges
- **AND** 每个 node 的 group 为 `"module"`

#### Scenario: FSM 转换为 GraphData

- **WHEN** 调用 `fsm_to_graph(fsm)` 传入包含 3 个状态、2 个转移的 FSM
- **THEN** 返回的 GraphData 包含 3 个 nodes（状态）和 2 个 edges（转移）
- **AND** 每个 node 的 group 为 `"state"`
