"""
Level 2 — 关联分析 MCP Tools

基于 analysis/ 层的引擎，提供模块间关联分析能力：
- 信号扇入/扇出追踪
- 跨模块引用查找
- 例化端口连接详情
- 增强层次树（含路径追踪）
"""

from __future__ import annotations
from typing import Optional

from ..database.index_store import IndexStore
from ..database.errors import DomainError, AnalysisError
from ..analysis.hierarchy import HierarchyBuilder
from ..analysis.dataflow import DataflowTracer
from ..analysis.cross_ref import CrossReference


def _do_trace_signal(index_store: IndexStore, signal_name: str, start_module: str,
                     direction: str, max_depth: int):
    """信号追踪，调用 DataflowTracer"""
    tracer = DataflowTracer(index_store)
    return tracer.trace_signal(
        signal_name=signal_name, start_module=start_module,
        direction=direction, max_depth=max_depth,
    )


def _do_where_used(index_store: IndexStore, target: str, target_type: str):
    """查找模块/信号的使用处"""
    cr = CrossReference(index_store)
    if target_type == "module":
        return cr.where_used_module(target)
    elif target_type == "signal":
        return cr.where_used_signal(target)
    else:
        raise AnalysisError(f"无效的目标类型: '{target_type}'，应为 'module' 或 'signal'")


def _do_instance_connections(index_store: IndexStore, instance_name: str, module_name: str):
    """获取例化端口连接详情"""
    cr = CrossReference(index_store)
    return cr.instance_connections(instance_name, module_name)


def _do_hierarchy_tree(index_store: IndexStore, top_module: str, max_depth: int) -> str:
    """构建增强层次树"""
    hb = HierarchyBuilder(index_store)
    return hb.format_tree_text(top_module=top_module, max_depth=max_depth, show_ports=True)


def _do_hierarchy_instances(index_store: IndexStore, top_module: str, max_depth: int):
    """获取层次树中的扁平例化列表"""
    hb = HierarchyBuilder(index_store)
    return hb.get_all_instances(top_module=top_module, max_depth=max_depth)


def register_tools(mcp, index_store: IndexStore):
    """注册所有 Level 2 关联分析 tools"""

    hierarchy_builder = HierarchyBuilder(index_store)
    dataflow_tracer = DataflowTracer(index_store)
    cross_ref = CrossReference(index_store)

    @mcp.tool()
    def rtl_trace_signal(
        signal_name: str,
        start_module: str,
        direction: str = "fan_in",
        max_depth: int = 10,
    ) -> str:
        """
        信号跨模块追踪 — 沿驱动/负载链追溯

        追踪信号在模块层次中的完整数据流路径。
        Fan-in 从信号回溯到最终驱动源；Fan-out 从信号追踪到所有负载。

        Args:
            signal_name: 信号名
            start_module: 起始模块名
            direction: 追踪方向，"fan_in"（向上游追溯驱动源，默认）或 "fan_out"（向下游追溯负载）
            max_depth: 最大追踪深度（默认 10）

        Returns:
            数据流路径树（文本格式）
        """
        try:
            result = dataflow_tracer.trace_signal(
                signal_name=signal_name,
                start_module=start_module,
                direction=direction,
                max_depth=max_depth,
            )
            title = f"信号追踪: {signal_name} @ {start_module} ({'Fan-In' if direction == 'fan_in' else 'Fan-Out'})"
            return DataflowTracer.format_trace_result(result, title=title)
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_signal_fan_in(signal_name: str, module_name: str) -> str:
        """
        信号扇入分析 — 找出所有驱动源

        列出指定模块中某信号的所有驱动源（assign LHS、always 块赋值、端口连接等）

        Args:
            signal_name: 信号名
            module_name: 模块名

        Returns:
            驱动源列表
        """
        try:
            result = dataflow_tracer.trace_signal(
                signal_name=signal_name,
                start_module=module_name,
                direction="fan_in",
                max_depth=5,
            )
            title = f"扇入分析: {signal_name} @ {module_name}"
            return DataflowTracer.format_trace_result(result, title=title)
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_signal_fan_out(signal_name: str, module_name: str) -> str:
        """
        信号扇出分析 — 找出所有负载

        列出指定模块中某信号的所有负载（assign RHS、always 敏感列表、端口连接等）

        Args:
            signal_name: 信号名
            module_name: 模块名

        Returns:
            负载列表
        """
        try:
            result = dataflow_tracer.trace_signal(
                signal_name=signal_name,
                start_module=module_name,
                direction="fan_out",
                max_depth=5,
            )
            title = f"扇出分析: {signal_name} @ {module_name}"
            return DataflowTracer.format_trace_result(result, title=title)
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_where_used(target: str, target_type: str = "module") -> str:
        """
        查找指定模块或信号的使用处

        对于模块：找出所有例化该模块的位置
        对于信号：找出所有引用该信号的位置（端口、信号定义、assign、always、例化连接）

        Args:
            target: 目标名称（模块名或信号名）
            target_type: "module"（模块，默认）或 "signal"（信号）

        Returns:
            使用位置列表
        """
        try:
            if target_type == "module":
                results = cross_ref.where_used_module(target)
                title = f"模块 '{target}' 的使用处"
                return CrossReference.format_usage_results(results, title=title)
            elif target_type == "signal":
                results = cross_ref.where_used_signal(target)
                title = f"信号 '{target}' 的使用处"
                return CrossReference.format_usage_results(results, title=title)
            else:
                return f"❌ 无效的目标类型: '{target_type}'，应为 'module' 或 'signal'"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_instance_connections(instance_name: str, module_name: str) -> str:
        """
        获取指定例化的端口连接详情

        列出例化的每个形式端口与实际信号的映射关系，含端口方向和宽度信息

        Args:
            instance_name: 例化名
            module_name: 所在模块名

        Returns:
            端口连接详情列表
        """
        try:
            details = cross_ref.instance_connections(instance_name, module_name)
            title = f"例化 '{instance_name}' 在模块 '{module_name}' 中的端口连接"
            return CrossReference.format_connection_details(details, title=title)
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_hierarchy_tree(top_module: str, max_depth: int = 10) -> str:
        """
        增强模块层次树（含例化路径追踪）

        递归展开模块例化层次结构，显示完整例化路径和端口信息。
        支持循环例化检测。

        Args:
            top_module: 顶层模块名
            max_depth: 最大展开深度（默认 10）

        Returns:
            树状层次结构
        """
        try:
            return hierarchy_builder.format_tree_text(
                top_module=top_module,
                max_depth=max_depth,
                show_ports=True,
            )
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"

    @mcp.tool()
    def rtl_hierarchy_instances(top_module: str, max_depth: int = 10) -> str:
        """
        获取层次树中所有例化的扁平列表

        返回指定顶层模块下所有例化实例的路径、类型等信息

        Args:
            top_module: 顶层模块名
            max_depth: 最大深度（默认 10）

        Returns:
            例化实例列表
        """
        try:
            instances = hierarchy_builder.get_all_instances(
                top_module=top_module, max_depth=max_depth,
            )
            if not instances:
                return f"在 '{top_module}' 下未找到例化"

            lines: list[str] = []
            lines.append(f"📋 例化列表 (顶层: {top_module})")
            lines.append(f"   共 {len(instances)} 个例化\n")
            for inst in instances:
                cycle_flag = " ⚠️" if inst["is_cycle_ref"] else ""
                lines.append(
                    f"  {inst['instance_path']:<50} → {inst['module_type']}"
                    f"{cycle_flag}"
                )
            return "\n".join(lines)
        except ValueError as e:
            return f"❌ 错误: {e}"
        except DomainError as e:
            return f"❌ {e}"
