"""
Yosys 相关 MCP Tools

提供 Yosys 综合分析结果的查询功能。
所有工具查询 build 阶段预计算的数据，不触发实时综合。
"""

from __future__ import annotations

from ..database.index_store import IndexStore


# Yosys 未启用的提示信息
_YOSYS_NOT_ENABLED_MSG = (
    "⚠️ Yosys 分析未启用。\n"
    "请在启动时使用 `--yosys --top <dut_top_module>` 重新 build 索引。\n"
    "例如：verilog-mcp-server --build --yosys --top soc_top -p /path/to/rtl"
)

_YOSYS_NOT_AVAILABLE_MSG = (
    "⚠️ Yosys 未安装或不可用。\n"
    "请安装 Yosys 后重新 build：https://github.com/YosysHQ/yosys"
)


def register_tools(mcp, index_store: IndexStore):
    """注册 Yosys 相关 tools"""

    @mcp.tool()
    def rtl_yosys_fsm(module_name: str = None) -> str:
        """
        查询 Yosys 检测到的 FSM 状态机列表（需 build 时启用 --yosys）

        返回综合网表中检测到的 FSM，包含状态数、编码方式（one-hot/binary/gray）。

        Args:
            module_name: 可选，指定模块名过滤。不指定则返回全部。

        Returns:
            FSM 列表报告
        """
        fsms = index_store.get_yosys_fsms(module_name)
        if not fsms:
            return _check_yosys_available(index_store)

        lines = [f"🔍 **Yosys FSM 检测结果** (source: yosys)\n"]
        lines.append(f"共检测到 {len(fsms)} 个 FSM：\n")

        for fsm in fsms:
            lines.append(f"### {fsm.fsm_name}")
            lines.append(f"- 模块: `{fsm.module_name}`")
            lines.append(f"- 状态数: {fsm.state_count}")
            lines.append(f"- 编码: {fsm.encoding}")
            if fsm.source_file:
                lines.append(f"- 源文件: {fsm.source_file}")
            if fsm.transitions:
                lines.append(f"- 跳转数: {len(fsm.transitions)}")
                for t in fsm.transitions[:5]:  # 最多显示 5 条跳转
                    cond = t.get("condition", "")
                    lines.append(
                        f"  - `{t.get('from', '?')}` → `{t.get('to', '?')}`"
                        + (f" ({cond})" if cond and cond != "N/A" else "")
                    )
                if len(fsm.transitions) > 5:
                    lines.append(f"  ...({len(fsm.transitions) - 5} more)")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_yosys_comb_loops() -> str:
        """
        查询 Yosys 检测到的组合逻辑环（需 build 时启用 --yosys）

        Returns:
            组合逻辑环列表报告
        """
        loops = index_store.get_yosys_comb_loops()
        if not loops:
            return _check_yosys_available(index_store)

        lines = [f"⚠️ **Yosys 组合逻辑环检测结果** (source: yosys)\n"]
        lines.append(f"共检测到 {len(loops)} 个组合逻辑环：\n")

        for i, loop in enumerate(loops, 1):
            lines.append(f"### 环 {i}（{loop.severity}）")
            lines.append(f"- 涉及信号: {', '.join(loop.loop_signals)}")
            if loop.source_files:
                lines.append(f"- 涉及文件: {', '.join(loop.source_files)}")
            if loop.message:
                lines.append(f"- 详情: {loop.message[:200]}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_yosys_gated_clocks(module_name: str = None) -> str:
        """
        查询 Yosys 检测到的门控时钟信号（需 build 时启用 --yosys）

        返回门控时钟列表，标注门控类型（latch-based/and-gate）和使能信号。

        Args:
            module_name: 可选，指定模块名过滤。不指定则返回全部。

        Returns:
            门控时钟列表报告
        """
        clocks = index_store.get_yosys_gated_clocks(module_name)
        if not clocks:
            return _check_yosys_available(index_store)

        lines = [f"🕐 **Yosys 门控时钟检测结果** (source: yosys)\n"]
        lines.append(f"共检测到 {len(clocks)} 个门控时钟：\n")

        for clock in clocks:
            lines.append(f"### {clock.gated_clock_name}")
            lines.append(f"- 模块: `{clock.module_name}`")
            lines.append(f"- 源时钟: `{clock.source_clock}`")
            lines.append(f"- 使能信号: `{clock.enable_signal}`")
            lines.append(f"- 门控类型: {clock.type}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_yosys_stat(module_name: str = None) -> str:
        """
        查询 Yosys 资源统计（需 build 时启用 --yosys）

        返回工艺无关的通用单元计数（LUT/FF/Memory/DSP 估算）。

        Args:
            module_name: 可选，指定模块名过滤。不指定则返回全部。

        Returns:
            资源统计报告
        """
        stats = index_store.get_yosys_stats(module_name)
        if not stats:
            return _check_yosys_available(index_store)

        lines = [f"📊 **Yosys 资源统计** (source: yosys)\n"]

        for stat in stats:
            total = stat.num_lut + stat.num_ff + stat.num_memory + stat.num_dsp
            lines.append(f"### {stat.module_name}")
            lines.append(f"- 总单元数: {stat.num_cells}")
            lines.append(f"- 线网数: {stat.num_wires}")
            lines.append(f"- LUT: {stat.num_lut}")
            lines.append(f"- FF: {stat.num_ff}")
            lines.append(f"- Memory: {stat.num_memory}")
            lines.append(f"- DSP: {stat.num_dsp}")
            if total > 0:
                lines.append(f"- 资源总计: {total}")
            lines.append("")

        return "\n".join(lines)


def _check_yosys_available(index_store: IndexStore) -> str:
    """检查 Yosys 数据是否可用，返回友好提示"""
    # 检查是否有任何 Yosys 数据
    if index_store.get_elab_report() is not None:
        # 有 elaboration 数据说明 build 过，但可能没启用 --yosys
        return _YOSYS_NOT_ENABLED_MSG
    return _YOSYS_NOT_AVAILABLE_MSG
