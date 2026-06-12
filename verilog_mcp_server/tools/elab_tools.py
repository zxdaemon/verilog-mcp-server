"""
Elaboration 相关 MCP Tools

提供 pyslang elaboration 结果的查询和报告功能
"""

from __future__ import annotations

from ..database.index_store import IndexStore
from ..database.errors import DomainError


def register_tools(mcp, index_store: IndexStore):
    """注册 elaboration 相关 tools"""

    @mcp.tool()
    def rtl_elab_report() -> str:
        """
        获取 pyslang elaboration 报告

        显示 elaboration 摘要：顶层模块、generate 展开实例数、
        参数求值后的信号数、tree-sitter 与 pyslang 模块数量差异、
        诊断信息（错误/警告）等。

        Returns:
            elaboration 摘要报告
        """
        report = index_store.get_elab_report()
        if not report:
            return "暂无 pyslang elaboration 数据。请先运行 rtl_build_index 或 rtl_update_index 构建索引。"

        lines = ["📊 **pyslang Elaboration 报告**\n"]

        # 顶层模块
        if report.top_modules:
            lines.append(f"**顶层模块**: {', '.join(report.top_modules)}")

        # 实例统计
        lines.append(f"\n**实例统计**:")
        lines.append(f"  总实例数: {report.total_instances}")
        lines.append(f"  ├─ generate 展开: {report.generated_instances}")
        lines.append(f"  └─ 非 generate: {report.non_generated_instances}")
        lines.append(f"  唯一模块类型: {report.unique_module_types}")

        # 信号统计
        lines.append(f"\n**信号统计**:")
        lines.append(f"  Resolved 信号: {report.resolved_signals}")

        # 模块数量对比
        lines.append(f"\n**模块数量对比**:")
        lines.append(f"  tree-sitter 解析: {report.tree_sitter_module_count}")
        lines.append(f"  pyslang elaboration: {report.pyslang_module_count}")
        diff = report.pyslang_module_count - report.tree_sitter_module_count
        if diff > 0:
            lines.append(f"  差异: +{diff} (generate 展开导致)")
        elif diff < 0:
            lines.append(f"  差异: {diff}")
        else:
            lines.append(f"  差异: 0 (一致)")

        # 诊断信息
        lines.append(f"\n**诊断信息**:")
        lines.append(f"  错误: {report.error_count}")
        lines.append(f"  警告: {report.warning_count}")

        if report.diagnostics:
            lines.append(f"\n**详细诊断**:")
            for d in report.diagnostics[:20]:
                severity = d.get("severity", "unknown")
                loc = d.get("location", "")
                msg = d.get("message", "")
                icon = "🔴" if d.get("is_error") else "⚠️"
                lines.append(f"  {icon} [{severity}] {loc} {msg}")
            if len(report.diagnostics) > 20:
                lines.append(f"  ... 还有 {len(report.diagnostics) - 20} 条诊断")

        # 层次概览
        if report.hierarchy:
            lines.append(f"\n**层次概览**:")
            for mod, children in list(report.hierarchy.items())[:10]:
                lines.append(f"  {mod} → {', '.join(children[:5])}")
                if len(children) > 5:
                    lines.append(f"    ... 还有 {len(children) - 5} 个子模块")
            if len(report.hierarchy) > 10:
                lines.append(f"  ... 还有 {len(report.hierarchy) - 10} 个模块")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_elab_instances(module_name: str | None = None) -> str:
        """
        获取 pyslang elaboration 后的实例列表

        Args:
            module_name: 可选，限定模块类型。为 None 时返回所有实例。

        Returns:
            elaborated 实例列表（含层次路径和 generate 信息）
        """
        instances = index_store.get_elab_instances(module_name)
        if not instances:
            scope = f"模块 '{module_name}'" if module_name else "全部"
            return f"未找到 {scope} 的 elaborated 实例数据"

        lines = [f"找到 {len(instances)} 个 elaborated 实例:\n"]
        for inst in instances:
            gen_marker = " [generate]" if inst.is_generated else ""
            lines.append(f"### {inst.hierarchical_path}{gen_marker}")
            lines.append(f"  实例名: {inst.instance_name}")
            lines.append(f"  模块类型: {inst.module_type}")
            if inst.parent_module:
                lines.append(f"  父模块: {inst.parent_module}")
            if inst.generate_condition:
                lines.append(f"  generate 条件: {inst.generate_condition}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_resolved_signals(module_name: str) -> str:
        """
        获取模块的参数求值后信号列表

        Args:
            module_name: 模块名

        Returns:
            信号列表（含原始位宽和 resolved 位宽对比）
        """
        signals = index_store.get_resolved_signals(module_name)
        if not signals:
            return f"未找到模块 '{module_name}' 的 resolved 信号数据"

        lines = [f"模块 '{module_name}' 的 resolved 信号 ({len(signals)}):\n"]
        for sig in signals:
            orig = sig.original_width or "(未指定)"
            resolved = sig.resolved_width or "(未知)"
            signed = " signed" if sig.is_signed else ""
            lines.append(
                f"  {sig.name:<20} {sig.var_type}{signed:<8} "
                f"原始: {orig:<12} → resolved: {resolved} ({sig.resolved_bit_width} bit)"
            )

        return "\n".join(lines)
