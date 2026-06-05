# 可视化图谱优化设计

日期: 2026-06-05

## 目标

将 vis.js 替换为 Cytoscape.js，提升大规模 RTL 设计（300-1000+ 模块）的 HTML 交互体验。保持后端 `GraphData` 模型不变，只替换前端渲染层。同时统一 Mermaid 生成路径，本地化静态资源。

## 架构变更

```
                        ─── 不变 ───              ─── 变更 ───

analysis/hierarchy.py ─┐
analysis/fsm_detector   │
analysis/fan_in.py     ├─▶ GraphData ──▶ HtmlVisualizer.generate()
analysis/clock_tree.py ─┘       │                    │
                                │                    ├── HTML: Cytoscape.js (new)
                                │                    └── Mermaid: graph_to_mermaid() (new)
                                │
                                └── 各引擎 format_mermaid() → 删除
```

### 改动文件

| 文件 | 改动 | 幅度 |
|------|------|------|
| `templates/visualizer.html` | 重写为 Cytoscape.js + 亮色主题 | ~450 行 |
| `analysis/visualizer.py` | 新增 `graph_to_mermaid()`，删除各引擎中的 `format_mermaid()` | 中 |
| `analysis/hierarchy.py` | 删除 `format_mermaid()`，依赖改为 visualizer | 小 |
| `analysis/fsm_detector.py` | 删除 `format_mermaid()` | 小 |
| `analysis/fan_in.py` | 删除 `format_mermaid()` | 小 |
| `analysis/clock_tree.py` | 删除 `format_mermaid()` | 小 |
| `tools/visualize.py` | 更新 import，所有 `format_mermaid()` 调用改为 `graph_to_mermaid()` | 小 |
| `tests/test_visualization.py` | 更新测试 | 小 |
| `.verilog_mcp/assets/` | 新增 `cytoscape.min.js` + `dagre.min.js` | 首次下载 |

## 前端组件

### HTML 结构

```
<!DOCTYPE html>
<html>
<head>
  <script src="cytoscape.min.js">    <!-- 本地文件, CDN fallback -->
  <script src="dagre.min.js">
  <style>
    1. CSS 变量 (亮色主题)
    2. 布局 (#toolbar, #cy-container, #info-panel, #minimap, #legend)
    3. 节点/边样式
    4. Glass 面板 (backdrop-filter)
  </style>
</head>
<body>
  <!-- DOM -->
  #toolbar          [Back] [Reset] [Fit] [Zoom +/-] | 🔍 [搜索...] | [PNG↓]
  #cy-container     Cytoscape 画布
  #minimap          MiniMap 容器 (右下角)
  #info-panel       (右侧, glass) 节点详情 + 钻取提示
  #legend           (左下) 图例

  <!-- JS (11 个模块) -->
  <script>
    1. 数据注入 ($nodes_json, $edges_json)
    2. 索引构建 (childrenMap, parentMap)
    3. Cytoscape 初始化 + 布局选择
    4. 样式映射 (按 group 配色)
    5. tap → 信息面板
    6. dbltap → 钻取 (仅 hierarchy)
    7. 钻取逻辑 (drillInto / goUp / resetView)
    8. 搜索过滤 (debounce 200ms + 高亮 + fit)
    9. PNG 导出 (cy.png)
    10. MiniMap (cy-minimap 插件或内嵌)
    11. 按钮事件绑定
  </script>
</body>
</html>
```

### 布局策略

| 图类型 | 布局引擎 | 参数 |
|--------|---------|------|
| hierarchy | dagre | rankDir: TB, animate: true |
| fsm | fcose | gravity: 0.3, animate: true |
| dataflow | dagre | rankDir: LR, animate: true |
| clock | fcose | gravity: 0.3, animate: true |

### 交互行为

| 操作 | 行为 |
|------|------|
| 单击节点 | 右侧面板显示详情, 节点高亮, 其余节点/边淡出 |
| 双击节点 (hierarchy) | 钻取子模块, 更新面包屑, 动画过渡 |
| 双击空白 | 返回上级 (同 Back 按钮) |
| 搜索输入 | 实时过滤, 匹配节点高亮, 不匹配淡出, 自动 fit |
| Back 按钮 | 返回上一层钻取, 面包屑跳动 |
| Reset 按钮 | 恢复全图, 清除钻取栈 |
| PNG 按钮 | 导出全图 PNG, 保持背景色 |

## 配色方案

### 亮色主题 CSS 变量

```css
:root {
  /* 背景层次 */
  --bg-root: #f8f9fa;
  --bg-surface: #ffffff;
  --bg-elevated: #f0f1f3;

  /* 文字 */
  --text-primary: #1a1a2e;
  --text-secondary: #636d83;
  --text-muted: #94a3b8;

  /* 强调 */
  --accent: #2563eb;
  --accent-dim: #dbeafe;

  /* 边框 */
  --border-subtle: #e2e8f0;
  --border-medium: #cbd5e1;

  /* Glass */
  --glass-bg: rgba(255, 255, 255, 0.85);
  --glass-border: rgba(0, 0, 0, 0.06);
}
```

### 节点颜色 (语义分组)

```css
--node-module: #3b82f6;  /* 蓝 */
--node-signal: #22c55e;  /* 绿 */
--node-state:  #f59e0b;  /* 琥珀 */
--node-clock:  #8b5cf6;  /* 紫 */
--node-cycle:  #ef4444;  /* 红 */
```

## 离线支持

首次启动时自动下载静态资源到 `.verilog_mcp/assets/`:

```
.verilog_mcp/assets/
├── cytoscape.min.js     (~400KB, npm cytoscape@3.x)
└── dagre.min.js         (~50KB, npm dagre@0.8.x)
```

HTML 模板加载逻辑:
1. 尝试加载 `file://.verilog_mcp/assets/cytoscape.min.js`
2. 失败则 fallback CDN (cdnjs)
3. 记录警告但继续渲染

`HtmlVisualizer` 生成 HTML 前确保资源文件存在，不存在时自动下载。

## Mermaid 统一生成

在 `visualizer.py` 中新增 `graph_to_mermaid(graph_data: GraphData) -> str`:

```python
def graph_to_mermaid(graph_data: GraphData) -> str:
    """从 GraphData 统一生成 Mermaid 图"""
    if graph_data.graph_type == "hierarchy":
        return _mermaid_flowchart(graph_data, direction="TD")
    elif graph_data.graph_type == "fsm":
        return _mermaid_statediagram(graph_data)
    elif graph_data.graph_type == "dataflow":
        return _mermaid_flowchart(graph_data, direction="LR")
    elif graph_data.graph_type == "clock":
        return _mermaid_flowchart(graph_data, direction="TD")
```

各分析引擎 (`hierarchy.py`, `fsm_detector.py`, `fan_in.py`, `clock_tree.py`) 中的 `format_mermaid()` 方法一并删除，`tools/visualize.py` 中所有 `format_mermaid()` 调用改为先构建 `GraphData` 再调用 `graph_to_mermaid()`。

## 测试更新

`tests/test_visualization.py`:
- 更新 Mermaid 输出测试，使用 `graph_to_mermaid()` 路径
- 新增 HTML 生成测试（验证文件包含 cytoscape 引用）
- 确保现有 FSM/层次图测试仍然通过

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Cytoscape.js 学习曲线 | 复用现有钻取逻辑结构，只换 API 调用 |
| dagre 对超大图 (>500 节点) 也可能慢 | dagre 用于 hierarchy/dataflow 已有层次约束，实际渲染节点数由钻取深度限制 |
| 离线资源下载首次慢 | 启动时后台下载，不阻塞 MCP 响应 |
| 老 HTML 文件不兼容 | 不向后兼容 — 新版本生成全新格式 HTML |
