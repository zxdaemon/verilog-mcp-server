## ADDED Requirements

### Requirement: HTML 图谱使用 Cytoscape.js 渲染

系统 SHALL 使用 Cytoscape.js 生成交互式 HTML 图谱，替代 vis.js。

节点和边从 GraphData 注入为 JSON，Cytoscape 初始化时读取并渲染。布局策略：
- hierarchy 和 dataflow 类型使用 dagre 层次布局（TB/LR）
- fsm 和 clock 类型使用 fcose 力导向布局

#### Scenario: 生成 hierarchy HTML 图谱

- **WHEN** 调用 `rtl_visualize("top", "hierarchy", "html")`
- **THEN** 生成的 HTML 文件包含 Cytoscape.js 画布，节点按 dagre 上→下布局排列

#### Scenario: 生成 fsm HTML 图谱

- **WHEN** 调用 `rtl_visualize("my_fsm_module", "fsm", "html")`
- **THEN** 生成的 HTML 文件包含 Cytoscape.js 画布，状态节点为椭圆形，转移边带条件标签

### Requirement: 亮色主题

系统 SHALL 使用亮色主题作为默认配色方案。CSS 变量定义在 HTML 模板的 `<style>` 块中。

配色规范：
- 页面底色 `#f8f9fa`，面板底色 `#ffffff`
- 强调色 `#2563eb`（蓝色）
- 节点分组着色：模块 `#3b82f6`、信号 `#22c55e`、状态 `#f59e0b`、时钟 `#8b5cf6`、循环 `#ef4444`

#### Scenario: HTML 页面展示亮色主题

- **WHEN** 在浏览器中打开生成的 HTML 文件
- **THEN** 页面背景为浅灰色，工具栏和面板为白色，节点按分组着色

### Requirement: 节点搜索过滤

系统 SHALL 在 toolbar 提供搜索输入框，支持按节点标签实时过滤。

用户输入时，匹配的节点高亮显示，不匹配的节点半透明（opacity: 0.15）。回车或自动 debounce 200ms 后触发 fit 到匹配节点。

#### Scenario: 搜索节点

- **WHEN** 用户在搜索框输入 "alu"
- **THEN** 标签包含 "alu" 的节点高亮，其余节点淡出，视图自动缩放定位到匹配节点

#### Scenario: 清空搜索

- **WHEN** 用户清空搜索框
- **THEN** 所有节点恢复正常透明度

### Requirement: MiniMap 导航

系统 SHALL 在画布右下角显示 MiniMap 缩略图，展示全图概览。

MiniMap 框选区域应同步主画布视口位置，拖拽 MiniMap 框选区域应联动主画布平移。

#### Scenario: MiniMap 显示

- **WHEN** 图谱加载完成
- **THEN** 右下角出现缩略图，显示整个图谱的微型视图

### Requirement: PNG 导出

系统 SHALL 在 toolbar 提供 PNG 导出按钮，将当前图谱导出为 PNG 图片。

导出使用 Cytoscape.js 的 `cy.png()` API，输出为 PNG blob 并触发浏览器下载。导出时保持当前背景色和节点样式。

#### Scenario: 导出 PNG

- **WHEN** 用户点击 PNG 导出按钮
- **THEN** 浏览器下载当前图谱的 PNG 截图文件

### Requirement: 层次图钻取导航

系统 SHALL 在 hierarchy 类型图谱中支持双击钻取子模块。

双击节点后，非子树节点和边从画布中移除，仅显示该节点及其子孙。Back 按钮恢复上一层。面包屑显示当前钻取路径。

#### Scenario: 钻取子模块

- **WHEN** 用户在 hierarchy 图谱中双击某个模块节点
- **THEN** 画布仅显示该模块及其子模块，面包屑更新为 "top ▸ u_cpu"，Back 按钮启用

#### Scenario: 返回上层

- **WHEN** 用户点击 Back 按钮
- **THEN** 画布恢复到上一层的子模块视图，面包屑相应更新

### Requirement: 信息面板

系统 SHALL 在右侧显示 Glass 风格的信息面板，展示当前选中节点的详情。

单击节点时面板更新为节点的 title 属性内容（模块名、路径、文件、端口数等）。面板使用 `backdrop-filter: blur(12px)` 半透明效果。

#### Scenario: 查看节点详情

- **WHEN** 用户单击一个节点
- **THEN** 右侧信息面板显示该节点的详细信息

### Requirement: 离线资源管理

系统 SHALL 在首次生成 HTML 时自动下载静态资源到 `.verilog_mcp/assets/` 目录。

资源包括 `cytoscape.min.js` 和 `dagre.min.js`。HTML 模板中使用 `<script>` 标签优先加载本地文件，失败时 fallback CDN。

#### Scenario: 首次生成 HTML

- **WHEN** `.verilog_mcp/assets/` 不存在或缺少资源文件
- **THEN** `HtmlVisualizer.generate()` 自动下载并缓存所需资源文件

#### Scenario: 离线打开 HTML

- **WHEN** 在无网络环境下打开生成的 HTML 文件
- **THEN** 图谱正常渲染（使用本地缓存的 js 文件）
