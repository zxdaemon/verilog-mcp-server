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

        if result.fsm_count == 0:
            return f"ℹ️ 模块 `{module_name}` 中未检测到有限状态机（未找到 `case` + `next_state` 模式）"

        lines = [
            f"# FSM 检测结果: {module_name}",
            f"",
            f"**检测到 {result.fsm_count} 个状态机**",
            f"",
        ]
        for i, fsm in enumerate(result.fsms):
            lines.append(f"---")
            lines.append(f"## FSM {i+1}: `{fsm.name}`")
            lines.append(f"")
            lines.append(f"| 属性 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 状态寄存器 | `{fsm.state_register}` |")
            lines.append(f"| 次态信号 | `{fsm.next_state_signal or '无'}` |")
            lines.append(f"| 编码风格 | **{fsm.encoding.upper()}** |")
            lines.append(f"| 类型 | {'Mealy' if fsm.is_mealy else 'Moore'} |")
            lines.append(f"| 状态数量 | {len(fsm.states)} |")
            lines.append(f"")

            lines.append(f"### 状态定义")
            for s in fsm.states:
                lines.append(f"- `{s}`")
            lines.append(f"")

            if fsm.transitions:
                lines.append(f"### 状态转移表")
                lines.append(f"| 当前状态 | 下一状态 | 条件 |")
                lines.append(f"|----------|----------|------|")
                for t in fsm.transitions:
                    cond = f"`{t.condition}`" if t.condition else "—"
                    lines.append(f"| `{t.from_state}` | `{t.to_state}` | {cond} |")
                lines.append(f"")

        return "\n".join(lines)

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

        if not result.clock_domains:
            return f"ℹ️ 模块 `{module_name}` 中未检测到时钟域"

        lines = [
            f"# 时钟域分析: {module_name}",
            f"",
            f"**检测到 {len(result.clock_domains)} 个时钟域**",
            f"",
        ]
        for cd in result.clock_domains:
            lines.append(f"## 时钟域: `{cd.clock_name}`")
            lines.append(f"")
            lines.append(f"- **边沿**: {cd.edge}")
            lines.append(f"- **驱动信号数**: {len(cd.signals)}")
            if cd.signals:
                lines.append(f"- **信号列表**:")
                for sig in cd.signals:
                    lines.append(f"  - `{sig}`")
            lines.append(f"")
            if cd.resets:
                lines.append(f"- **关联复位**:")
                for r in cd.resets:
                    lines.append(f"  - `{r.signal}` ({r.type}, {r.polarity})")
                lines.append(f"")

        return "\n".join(lines)

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

        lines = [
            f"# 复位域分析: {module_name}",
            f"",
        ]

        all_resets = result.async_resets + result.sync_resets
        if not all_resets:
            lines.append(f"ℹ️ 未检测到复位信号")
            return "\n".join(lines)

        lines.append(f"| 复位信号 | 类型 | 极性 | 关联时钟 |")
        lines.append(f"|----------|------|------|----------|")
        for r in result.async_resets:
            clock = r.domain_of_reset or "—"
            lines.append(f"| `{r.signal}` | {r.type} | {r.polarity} | {clock} |")
        for r in result.sync_resets:
            clock = r.domain_of_reset or "—"
            lines.append(f"| `{r.signal}` | {r.type} | {r.polarity} | {clock} |")
        lines.append(f"")

        async_count = len(result.async_resets)
        sync_count = len(result.sync_resets)
        lines.append(f"- **异步复位**: {async_count} 个")
        lines.append(f"- **同步复位**: {sync_count} 个")

        return "\n".join(lines)

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

        lines = [
            f"# Always 块分类: {module_name}",
            f"",
            f"| 序号 | 类型 | 敏感列表 | 赋值信号 |",
            f"|------|------|----------|----------|",
        ]

        all_blocks = []
        for b in result.sequential_blocks:
            all_blocks.append(("sequential", b))
        for b in result.combinational_blocks:
            all_blocks.append(("combinational", b))
        for b in result.latch_blocks:
            all_blocks.append(("latch", b))

        for i, (btype, b) in enumerate(all_blocks):
            type_label = {"sequential": "🔵 时序", "combinational": "🟢 组合", "latch": "🟡 锁存器"}.get(btype, btype)
            sigs = ", ".join(b.signals_assigned) if b.signals_assigned else "—"
            lines.append(f"| {i+1} | {type_label} | `{b.sensitivity}` | {sigs} |")

        lines.append(f"")
        lines.append(f"- **时序块**: {len(result.sequential_blocks)} 个")
        lines.append(f"- **组合块**: {len(result.combinational_blocks)} 个")
        lines.append(f"- **锁存器**: {len(result.latch_blocks)} 个")

        return "\n".join(lines)

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
                lines.append(f"**发现 {len(cross_signals)} 个跨时钟域信号** ⚠️")
                lines.append(f"")
                lines.append(f"| 信号 | 所属时钟域 |")
                lines.append(f"|------|-----------|")
                for sig, ds in sorted(cross_signals.items()):
                    lines.append(f"| `{sig}` | {', '.join(ds)} |")
                lines.append(f"")
                lines.append(f"> ⚠️ 跨时钟域信号需要同步器（如 double flop）处理")
            else:
                lines.append(f"✅ 未检测到跨时钟域信号")
        except DomainError as e:
            return f"❌ {e}"

        return "\n".join(lines)

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
                return clock_tree_builder.format_mermaid(result)
            else:
                return clock_tree_builder.format_text_tree(result)

        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_port_dataflow(module_name: str, port_name: str) -> str:
        """追踪模块端口信号的驱动源或负载

        Args:
            module_name: 模块名称
            port_name: 端口名称
        """
        tracer = DataflowTracer(index_store)
        try:
            result = tracer.trace_port_to_internal(module_name, port_name)
            if result is None:
                trace = tracer.trace_signal(port_name, module_name, "fan_in", max_depth=5)
                if trace and trace.nodes_count > 0:
                    lines = [
                        f"# 端口数据流: {module_name}.{port_name}",
                        f"",
                        f"**Fan-in 追踪** — 回溯到 {trace.nodes_count} 个节点:",
                        f"",
                    ]
                    result = trace
                else:
                    lines = [
                        f"# 端口数据流: {module_name}.{port_name}",
                        f"",
                        f"ℹ️ 未追踪到数据流路径",
                    ]
                return "\n".join(lines) + "\n\n> 💡 端口数据流穿透的详细功能需要完整的跨层级追踪支持，当前使用 fan-in 模式"
        except DomainError as e:
            return f"❌ {e}"

        return "\n".join(lines) if isinstance(lines, list) else str(lines)
