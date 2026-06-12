"""
可视化图谱生成器

提供：
- GraphData 通用图数据模型（节点 + 边）
- 从各分析结果到 GraphData 的转换函数
- HtmlVisualizer 生成交互式 HTML 图谱（vis.js）
"""

from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from string import Template
from typing import TYPE_CHECKING
from urllib.request import urlretrieve

from importlib.resources import files as _resource_files

if TYPE_CHECKING:
    from .hierarchy import HierarchyNode
    from .fan_in import TraceResult, TraceNode
    from .fsm_detector import FSM
    from .clock_tree import ClockTreeResult


# ── 通用图数据模型 ──

@dataclass
class GraphNode:
    """图节点"""
    id: str
    label: str
    group: str = ""        # module / signal / state / clock / cycle / top / controller / arithmetic / memory / interface / basic / aggregated
    title: str = ""        # hover tooltip
    shape: str = "box"     # vis.js shape
    parent_id: str = ""    # 父节点 id（用于层次收缩/展开）
    depth: int = 0         # 节点深度
    aggregated_count: int = 0  # >0 表示聚合了多少个同类型实例


@dataclass
class GraphEdge:
    """图边"""
    from_id: str
    to_id: str
    label: str = ""
    dashes: bool = False  # 循环引用虚线
    arrows: str = "to"


@dataclass
class GraphData:
    """通用图数据"""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    title: str = ""
    graph_type: str = ""   # hierarchy / fsm / dataflow / clock


# ── 转换函数 ──

def _sanitize_id(name: str) -> str:
    """转义 Mermaid/vis.js 不兼容的字符"""
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


# ── 模块分类 ──

_MODULE_CLASSIFICATION_PATTERNS: dict[str, list[str]] = {
    "controller": ["ctrl", "fsm", "arbiter", "scheduler", "sequencer", "decoder", "encoder", "priority"],
    "arithmetic": ["alu", "adder", "multiplier", "div", "mult", "mac", "dsp", "cmp", "comparator"],
    "memory":     ["ram", "rom", "fifo", "regfile", "sram", "mem", "queue", "buffer", "cache"],
    "interface":  ["uart", "spi", "i2c", "axi", "apb", "ahb", "gpio", "usb", "pcie", "eth", "mdio", "jtag"],
    "basic":      ["buf", "inv", "mux", "demux", "and", "or", "xor", "not", "nand", "nor", "xnor", "dff", "flipflop", "latch", "register"],
}


def classify_module(module_name: str) -> str:
    """按模块名称模式分类模块功能类型"""
    mn_lower = module_name.lower()
    for group, patterns in _MODULE_CLASSIFICATION_PATTERNS.items():
        if any(p in mn_lower for p in patterns):
            return group
    return "module"


def _extract_module_name(label: str) -> str:
    """从 label 'instance: module' 中提取 module_name"""
    if ": " in label:
        return label.split(": ", 1)[1]
    return label


def _aggregate_leaf_nodes(
    nodes: list[GraphNode], edges: list[GraphEdge], max_nodes: int
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """聚合同 parent 下相同 module_name 的 leaf 节点，直到节点数 <= max_nodes"""
    if len(nodes) <= max_nodes:
        return nodes, edges

    node_by_id = {n.id: n for n in nodes}

    def _rebuild_indices() -> tuple[set[str], dict[str, list[str]]]:
        has_children: set[str] = set()
        for e in edges:
            has_children.add(e.from_id)
        parent_to_children: dict[str, list[str]] = {}
        for n in nodes:
            if n.parent_id:
                parent_to_children.setdefault(n.parent_id, []).append(n.id)
        return has_children, parent_to_children

    iteration = 0
    while len(nodes) > max_nodes:
        has_children, parent_to_children = _rebuild_indices()

        best_group: tuple[str, str, list[str]] | None = None
        best_count = 0

        for parent_id, child_ids in parent_to_children.items():
            by_module: dict[str, list[str]] = {}
            for cid in child_ids:
                if cid not in node_by_id or cid in has_children:
                    continue  # skip deleted or non-leaf
                mod_name = _extract_module_name(node_by_id[cid].label)
                by_module.setdefault(mod_name, []).append(cid)

            for mod_name, cids in by_module.items():
                if len(cids) >= 2 and len(cids) > best_count:
                    best_count = len(cids)
                    best_group = (parent_id, mod_name, cids)

        if not best_group:
            break  # 无法再聚合

        parent_id, mod_name, cids = best_group
        depth = node_by_id[cids[0]].depth

        # 唯一 agg_id
        agg_id = f"agg_{parent_id}_{mod_name}_{depth}_{iteration}"
        iteration += 1

        agg_label = f"{mod_name} (×{len(cids)})"

        titles: list[str] = []
        for cid in cids:
            node = node_by_id[cid]
            if node.title:
                titles.append(node.title)

        agg_title = f"聚合: {mod_name} ({len(cids)} 个实例)\n"
        agg_title += "\n".join(titles[:10])
        if len(titles) > 10:
            agg_title += f"\n... 还有 {len(titles) - 10} 个"

        agg_node = GraphNode(
            id=agg_id, label=agg_label, group="aggregated",
            title=agg_title, shape="round-rectangle",
            parent_id=parent_id, depth=depth,
            aggregated_count=len(cids),
        )

        # 替换节点
        new_nodes = [n for n in nodes if n.id not in cids]
        new_nodes.append(agg_node)

        # 替换边：删除 parent->child 和 child->* 的边，添加 parent->agg
        new_edges: list[GraphEdge] = []
        for e in edges:
            if e.to_id in cids:
                if e.from_id == parent_id:
                    continue  # 删除 parent->child，稍后添加 parent->agg
                # 其他指向被聚合节点的边——删除（这种情况在 leaf 聚合中不应该出现）
                continue
            if e.from_id in cids:
                continue  # 删除从被聚合节点出发的边
            new_edges.append(e)

        new_edges.append(GraphEdge(from_id=parent_id, to_id=agg_id))

        nodes = new_nodes
        edges = new_edges
        node_by_id = {n.id: n for n in nodes}

    return nodes, edges


def hierarchy_to_graph(root: "HierarchyNode", max_nodes: int = 100) -> GraphData:
    """将 HierarchyNode 树转换为 GraphData（含父子关系用于钻取导航）"""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    idx = 0

    def _walk(node: "HierarchyNode", parent_id: str | None = None, depth: int = 0):
        nonlocal idx
        nid = f"n{idx}"
        idx += 1

        label = f"{node.instance_name}: {node.module_name}" if node.instance_name else node.module_name
        if node.is_cycle_ref:
            group = "cycle"
        elif depth == 0:
            group = "top"
        else:
            group = classify_module(node.module_name)

        title = f"模块: {node.module_name}\n路径: {node.instance_path}\n文件: {node.file_path}"
        if node.is_cycle_ref:
            title += "\n(循环引用)"

        has_children = len(node.children) > 0
        if has_children:
            title += f"\n子模块数: {len(node.children)}\n(双击钻取)"

        nodes.append(GraphNode(
            id=nid, label=label, group=group, title=title, shape="box",
            parent_id=parent_id or "", depth=depth,
        ))

        if parent_id is not None:
            edges.append(GraphEdge(
                from_id=parent_id, to_id=nid,
                label="cycle" if node.is_cycle_ref else "",
                dashes=node.is_cycle_ref,
            ))

        for child in node.children:
            _walk(child, nid, depth + 1)

    _walk(root)

    # 节点过多时聚合同类型 leaf 实例
    if len(nodes) > max_nodes:
        nodes, edges = _aggregate_leaf_nodes(nodes, edges, max_nodes)

    return GraphData(nodes=nodes, edges=edges, title=f"层次树: {root.module_name}", graph_type="hierarchy")


def fsm_to_graph(fsm: "FSM") -> GraphData:
    """将 FSM 转换为 GraphData"""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    state_id_map: dict[str, str] = {}
    for i, state in enumerate(fsm.states):
        nid = f"s{i}"
        state_id_map[state] = nid
        title = f"状态: {state}\n编码: {fsm.encoding}"
        nodes.append(GraphNode(id=nid, label=state, group="state", title=title, shape="ellipse"))

    # 初始状态标记
    if fsm.states:
        init_id = f"init_{state_id_map[fsm.states[0]]}"
        nodes.append(GraphNode(id=init_id, label="", group="state", shape="diamond"))
        edges.append(GraphEdge(from_id=init_id, to_id=state_id_map[fsm.states[0]]))

    for t in fsm.transitions:
        from_id = state_id_map.get(t.from_state)
        to_id = state_id_map.get(t.to_state)
        if from_id and to_id:
            edges.append(GraphEdge(from_id=from_id, to_id=to_id, label=t.condition))

    return GraphData(nodes=nodes, edges=edges, title=f"FSM: {fsm.name}", graph_type="fsm")


def trace_to_graph(result: "TraceResult") -> GraphData:
    """将 TraceResult 转换为 GraphData"""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    idx = 0

    def _walk(node: "TraceNode", parent_id: str | None = None, depth: int = 0):
        nonlocal idx
        nid = f"t{idx}"
        idx += 1

        label = f"{node.signal_name} @ {node.module_name}"
        group = "signal"
        title = f"信号: {node.signal_name}\n模块: {node.module_name}\n角色: {node.role}\n{node.description}"

        nodes.append(GraphNode(
            id=nid, label=label, group=group, title=title, shape="box",
            parent_id=parent_id or "", depth=depth,
        ))

        if parent_id is not None:
            edges.append(GraphEdge(from_id=parent_id, to_id=nid, label=node.role))

        for child in node.children:
            _walk(child, nid, depth + 1)

    _walk(result.root)
    return GraphData(nodes=nodes, edges=edges, title=f"信号追踪: {result.root.signal_name}", graph_type="dataflow")


def clock_tree_to_graph(
    result: "ClockTreeResult", max_nodes: int = 100, show_leaves: bool = False
) -> GraphData:
    """将 ClockTreeResult 转换为 GraphData

    Args:
        result: 时钟树分析结果
        max_nodes: 最大节点数，超过时聚合同类型叶子模块
        show_leaves: 是否显示叶子模块（无子实例的模块）
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    path_to_id: dict[str, str] = {}
    idx = 0

    # 预先计算哪些模块有子实例（用于判断 leaf）
    all_paths = {m.instance_path for m in _all_clock_modules(result)}
    has_children_paths: set[str] = set()
    for p in all_paths:
        for other in all_paths:
            if other != p and other.startswith(p + "."):
                has_children_paths.add(p)
                break

    for gi, group in enumerate(result.clock_domains):
        # 时钟域作为容器节点
        domain_id = f"cd{gi}"
        domain_label = f"{group.root_clock_name} ({group.edge})"
        gated_info = ""
        if group.is_gated:
            gated_info = f"\n门控来源: {group.gated_from or 'unknown'}"
            if group.gating_cell_path:
                gated_info += f"\n门控单元: {group.gating_cell_path}"
            domain_label += " [gated]"

        domain_title = f"时钟域: {group.root_clock_name}\n模块数: {group.module_count}{gated_info}"
        nodes.append(GraphNode(
            id=domain_id, label=domain_label, group="clock",
            title=domain_title, shape="box",
        ))

        # 门控时钟链：在 domain 和模块之间添加门控节点
        gated_node_id = ""
        if group.is_gated and group.gating_cell_path:
            gated_node_id = f"gated{gi}"
            gated_label = f"gated: {group.gated_from or group.root_clock_name}"
            gated_title = f"门控时钟\n来源: {group.gated_from or 'unknown'}\n单元: {group.gating_cell_path}"
            nodes.append(GraphNode(
                id=gated_node_id, label=gated_label, group="clock",
                title=gated_title, shape="diamond",
            ))
            edges.append(GraphEdge(from_id=domain_id, to_id=gated_node_id))

        # 收集该 domain 的模块，过滤叶子
        domain_modules: list = []
        for m in group.modules:
            is_leaf = m.instance_path not in has_children_paths
            if not show_leaves and is_leaf and not m.is_gated_cell:
                continue  # 隐藏普通叶子模块
            domain_modules.append(m)

        for m in domain_modules:
            nid = f"n{idx}"
            idx += 1
            label = f"{m.instance_name}: {m.module_type}"
            gated = " ⚙" if m.is_gated_cell else ""
            title = f"模块: {m.module_type}\n时钟: {m.local_clock_signal}{gated}\n路径: {m.instance_path}"
            mod_group = classify_module(m.module_type) if not m.is_gated_cell else "clock"
            nodes.append(GraphNode(id=nid, label=label, group=mod_group, title=title, shape="box"))
            path_to_id[m.instance_path] = nid

            # 连接到父节点、门控节点或时钟域
            if "." in m.instance_path:
                parent_path = m.instance_path.rsplit(".", 1)[0]
                if parent_path in path_to_id:
                    edges.append(GraphEdge(from_id=path_to_id[parent_path], to_id=nid))
                elif gated_node_id and parent_path == group.gating_cell_path:
                    edges.append(GraphEdge(from_id=gated_node_id, to_id=nid))
                elif gated_node_id:
                    edges.append(GraphEdge(from_id=gated_node_id, to_id=nid))
                else:
                    edges.append(GraphEdge(from_id=domain_id, to_id=nid))
            else:
                connect_from = gated_node_id if gated_node_id else domain_id
                edges.append(GraphEdge(from_id=connect_from, to_id=nid))

    # 隐藏叶子后，如果节点仍过多，聚合叶子模块
    if len(nodes) > max_nodes:
        nodes, edges = _aggregate_leaf_nodes(nodes, edges, max_nodes)

    return GraphData(nodes=nodes, edges=edges, title=f"时钟树: {result.top_module}", graph_type="clock")


def _all_clock_modules(result: "ClockTreeResult") -> list:
    """提取 ClockTreeResult 中所有模块"""
    modules = []
    for group in result.clock_domains:
        modules.extend(group.modules)
    return modules


# ── HTML 可视化生成器 ──

_GROUP_COLORS = {
    "top":        {"background": "#1e3a5f", "border": "#0f172a"},
    "controller": {"background": "#4f46e5", "border": "#3730a3"},
    "arithmetic": {"background": "#f59e0b", "border": "#d97706"},
    "memory":     {"background": "#8b5cf6", "border": "#7c3aed"},
    "interface":  {"background": "#06b6d4", "border": "#0891b2"},
    "basic":      {"background": "#94a3b8", "border": "#64748b"},
    "module":     {"background": "#3b82f6", "border": "#1d4ed8"},
    "signal":     {"background": "#22c55e", "border": "#16a34a"},
    "state":      {"background": "#f59e0b", "border": "#d97706"},
    "clock":      {"background": "#8b5cf6", "border": "#7c3aed"},
    "cycle":      {"background": "#ef4444", "border": "#dc2626"},
    "aggregated": {"background": "#e2e8f0", "border": "#94a3b8"},
}

_GROUP_LABELS = {
    "top":        "顶层",
    "controller": "控制器",
    "arithmetic": "运算单元",
    "memory":     "存储器",
    "interface":  "接口",
    "basic":      "基础单元",
    "module":     "模块",
    "signal":     "信号",
    "state":      "状态",
    "clock":      "时钟域",
    "cycle":      "循环引用",
    "aggregated": "聚合",
}

_ASSET_FILES = {
    "cytoscape.min.js": "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js",
    "dagre.min.js": "https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js",
    "cytoscape-dagre.min.js": "https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js",
}


class HtmlVisualizer:
    """生成交互式 HTML 图谱"""

    _template: Template | None = None

    @classmethod
    def _load_template(cls) -> Template:
        if cls._template is None:
            html_text = _resource_files("verilog_mcp_server.templates") \
                .joinpath("visualizer.html").read_text(encoding="utf-8")
            cls._template = Template(html_text)
        return cls._template

    @staticmethod
    def _ensure_assets() -> str:
        """确保静态资源存在，返回 assets 目录路径"""
        assets_dir = os.path.join(os.getcwd(), ".verilog_mcp", "assets")
        os.makedirs(assets_dir, exist_ok=True)
        for filename, url in _ASSET_FILES.items():
            filepath = os.path.join(assets_dir, filename)
            if not os.path.exists(filepath):
                try:
                    urlretrieve(url, filepath)
                except Exception:
                    pass
        return assets_dir

    @staticmethod
    def _read_inline_scripts() -> str:
        """读取所有 JS 资源并拼接为内联 <script> 标签"""
        assets_dir = HtmlVisualizer._ensure_assets()
        parts: list[str] = []
        for filename in _ASSET_FILES:
            filepath = os.path.join(assets_dir, filename)
            try:
                js_content = open(filepath, encoding="utf-8").read()
                parts.append(f"<script>{js_content}</script>")
            except Exception:
                # fallback: CDN
                url = _ASSET_FILES[filename]
                parts.append(f'<script src="{url}"></script>')
        return "\n".join(parts)

    @staticmethod
    def generate(graph_data: GraphData, output_path: str | None = None) -> str:
        """生成自包含 HTML 文件，返回文件路径"""
        if output_path is None:
            vis_dir = os.path.join(os.getcwd(), ".verilog_mcp", "visualizations")
            os.makedirs(vis_dir, exist_ok=True)
            safe_title = re.sub(r'[^a-zA-Z0-9_一-鿿]', '_', graph_data.title)[:60]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = os.path.join(vis_dir, f"{safe_title}_{ts}.html")

        inline_scripts = HtmlVisualizer._read_inline_scripts()

        nodes_json = json.dumps([
            {
                "id": n.id, "label": n.label, "group": n.group,
                "title": n.title, "shape": n.shape,
                "parent_id": n.parent_id, "depth": n.depth,
            }
            for n in graph_data.nodes
        ], ensure_ascii=False, indent=2)

        edges_json = json.dumps([
            {
                "from": e.from_id, "to": e.to_id, "label": e.label,
                "dashes": e.dashes, "arrows": e.arrows,
            }
            for e in graph_data.edges
        ], ensure_ascii=False, indent=2)

        legend_items = "\n".join(
            f'<div class="legend-item"><div class="legend-dot" style="background:{c["background"]}"></div>{_GROUP_LABELS.get(g, g)}</div>'
            for g, c in _GROUP_COLORS.items()
            if any(n.group == g for n in graph_data.nodes)
        )

        template = HtmlVisualizer._load_template()
        html = template.safe_substitute(
            title=graph_data.title,
            inline_scripts=inline_scripts,
            nodes_json=nodes_json,
            edges_json=edges_json,
            legend_items=legend_items,
            graph_type=graph_data.graph_type,
        )

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return output_path


# ── Mermaid 统一生成 ──

def graph_to_mermaid(graph_data: GraphData) -> str:
    """从 GraphData 统一生成 Mermaid 文本

    根据 graph_type 选择对应的 Mermaid 图表类型：
    - hierarchy → flowchart TD
    - fsm → stateDiagram-v2
    - dataflow → flowchart LR
    - clock → flowchart TD (with subgraph per clock domain)
    """
    if graph_data.graph_type == "hierarchy":
        return _mermaid_hierarchy(graph_data)
    elif graph_data.graph_type == "fsm":
        return _mermaid_fsm(graph_data)
    elif graph_data.graph_type == "dataflow":
        return _mermaid_dataflow(graph_data)
    elif graph_data.graph_type == "clock":
        return _mermaid_clock(graph_data)
    return f"%% Unsupported graph type: {graph_data.graph_type}"


def _mermaid_hierarchy(g: GraphData) -> str:
    lines = ["flowchart TD"]
    for node in g.nodes:
        safe_label = node.label.replace('"', "'")
        lines.append(f'    {node.id}["{safe_label}"]')
        if node.group:
            lines.append(f"    class {node.id} {node.group}")
    for edge in g.edges:
        if edge.dashes:
            lines.append(f"    {edge.from_id} -.->|cycle| {edge.to_id}")
        else:
            lines.append(f"    {edge.from_id} --> {edge.to_id}")
    lines.append("")
    lines.append("    classDef top fill:#1e3a5f,stroke:#0f172a,color:#fff")
    lines.append("    classDef controller fill:#4f46e5,stroke:#3730a3,color:#fff")
    lines.append("    classDef arithmetic fill:#f59e0b,stroke:#d97706,color:#000")
    lines.append("    classDef memory fill:#8b5cf6,stroke:#7c3aed,color:#fff")
    lines.append("    classDef interface fill:#06b6d4,stroke:#0891b2,color:#000")
    lines.append("    classDef basic fill:#94a3b8,stroke:#64748b,color:#000")
    lines.append("    classDef module fill:#3b82f6,stroke:#1d4ed8,color:#fff")
    lines.append("    classDef cycle fill:#EF9A9A,stroke:#D32F2F,color:#000,stroke-dasharray:5")
    lines.append("    classDef aggregated fill:#e2e8f0,stroke:#94a3b8,color:#334155,stroke-dasharray:5")
    return "\n".join(lines)


def _mermaid_fsm(g: GraphData) -> str:
    lines = ["stateDiagram-v2"]
    state_nodes = [n for n in g.nodes if n.group == "state"]
    init_nodes = [n for n in g.nodes if n.shape == "diamond"]
    if state_nodes:
        lines.append(f"    [*] --> {state_nodes[0].label.replace(' ', '_')}")
    for edge in g.edges:
        safe_from = edge.from_id
        safe_to = edge.to_id
        # Map edge id back to labels
        from_node = next((n for n in g.nodes if n.id == edge.from_id), None)
        to_node = next((n for n in g.nodes if n.id == edge.to_id), None)
        if from_node and from_node.shape == "diamond":
            continue  # skip init diamond edges
        if from_node:
            safe_from = from_node.label.replace(" ", "_")
        if to_node:
            safe_to = to_node.label.replace(" ", "_")
        if edge.label:
            safe_cond = edge.label.replace('"', "'")
            lines.append(f"    {safe_from} --> {safe_to} : {safe_cond}")
        else:
            lines.append(f"    {safe_from} --> {safe_to}")
    return "\n".join(lines)


def _mermaid_dataflow(g: GraphData) -> str:
    lines = ["flowchart LR"]
    for node in g.nodes:
        safe_label = node.label.replace('"', "'")
        lines.append(f'    {node.id}["{safe_label}"]')
    for edge in g.edges:
        lines.append(f"    {edge.from_id} --> {edge.to_id}")
    return "\n".join(lines)


def _mermaid_clock(g: GraphData) -> str:
    lines = ["%%{init: {'theme': 'base'}}%%", "flowchart TD"]

    # 定义所有节点（domain + module + gated）
    for node in g.nodes:
        safe_label = node.label.replace('"', "'")
        lines.append(f'    {node.id}["{safe_label}"]')
        if node.group:
            lines.append(f"    class {node.id} {node.group}")

    # 按 domain 分组输出 subgraph：找到从每个 domain 可达的所有非-domain 节点
    domain_nodes = [n for n in g.nodes if n.group == "clock"]
    non_domain_ids = {n.id for n in g.nodes if n.group != "clock"}

    for dn in domain_nodes:
        domain_label = dn.label.replace('"', "'")
        lines.append(f"  subgraph {dn.id}_g[\"{domain_label}\"]")
        # BFS 找从 domain 可达的非 domain 节点
        reachable: set[str] = set()
        queue = [dn.id]
        visited = {dn.id}
        while queue:
            curr = queue.pop(0)
            for e in g.edges:
                if e.from_id == curr and e.to_id in non_domain_ids and e.to_id not in visited:
                    visited.add(e.to_id)
                    reachable.add(e.to_id)
                    queue.append(e.to_id)
        for rid in sorted(reachable):
            node = next((n for n in g.nodes if n.id == rid), None)
            if node:
                safe_label = node.label.replace('"', "'")
                lines.append(f"    {node.id}[\"{safe_label}\"]")
        lines.append(f"  end")

    # 输出所有边
    for edge in g.edges:
        if edge.dashes:
            lines.append(f"    {edge.from_id} -.-> {edge.to_id}")
        else:
            lines.append(f"    {edge.from_id} --> {edge.to_id}")

    lines.append("")
    lines.append("    classDef clock fill:#8b5cf6,stroke:#7c3aed,color:#fff")
    lines.append("    classDef controller fill:#4f46e5,stroke:#3730a3,color:#fff")
    lines.append("    classDef arithmetic fill:#f59e0b,stroke:#d97706,color:#000")
    lines.append("    classDef memory fill:#8b5cf6,stroke:#7c3aed,color:#fff")
    lines.append("    classDef interface fill:#06b6d4,stroke:#0891b2,color:#000")
    lines.append("    classDef basic fill:#94a3b8,stroke:#64748b,color:#000")
    lines.append("    classDef module fill:#3b82f6,stroke:#1d4ed8,color:#fff")
    lines.append("    classDef aggregated fill:#e2e8f0,stroke:#94a3b8,color:#334155,stroke-dasharray:5")
    return "\n".join(lines)
