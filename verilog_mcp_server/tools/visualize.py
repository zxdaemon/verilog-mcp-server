"""
可视化 MCP Tool

提供 rtl_visualize 统一可视化入口，支持 Mermaid 和 HTML 两种输出格式。
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp import FastMCP
    from ..database.index_store import IndexStore


def register_tools(mcp: "FastMCP", index_store: "IndexStore"):
    """注册可视化工具"""

    from ..analysis.hierarchy import HierarchyBuilder
    from ..analysis.fan_in import DataflowTracer
    from ..analysis.fsm_detector import FSMDetector
    from ..analysis.clock_tree import ClockTreeBuilder
    from ..database.errors import DomainError
    from ..analysis.visualizer import (
        hierarchy_to_graph, fsm_to_graph, trace_to_graph,
        clock_tree_to_graph, graph_to_mermaid, HtmlVisualizer,
    )

    @mcp.tool()
    def rtl_visualize(
        target: str,
        diagram_type: str = "auto",
        output_format: str = "mermaid",
        max_depth: int = 10,
        max_nodes: int = 100,
    ) -> str:
        """生成 RTL 设计的可视化图谱

        Args:
            target: 模块名或信号名
            diagram_type: 图类型 — "hierarchy"（层次树）、"fsm"（状态机）、
                "dataflow"（数据流）、"clock"（时钟域）、"auto"（自动检测，默认）
            output_format: 输出格式 — "mermaid"（Mermaid 文本，默认）或 "html"（交互式 HTML）
            max_depth: 最大遍历深度（默认 10）
            max_nodes: 最大节点数，超过时自动聚合同类型叶子实例（默认 100）
        """
        # auto 检测图类型
        if diagram_type == "auto":
            diagram_type = _detect_diagram_type(target, index_store)

        # 根据图类型调用对应的分析引擎
        if diagram_type == "hierarchy":
            builder = HierarchyBuilder(index_store)
            mod = index_store.get_module(target)
            if not mod:
                return f"❌ 模块 '{target}' 不存在于索引中"
            root = builder.build_tree(target, max_depth)
            graph_data = hierarchy_to_graph(root, max_nodes=max_nodes)
            if output_format == "mermaid":
                return graph_to_mermaid(graph_data)
            else:
                path = HtmlVisualizer.generate(graph_data)
                return f"✅ HTML 图谱已生成: {path}"

        elif diagram_type == "fsm":
            detector = FSMDetector(index_store)
            mod = index_store.get_module(target)
            if not mod:
                return f"❌ 模块 '{target}' 不存在于索引中"
            result = detector.detect_fsms(target)
            if result.fsm_count == 0:
                return f"ℹ️ 模块 '{target}' 中未检测到状态机"
            # 合并多个 FSM 到一个图
            from ..analysis.visualizer import GraphData, GraphNode, GraphEdge
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
            graph_data = GraphData(nodes=all_nodes, edges=all_edges, title=f"FSM: {target}", graph_type="fsm")
            if output_format == "mermaid":
                return graph_to_mermaid(graph_data)
            else:
                path = HtmlVisualizer.generate(graph_data)
                return f"✅ HTML 图谱已生成: {path}"

        elif diagram_type == "dataflow":
            tracer = DataflowTracer(index_store)
            mod = index_store.get_module(target)
            if not mod:
                # 尝试作为信号名
                all_mods = index_store.get_all_modules()
                found_mod = None
                for m in all_mods:
                    for sig in m.signals:
                        if sig.name == target:
                            found_mod = m.name
                            break
                    if found_mod:
                        break
                if found_mod:
                    mod_name = found_mod
                else:
                    return f"❌ '{target}' 既不是模块名也不是信号名"
            else:
                mod_name = target

            try:
                result = tracer.trace_signal(target, mod_name, "fan_in", max_depth)
            except (ValueError, DomainError) as e:
                return f"❌ 追踪失败: {e}"

            if result.nodes_count <= 1:
                return f"ℹ️ 未找到信号 '{target}' 的追踪路径"

            graph_data = trace_to_graph(result)
            if output_format == "mermaid":
                return graph_to_mermaid(graph_data)
            else:
                path = HtmlVisualizer.generate(graph_data)
                return f"✅ HTML 图谱已生成: {path}"

        elif diagram_type == "clock":
            builder = ClockTreeBuilder(index_store)
            mod = index_store.get_module(target)
            if not mod:
                return f"❌ 模块 '{target}' 不存在于索引中"
            result = builder.build(target, max_depth)
            if not result.clock_domains:
                return f"ℹ️ 未在 '{target}' 及其子模块中检测到时钟域"
            graph_data = clock_tree_to_graph(result, max_nodes=max_nodes)
            if output_format == "mermaid":
                return graph_to_mermaid(graph_data)
            else:
                path = HtmlVisualizer.generate(graph_data)
                return f"✅ HTML 图谱已生成: {path}"

        else:
            return f"❌ 未知图类型: '{diagram_type}'，支持: hierarchy, fsm, dataflow, clock, auto"


def _detect_diagram_type(target: str, index_store: "IndexStore") -> str:
    """自动检测目标应使用的图类型"""
    mod = index_store.get_module(target)

    if mod:
        # 有子例化 → 层次图
        if mod.instances:
            return "hierarchy"
        # 无子例化但有 always+case → FSM
        for ab in mod.always_blocks:
            for stmt in ab.statements:
                if "case" in stmt.lower():
                    return "fsm"
        # 默认层次图
        return "hierarchy"

    # 不是模块 → 尝试作为信号名
    all_mods = index_store.get_all_modules()
    for m in all_mods:
        for sig in m.signals:
            if sig.name == target:
                return "dataflow"

    # 找不到 → 默认层次图（会让后续模块检查报错）
    return "hierarchy"
