"""
Level 3 — 智能分析 MCP Tool

基于 analysis/ 层的智能分析引擎，提供模块级高级分析能力：
- FSM 状态机检测
- 时钟域/复位域分析
- Always 块分类
- 跨时钟域信号检查
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from mcp import FastMCP
    from ..database.index_store import IndexStore


def register_tools(mcp: "FastMCP", index_store: "IndexStore"):
    """注册 Level 3 分析工具"""

    from ..analysis.fsm_detector import FSMDetector
    from ..analysis.clock_analyzer import ClockAnalyzer
    from ..analysis.always_classify import AlwaysClassifier
    from ..analysis.clock_tree import ClockTreeBuilder
    from ..analysis.dataflow import DataflowTracer
    from ..database.errors import DomainError

    # 引擎实例 — 只创建一次
    fsm_detector = FSMDetector(index_store)
    clock_analyzer = ClockAnalyzer(index_store)
    always_classifier = AlwaysClassifier(index_store)
    clock_tree_builder = ClockTreeBuilder(index_store)

    @mcp.tool()
    def rtl_detect_fsm(module_name: str) -> str:
        """检测模块中的有限状态机，返回状态编码、转移表、输出逻辑

        Args:
            module_name: 模块名称
        """
        try:
            result = fsm_detector.detect_fsms(module_name)
        except ValueError as e:
            return f"❌ {e}"
        except DomainError as e:
            return f"❌ {e}"


    @mcp.tool()
    def rtl_clock_domains(module_name: str) -> str:
        """分析指定模块的时钟域，列出每个时钟驱动的信号

        Args:
            module_name: 模块名称
        """
        try:
            result = clock_analyzer.analyze(module_name)
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_reset_domains(module_name: str) -> str:
        """分析模块的复位域，标记同步/异步、电平极性

        Args:
            module_name: 模块名称
        """
        try:
            result = clock_analyzer.analyze(module_name)
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_always_classify(module_name: str) -> str:
        """分类模块中所有 always 块（时序/组合/锁存器）

        Args:
            module_name: 模块名称
        """
        try:
            result = always_classifier.classify(module_name)
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_cross_domain_signals(module_name: str) -> str:
        """列出模块中跨时钟域的信号

        Args:
            module_name: 模块名称
        """
        try:
            result = clock_analyzer.analyze(module_name)

            domains = result.clock_domains
            if len(domains) < 2:
                return f"ℹ️ 模块 `{module_name}` 只有一个时钟域，无需跨时钟域检查"

            sig_domains: dict[str, list[str]] = defaultdict(list)
            for d in domains:
                for sig in d.signals:
                    sig_domains[sig].append(d.clock_name)

            cross_signals = {s: ds for s, ds in sig_domains.items() if len(ds) > 1}

            lines = [
                f"# 跨时钟域信号: {module_name}",
                f"",
            ]
            if cross_signals:
                lines.append(f"**发现 {len(cross_signals)} 个跨时钟域信号**")
                lines.append(f"")
                lines.append(f"| 信号 | 所属时钟域 | 风险 | 同步器 |")
                lines.append(f"|------|-----------|------|--------|")
                for cd in analysis.cross_domain_signals:
                    sig = cd["signal"]
                    clks = cd["clock_domains"]
                    risk = cd.get("risk", "高")
                    sync = cd.get("synchronizer", "")
                    sync_str = {"two_flop": "双触发器", "handshake": "握手"}.get(sync, "无")
                    risk_icon = "✅" if risk == "低" else "⚠️"
                    lines.append(f"| `{sig}` | {', '.join(clks)} | {risk_icon} {risk} | {sync_str} |")
                lines.append(f"")
                unsynced = [cd for cd in analysis.cross_domain_signals if not cd.get("synchronizer")]
                if unsynced:
                    lines.append(f"> ⚠️ {len(unsynced)} 个信号未检测到同步器，建议添加")
                else:
                    lines.append(f"> ✅ 所有跨时钟域信号均有同步器保护")
            else:
                lines.append(f"✅ 未检测到跨时钟域信号")
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_clock_tree(
        top_module: str,
        max_depth: int = 10,
        output_format: str = "text",
        gated_clock_patterns: str = "",
    ) -> str:
        """展示设计时钟域结构图

        从顶层模块出发，遍历模块层次树，分析每个模块的时钟域，
        追踪时钟信号在层次间的传播路径，按时钟域分组展示所有模块。

        Args:
            top_module: 顶层模块名
            max_depth: 最大层次深度（默认 10）
            output_format: 输出格式 — "text"（ASCII树状图，默认）或 "mermaid"（流程图）
            gated_clock_patterns: 逗号分隔的门控时钟模块名模式（如 "gated_clk_cell,icg"）

        Returns:
            时钟域结构图
        """
        try:
            if gated_clock_patterns:
                patterns = [p.strip() for p in gated_clock_patterns.split(",") if p.strip()]
                clock_tree_builder._gated_patterns = patterns

            result = clock_tree_builder.build(top_module, max_depth)

            if not result.clock_domains:
                return f"ℹ️ 未在 '{top_module}' 及其子模块中检测到时钟域"

            if output_format == "mermaid":
                from ..analysis.visualizer import clock_tree_to_graph, graph_to_mermaid
                return graph_to_mermaid(clock_tree_to_graph(result))
            else:
                return clock_tree_builder.format_text_tree(result)

        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_port_dataflow(
        module_name: str, port_name: str, direction: str = "both", max_depth: int = 5
    ) -> str:
        """追踪模块端口信号的跨层级数据流

        支持穿透例化边界，追踪端口信号的最终驱动源或负载。

        Args:
            module_name: 模块名称
            port_name: 端口名称
            direction: 追踪方向 — "fan_in"（向上追驱动源）、"fan_out"（向上追负载）、"both"（双向，默认）
            max_depth: 最大穿透深度（默认 5）
        """
        tracer = DataflowTracer(index_store)
        try:
            result = tracer.trace_port_dataflow(
                module_name, port_name, direction=direction, max_depth=max_depth
            )
            if result.nodes_count <= 1:
                return (
                    f"# 端口数据流: {module_name}.{port_name}\n\n"
                    f"ℹ️ 未追踪到数据流路径（端口可能未连接或无内部使用）"
                )
            return DataflowTracer.format_trace_result(
                result, title=f"端口数据流: {module_name}.{port_name}"
            )
        except ValueError as e:
            return (
                f"# 端口数据流: {module_name}.{port_name}\n\n"
                f"ℹ️ 端口或模块不存在: {e}"
            )
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_parameter_values(module_name: str) -> str:
        """
        获取模块的参数传播值

        从指定顶层模块开始 BFS 遍历例化树，传播参数实际值。

        Args:
            module_name: 顶层模块名

        Returns:
            该模块及其子模块的参数传播结果
        """
        from ..analysis.param_propagator import ParamPropagator

        top = index_store.get_module(module_name)
        if top is None:
            results = index_store.search_modules(module_name)
            if results:
                top = results[0]
                module_name = top.name
            else:
                return f"未找到模块 '{module_name}'"

        propagator = ParamPropagator(index_store, top_module=module_name)
        resolved = propagator.propagate()

        if not resolved:
            return f"模块 '{module_name}' 无参数传播数据"

        lines = [f"# 参数传播: {module_name}\n"]
        for mod_name, params in sorted(resolved.items()):
            lines.append(ParamPropagator.format_params(mod_name, params))
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_sva_properties(module_name: str) -> str:
        """
        获取模块的 SVA 断言（property/sequence/assert）

        Args:
            module_name: 模块名

        Returns:
            模块中所有 SVA 断言列表
        """
        from ..database.errors import ModuleNotFoundError
        try:
            mod = index_store.get_module(module_name)
            if mod is None:
                results = index_store.search_modules(module_name)
                if results:
                    mod = results[0]
                else:
                    return f"未找到模块 '{module_name}'"
        except ModuleNotFoundError:
            return f"未找到模块 '{module_name}'"

        assertions = mod.assertions
        if not assertions:
            return f"模块 '{mod.name}' 没有 SVA 断言"

        lines = [f"模块 '{mod.name}' 的 SVA 断言 ({len(assertions)}):\n"]
        for sva in assertions:
            kind = sva.kind or "assert"
            lines.append(f"### {sva.name or '(匿名)'}")
            lines.append(f"- 类型: {kind}")
            if sva.clock:
                lines.append(f"- 时钟: {sva.clock}")
            if sva.expression:
                lines.append(f"- 表达式: {sva.expression[:100]}")
            lines.append(f"- 位置: `{sva.file_path}` 行 {sva.line}")
            lines.append("")

        return "\n".join(lines)
