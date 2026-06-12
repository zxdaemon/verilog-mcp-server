## Context

当前项目已有 20+ MCP 工具，分三级（搜索/关系/分析）。分析引擎产出丰富的结构化数据：HierarchyNode 树、TraceNode 信号流、FSM 状态转移、ClockTreeResult 时钟域。其中 ClockTreeBuilder 已实现 `format_mermaid()`，其他引擎仅有 ASCII 文本输出。

本次添加可视化能力，复用现有分析引擎，仅新增格式化层和渲染层。关键约束：
- 零新依赖（Mermaid 纯文本，HTML 用 CDN vis.js）
- 所有现有 MCP 工具接口不变
- 可视化输出为新增能力，不修改现有工具行为

## Goals / Non-Goals

**Goals:**
- 为 hierarchy、fsm、dataflow、clock 四种图类型提供 Mermaid 输出
- 提供统一 `rtl_visualize` MCP 工具，支持 auto 检测
- 生成交互式 HTML 图谱（vis.js），支持缩放/拖拽/点击详情
- 定义通用 GraphData 中间表示，便于扩展新的可视化后端

**Non-Goals:**
- 不实现完整的 Web Dashboard（如 Understand-Anything 的 React Flow 方案）
- 不实现图谱的实时更新或 WebSocket 推送
- 不实现 SVG/PNG 导出（由客户端自行渲染 Mermaid）
- 不引入 ELK/Dagre 等布局引擎（vis.js 内置 forceAtlas2 已足够）

## Decisions

### D1: Mermaid 格式化策略

**选择**: 在各分析引擎类上添加 `format_mermaid()` 方法，与现有 `format_tree_text()` / `format_text_tree()` 并列。

参考实现：`ClockTreeBuilder.format_mermaid()` (clock_tree.py:290-323)

```python
# hierarchy.py
class HierarchyBuilder:
    def format_mermaid(self, top_module: str, max_depth: int = 10) -> str:
        """flowchart TD，节点为 instance_name: module_name"""

# fsm_detector.py
class FSM:
    def format_mermaid(self) -> str:
        """stateDiagram-v2，状态为节点，转移为带条件边"""

class FSMDetector:
    def format_mermaid(self, module_name: str) -> str:
        """调用 detect_fsms()，拼接各 FSM 的 Mermaid"""

# fan_in.py
class DataflowTracer:
    @staticmethod
    def format_mermaid(result: TraceResult, title: str = "Signal Trace") -> str:
        """flowchart TD，按模块名分 subgraph"""
```

**Mermaid 语法选择**:
- Hierarchy → `flowchart TD`（树形结构，自上而下）
- FSM → `stateDiagram-v2`（Mermaid 原生状态图语法）
- Dataflow → `flowchart TD` + `subgraph`（按模块分组）
- Clock Tree → `flowchart TD`（已有，增强样式）

**名称转义**: 模块/信号名含 `[]()<>|` 等 Mermaid 语法字符，统一用 `_sanitized_id()` 替换，节点标签用 `["..."]` 包裹。

**备选方案**:
- ❌ DOT/Graphviz 格式：需要额外工具渲染，不如 Mermaid 通用
- ✅ Mermaid：Claude Code 原生支持渲染，零依赖

### D2: 通用图数据模型

**选择**: 定义 `GraphData` 作为分析结果到可视化的中间表示。

```python
# analysis/visualizer.py

@dataclass
class GraphNode:
    id: str
    label: str
    group: str = ""       # module / signal / state / clock / cycle
    title: str = ""       # hover tooltip（HTML 中使用）
    shape: str = "box"    # vis.js shape

@dataclass
class GraphEdge:
    from_id: str
    to_id: str
    label: str = ""
    dashes: bool = False  # 循环引用虚线

@dataclass
class GraphData:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    title: str = ""
```

转换函数：
```python
def hierarchy_to_graph(root: HierarchyNode) -> GraphData
def fsm_to_graph(fsm: FSM) -> GraphData
def trace_to_graph(result: TraceResult) -> GraphData
def clock_tree_to_graph(result: ClockTreeResult) -> GraphData
```

### D3: HTML 交互图谱

**选择**: 生成自包含 HTML 文件，内嵌 vis.js（CDN），数据以 JSON 内联。

```python
class HtmlVisualizer:
    @staticmethod
    def generate(graph_data: GraphData, output_path: str | None = None) -> str:
        """生成 HTML 文件，返回文件路径"""
```

**技术选型**:
- vis.js (`https://unpkg.com/vis-network/standalone/umd/vis-network.min.js`)
- forceAtlas2Based 物理布局（适合层次结构）
- 分组着色：module=蓝, signal=绿, state=橙, clock=紫, cycle=红

**输出路径**: 默认 `.verilog_mcp/visualizations/`，可通过参数自定义。

**交互功能**: 缩放/拖拽、点击节点显示详情（端口、文件路径、信号类型）、工具栏、图例。

**备选方案**:
- ❌ D3.js：需要手动实现太多布局逻辑
- ❌ Cytoscape.js：API 复杂，vis.js 更简单
- ✅ vis.js：内置层次布局、开箱即用的交互、CDN 可用

### D4: 统一 MCP 工具

**选择**: 新增 `rtl_visualize` 工具，统一入口。

```python
@mcp.tool()
def rtl_visualize(
    target: str,
    diagram_type: str = "auto",    # hierarchy / fsm / dataflow / clock / auto
    output_format: str = "mermaid", # mermaid / html
    max_depth: int = 10,
) -> str:
```

**auto 检测逻辑**:
1. 查 IndexStore，target 是模块且有子例化 → `hierarchy`
2. target 是模块且无子例化、有 always+case → `fsm`
3. target 是信号名（IndexStore 中有信号定义）→ `dataflow`
4. target 是模块名 → `hierarchy`（默认）

**返回值**:
- mermaid 模式：返回 Mermaid 文本字符串
- html 模式：生成 HTML 文件，返回文件路径

### D5: 现有 clock_tree Mermaid 增强

在现有 `ClockTreeBuilder.format_mermaid()` 基础上：
- 添加 `%%{init: {'theme': 'base'}}%%` 主题声明
- 门控时钟节点添加特殊样式 `classDef gated fill:#f96`
- 无时钟模块添加灰色节点

## Risks / Trade-offs

- **[中] 大型设计 Mermaid 文本过长**: 200+ 模块的层次树 Mermaid 超出渲染限制 → 添加节点数上限（默认 200），超出时截断并提示
- **[低] HTML 需要网络加载 vis.js**: 离线环境无法使用 → 默认 CDN 方式，未来可添加 `embed_js` 参数内嵌
- **[低] auto 检测可能不准确**: 模块同时有子例化和 FSM → 优先返回 hierarchy，用户可手动指定 `diagram_type`
- **[低] Mermaid 名称转义可能丢失信息**: 特殊字符替换为 `_` → 标签用完整名称，仅 ID 做转义
