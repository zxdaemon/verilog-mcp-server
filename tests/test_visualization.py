"""测试可视化功能 — Mermaid 统一生成、GraphData 转换、HTML 生成"""

import os
import tempfile

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, SignalDef, AlwaysBlockInfo, InstanceDef, DriverInfo, LoadInfo,
)
from verilog_mcp_server.analysis.hierarchy import HierarchyBuilder
from verilog_mcp_server.analysis.fsm_detector import FSMDetector, FSM, Transition
from verilog_mcp_server.analysis.fan_in import DataflowTracer, TraceNode, TraceResult
from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
from verilog_mcp_server.analysis.visualizer import (
    GraphData, GraphNode, GraphEdge,
    hierarchy_to_graph, fsm_to_graph, trace_to_graph, clock_tree_to_graph,
    graph_to_mermaid, HtmlVisualizer,
)


# ── 测试 fixtures ──

def make_hierarchy_store() -> IndexStore:
    """创建有层次结构的 IndexStore"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="top", file_path="top.v", line_start=1, line_end=50,
        ports=[PortDef(name="clk", direction="input")],
        instances=[
            InstanceDef(module_type="cpu", instance_name="u_cpu",
                        port_connections={"clk": "clk"}, file_path="top.v", line=10),
            InstanceDef(module_type="uart", instance_name="u_uart",
                        port_connections={"clk": "clk"}, file_path="top.v", line=15),
        ],
    ))
    store.add_module(ModuleDef(
        name="cpu", file_path="cpu.v", line_start=1, line_end=30,
        ports=[PortDef(name="clk", direction="input")],
        instances=[
            InstanceDef(module_type="alu", instance_name="u_alu",
                        port_connections={"clk": "clk"}, file_path="cpu.v", line=5),
        ],
    ))
    store.add_module(ModuleDef(
        name="uart", file_path="uart.v", line_start=1, line_end=20,
        ports=[PortDef(name="clk", direction="input")],
    ))
    store.add_module(ModuleDef(
        name="alu", file_path="alu.v", line_start=1, line_end=15,
        ports=[PortDef(name="clk", direction="input")],
    ))
    return store


def make_fsm_store() -> IndexStore:
    """创建带 FSM 的 IndexStore"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="traffic_light", file_path="tl.v", line_start=1, line_end=50,
        ports=[PortDef(name="clk", direction="input")],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk",
                block_type="sequential",
                statements=["state <= next_state;"],
            ),
            AlwaysBlockInfo(
                sensitivity_list="*",
                block_type="combinational",
                statements=[
                    "case (state)",
                    "  RED: next_state = GREEN;",
                    "  GREEN: next_state = YELLOW;",
                    "  YELLOW: next_state = RED;",
                    "endcase",
                ],
            ),
        ],
        signals=[
            SignalDef(name="state", var_type="reg", drivers=[DriverInfo(type="always_block", source="state <= next_state")]),
            SignalDef(name="next_state", var_type="reg"),
        ],
    ))
    return store


def make_trace_result() -> TraceResult:
    """创建测试用 TraceResult"""
    root = TraceNode(
        signal_name="data", module_name="top", instance_path="top",
        role="start", description="追踪起点",
    )
    child1 = TraceNode(
        signal_name="data", module_name="top", instance_path="top",
        role="assign_rhs", description="assign data = next_data",
        depth=1,
    )
    child2 = TraceNode(
        signal_name="data", module_name="cpu", instance_path="top.u_cpu",
        role="port_input_up", description="端口连接",
        depth=1,
    )
    root.children = [child1, child2]
    return TraceResult(root=root, nodes_count=3, max_depth=1)


# ── graph_to_mermaid 统一生成测试 ──

def test_graph_to_mermaid_hierarchy():
    """hierarchy GraphData → Mermaid"""
    store = make_hierarchy_store()
    builder = HierarchyBuilder(store)
    root = builder.build_tree("top")
    graph = hierarchy_to_graph(root)
    mermaid = graph_to_mermaid(graph)

    assert mermaid.startswith("flowchart TD")
    assert "top" in mermaid
    assert "u_cpu" in mermaid or "cpu" in mermaid
    assert "-->" in mermaid


def test_graph_to_mermaid_hierarchy_classdef():
    """hierarchy Mermaid 包含样式定义"""
    store = make_hierarchy_store()
    builder = HierarchyBuilder(store)
    root = builder.build_tree("top")
    graph = hierarchy_to_graph(root)
    mermaid = graph_to_mermaid(graph)

    assert "classDef top" in mermaid
    assert "classDef cycle" in mermaid


def test_graph_to_mermaid_fsm():
    """FSM GraphData → Mermaid"""
    fsm = FSM(
        name="test_fsm", module_name="test", state_register="state",
        encoding="symbolic", states=["IDLE", "RUN", "DONE"],
        transitions=[
            Transition(from_state="IDLE", to_state="RUN", condition="start"),
            Transition(from_state="RUN", to_state="DONE", condition="finish"),
        ],
    )
    graph = fsm_to_graph(fsm)
    mermaid = graph_to_mermaid(graph)

    assert mermaid.startswith("stateDiagram-v2")
    assert "[*] -->" in mermaid
    assert "IDLE" in mermaid
    assert "start" in mermaid
    assert "RUN" in mermaid
    assert "DONE" in mermaid


def test_graph_to_mermaid_dataflow():
    """dataflow GraphData → Mermaid"""
    result = make_trace_result()
    graph = trace_to_graph(result)
    mermaid = graph_to_mermaid(graph)

    assert mermaid.startswith("flowchart LR")
    assert "data" in mermaid
    assert "-->" in mermaid


def test_graph_to_mermaid_unsupported_type():
    """不支持的图类型返回注释"""
    graph = GraphData(nodes=[], edges=[], graph_type="unknown")
    mermaid = graph_to_mermaid(graph)
    assert mermaid.startswith("%% Unsupported")


# ── FSM Mermaid 集成测试 ──

def test_fsm_detector_to_mermaid():
    """FSMDetector 检测 → GraphData → Mermaid"""
    store = make_fsm_store()
    detector = FSMDetector(store)
    result = detector.detect_fsms("traffic_light")

    from verilog_mcp_server.analysis.visualizer import GraphData, GraphNode, GraphEdge
    all_nodes = []
    all_edges = []
    for i, fsm in enumerate(result.fsms):
        g = fsm_to_graph(fsm)
        for n in g.nodes:
            n.id = f"f{i}_{n.id}"
        for e in g.edges:
            e.from_id = f"f{i}_{e.from_id}"
            e.to_id = f"f{i}_{e.to_id}"
        all_nodes.extend(g.nodes)
        all_edges.extend(g.edges)

    if all_nodes:
        graph = GraphData(nodes=all_nodes, edges=all_edges, title="FSM", graph_type="fsm")
        mermaid = graph_to_mermaid(graph)
        assert "stateDiagram-v2" in mermaid


# ── GraphData 转换测试 ──

def test_hierarchy_to_graph():
    """HierarchyNode → GraphData 转换"""
    store = make_hierarchy_store()
    builder = HierarchyBuilder(store)
    root = builder.build_tree("top")
    graph = hierarchy_to_graph(root)

    assert len(graph.nodes) >= 4  # top + cpu + uart + alu
    assert len(graph.edges) >= 3  # top->cpu, top->uart, cpu->alu
    assert graph.title.startswith("层次树")
    assert graph.graph_type == "hierarchy"
    # 根节点分类为 top，其他按模块名分类
    assert any(n.group == "top" for n in graph.nodes)
    assert any(n.group == "module" for n in graph.nodes)
    # 验证父子关系
    root_node = next(n for n in graph.nodes if n.group == "top")
    assert root_node.depth == 0
    assert root_node.parent_id == ""
    child_nodes = [n for n in graph.nodes if n.parent_id == root_node.id]
    assert len(child_nodes) >= 2  # cpu + uart


def test_fsm_to_graph():
    """FSM → GraphData 转换"""
    fsm = FSM(
        name="test_fsm", module_name="test", state_register="state",
        encoding="symbolic", states=["A", "B"],
        transitions=[Transition(from_state="A", to_state="B")],
    )
    graph = fsm_to_graph(fsm)

    # 2 状态 + 1 初始标记 = 3 节点
    assert len(graph.nodes) == 3
    assert len(graph.edges) >= 2  # init->A, A->B
    assert graph.graph_type == "fsm"
    assert all(n.group == "state" for n in graph.nodes)


def test_trace_to_graph():
    """TraceResult → GraphData 转换"""
    result = make_trace_result()
    graph = trace_to_graph(result)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert graph.graph_type == "dataflow"
    assert all(n.group == "signal" for n in graph.nodes)
    # 验证父子关系
    root_node = graph.nodes[0]
    assert root_node.depth == 0
    child_nodes = [n for n in graph.nodes if n.parent_id == root_node.id]
    assert len(child_nodes) == 2


# ── HTML 生成测试 ──

def test_html_generation_basic():
    """HTML 文件生成基本测试（Cytoscape.js）"""
    graph = GraphData(
        nodes=[
            GraphNode(id="n0", label="Test Node", group="module", title="details"),
        ],
        edges=[
            GraphEdge(from_id="n0", to_id="n1"),
        ],
        title="Test Graph",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.html")
        result = HtmlVisualizer.generate(graph, path)

        assert result == path
        assert os.path.exists(path)

        content = open(path).read()
        assert "cytoscape" in content.lower()
        assert "Test Node" in content
        assert "Test Graph" in content


def test_html_default_output_path():
    """HTML 默认输出路径"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="X", group="module")],
        edges=[],
        title="DefaultPath",
    )

    result = HtmlVisualizer.generate(graph)
    try:
        assert os.path.exists(result)
        assert ".verilog_mcp" in result
        assert result.endswith(".html")
    finally:
        os.unlink(result)
        # 清理目录
        parent = os.path.dirname(result)
        if os.path.exists(parent) and not os.listdir(parent):
            os.rmdir(parent)


def test_html_contains_legend_colors():
    """HTML legend 包含分组配色"""
    graph = GraphData(
        nodes=[
            GraphNode(id="n0", label="Mod", group="module"),
            GraphNode(id="n1", label="Sig", group="signal"),
        ],
        edges=[],
        title="Groups",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "groups.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "#3b82f6" in content  # module color
        assert "#22c55e" in content  # signal color


def test_html_drill_down_features():
    """HTML 包含钻取导航功能（Back/Reset/面包屑/drillInto）"""
    graph = GraphData(
        nodes=[
            GraphNode(id="n0", label="Top", group="module", parent_id="", depth=0),
            GraphNode(id="n1", label="Sub1", group="module", parent_id="n0", depth=1),
            GraphNode(id="n2", label="Sub2", group="module", parent_id="n0", depth=1),
        ],
        edges=[
            GraphEdge(from_id="n0", to_id="n1"),
            GraphEdge(from_id="n0", to_id="n2"),
        ],
        title="DrillDown Test",
        graph_type="hierarchy",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "drill.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "btn-back" in content
        assert "btn-reset" in content
        assert "breadcrumb" in content
        assert "drillInto" in content
        assert "goUp" in content
        assert "resetView" in content
        assert "childrenMap" in content
        assert "parent_id" in content
        assert "double-click" in content.lower()


def test_html_contains_cytoscape_reference():
    """HTML 包含 Cytoscape.js 引用"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="X", group="module")],
        edges=[],
        title="CytoscapeRef",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "cyto.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "cytoscape" in content
        assert "dagre" in content


def test_html_search_features():
    """HTML 包含搜索功能"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="Node", group="module")],
        edges=[],
        title="Search",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "search.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "search-box" in content
        assert "search-match" in content
        assert "search-dim" in content


def test_html_minimap_features():
    """HTML 包含 MiniMap"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="Node", group="module")],
        edges=[],
        title="MiniMap",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "minimap.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "minimap" in content.lower()


def test_html_png_export():
    """HTML 包含 PNG 导出功能"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="Node", group="module")],
        edges=[],
        title="PNGExport",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "png.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "exportPNG" in content
        assert "cy.png" in content


def test_html_light_theme():
    """HTML 使用亮色主题"""
    graph = GraphData(
        nodes=[GraphNode(id="n0", label="Node", group="module")],
        edges=[],
        title="LightTheme",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "light.html")
        HtmlVisualizer.generate(graph, path)
        content = open(path).read()

        assert "#f8f9fa" in content  # bg-root
        assert "#2563eb" in content  # accent


# ── 集成测试: rtl_visualize 工具 ──

def test_rtl_visualize_hierarchy_mermaid():
    """rtl_visualize 层次图 Mermaid 输出"""
    from verilog_mcp_server.tools.visualize import register_tools
    from mcp.server.fastmcp import FastMCP

    store = make_hierarchy_store()
    mcp = FastMCP("test")
    register_tools(mcp, store)

    # 调用工具
    tool_fn = None
    for tool_info in mcp._tool_manager._tools.values():
        if tool_info.name == "rtl_visualize":
            tool_fn = tool_info.fn
            break

    assert tool_fn is not None
    result = tool_fn(target="top", diagram_type="hierarchy", output_format="mermaid")
    assert "flowchart TD" in result
    assert "top" in result


def test_rtl_visualize_auto_detect():
    """rtl_visualize auto 检测"""
    from verilog_mcp_server.tools.visualize import _detect_diagram_type

    store = make_hierarchy_store()
    assert _detect_diagram_type("top", store) == "hierarchy"


def test_rtl_visualize_nonexistent():
    """rtl_visualize 目标不存在"""
    from verilog_mcp_server.tools.visualize import register_tools
    from mcp.server.fastmcp import FastMCP

    store = IndexStore()
    mcp = FastMCP("test")
    register_tools(mcp, store)

    tool_fn = None
    for tool_info in mcp._tool_manager._tools.values():
        if tool_info.name == "rtl_visualize":
            tool_fn = tool_info.fn
            break

    result = tool_fn(target="nonexistent", diagram_type="hierarchy")
    assert "不存在" in result


# ── 聚合测试 ──

def make_aggregation_store() -> IndexStore:
    """创建有大量同类型实例的 IndexStore（用于测试聚合）"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="top", file_path="top.v", line_start=1, line_end=100,
        ports=[PortDef(name="clk", direction="input")],
        instances=[
            InstanceDef(module_type="buf", instance_name=f"u_buf{i}",
                        port_connections={}, file_path="top.v", line=10 + i)
            for i in range(12)
        ],
    ))
    store.add_module(ModuleDef(
        name="buf", file_path="buf.v", line_start=1, line_end=5,
        ports=[PortDef(name="a", direction="input"), PortDef(name="y", direction="output")],
    ))
    return store


def test_hierarchy_to_graph_with_aggregation():
    """超过 max_nodes 时自动聚合同类型 leaf 实例"""
    store = make_aggregation_store()
    builder = HierarchyBuilder(store)
    root = builder.build_tree("top")

    # 默认 max_nodes=100，12 个 buf 不聚合
    graph = hierarchy_to_graph(root, max_nodes=100)
    assert len(graph.nodes) == 13  # top + 12 buf
    assert all(n.group != "aggregated" for n in graph.nodes)

    # max_nodes=5，应该聚合 12 个 buf 为 1 个聚合节点
    graph_agg = hierarchy_to_graph(root, max_nodes=5)
    assert len(graph_agg.nodes) <= 5
    agg_nodes = [n for n in graph_agg.nodes if n.group == "aggregated"]
    assert len(agg_nodes) == 1
    assert agg_nodes[0].aggregated_count == 12
    assert "buf" in agg_nodes[0].label
    assert "×12" in agg_nodes[0].label


def test_hierarchy_module_classification():
    """classify_module 按名称模式正确分类模块功能"""
    from verilog_mcp_server.analysis.visualizer import classify_module

    assert classify_module("alu") == "arithmetic"
    assert classify_module("ctrl_fsm") == "controller"
    assert classify_module("arbiter_n") == "controller"
    assert classify_module("uart_tx") == "interface"
    assert classify_module("axi_master") == "interface"
    assert classify_module("dmem") == "memory"
    assert classify_module("regfile_32") == "memory"
    assert classify_module("buf") == "basic"
    assert classify_module("mux2") == "basic"
    assert classify_module("my_custom_module") == "module"


# ── 时钟树可视化测试 ──

def test_clock_tree_to_graph():
    """ClockTreeResult → GraphData 转换（含层级折叠和门控链）"""
    from verilog_mcp_server.analysis.clock_tree import (
        ClockTreeResult, ClockDomainGroup, ClockModuleInfo,
    )

    result = ClockTreeResult(top_module="top")
    result.clock_domains.append(ClockDomainGroup(
        root_clock_name="clk", edge="posedge",
        modules=[
            ClockModuleInfo(module_type="cpu", instance_name="u_cpu",
                           instance_path="top.u_cpu", local_clock_signal="clk", edge="posedge"),
            ClockModuleInfo(module_type="alu", instance_name="u_alu",
                           instance_path="top.u_cpu.u_alu", local_clock_signal="clk", edge="posedge"),
            ClockModuleInfo(module_type="buf", instance_name="u_buf",
                           instance_path="top.u_cpu.u_alu.u_buf", local_clock_signal="clk", edge="posedge"),
        ],
    ))

    # show_leaves=False：叶子模块 buf 被隐藏
    graph = clock_tree_to_graph(result, max_nodes=100, show_leaves=False)
    assert graph.graph_type == "clock"
    # 应有 domain + cpu + alu = 3 个节点（buf 是 leaf，被隐藏）
    module_nodes = [n for n in graph.nodes if n.group != "clock"]
    assert len(module_nodes) == 2  # cpu, alu

    # show_leaves=True：显示所有模块
    graph_all = clock_tree_to_graph(result, max_nodes=100, show_leaves=True)
    module_nodes_all = [n for n in graph_all.nodes if n.group != "clock"]
    assert len(module_nodes_all) == 3  # cpu, alu, buf


def test_clock_tree_mermaid():
    """clock GraphData → Mermaid（含 subgraph 和 classDef）"""
    from verilog_mcp_server.analysis.clock_tree import (
        ClockTreeResult, ClockDomainGroup, ClockModuleInfo,
    )

    result = ClockTreeResult(top_module="top")
    result.clock_domains.append(ClockDomainGroup(
        root_clock_name="clk", edge="posedge",
        modules=[
            ClockModuleInfo(module_type="cpu", instance_name="u_cpu",
                           instance_path="top.u_cpu", local_clock_signal="clk", edge="posedge"),
            ClockModuleInfo(module_type="alu", instance_name="u_alu",
                           instance_path="top.u_cpu.u_alu", local_clock_signal="clk", edge="posedge"),
        ],
    ))

    graph = clock_tree_to_graph(result, max_nodes=100)
    mermaid = graph_to_mermaid(graph)

    assert "subgraph" in mermaid
    assert "clk" in mermaid
    assert "classDef clock" in mermaid
    assert "-->" in mermaid


# ── 工具参数测试 ──

def test_rtl_visualize_max_nodes():
    """rtl_visualize 支持 max_nodes 参数"""
    from verilog_mcp_server.tools.visualize import register_tools
    from mcp.server.fastmcp import FastMCP

    store = make_aggregation_store()
    mcp = FastMCP("test")
    register_tools(mcp, store)

    tool_fn = None
    for tool_info in mcp._tool_manager._tools.values():
        if tool_info.name == "rtl_visualize":
            tool_fn = tool_info.fn
            break

    assert tool_fn is not None
    # max_nodes=5 触发聚合
    result = tool_fn(target="top", diagram_type="hierarchy",
                     output_format="mermaid", max_nodes=5)
    assert "flowchart TD" in result
    assert "aggregated" in result or "×" in result
