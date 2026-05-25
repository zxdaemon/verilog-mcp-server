"""
Phase 2 — 跨模块引用解析引擎 (Cross Reference Engine)

提供跨模块的引用查找功能：
- where_used_module: 查找所有例化指定模块的地方
- where_used_signal: 查找所有引用指定信号的位置
- instance_connections: 获取指定实例路径的端口连接详情
- resolve_port_path: 将端口信号穿透到驱动/负载端
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from database.index_store import IndexStore
from database.models import ModuleDef, InstanceDef, PortDef, SignalDef


@dataclass
class UsageInfo:
    """引用位置信息"""
    usage_type: str               # module_instantiation / port_declaration / signal_declaration
                                  # assign_lhs / assign_rhs / always_block / instance_connection
    module_name: str              # 所在模块名
    file_path: str = ""
    line: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "usage_type": self.usage_type,
            "module_name": self.module_name,
            "file_path": self.file_path,
            "line": self.line,
            "description": self.description,
        }


@dataclass
class ConnectionDetail:
    """端口连接详情"""
    formal_port: str              # 形式端口名
    direction: str                # input / output / inout
    actual_signal: str            # 实际连接信号
    width: Optional[str] = None   # 端口宽度
    description: str = ""         # 连接描述

    def to_dict(self) -> dict:
        return {
            "formal_port": self.formal_port,
            "direction": self.direction,
            "actual_signal": self.actual_signal,
            "width": self.width,
            "description": self.description,
        }


@dataclass
class PortTraceResult:
    """端口穿透追踪结果"""
    original_port: str
    start_module: str
    resolved_signals: list[ResolvedSignal] = field(default_factory=list)
    path_description: str = ""


@dataclass
class ResolvedSignal:
    """穿透解析后的信号"""
    signal_name: str
    module_name: str
    instance_path: str
    role: str                     # driver / load / intermediate
    file_path: str = ""
    line: int = 0


class CrossReference:
    """跨模块引用解析器"""

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store

    # ── where_used_module ──

    def where_used_module(self, module_name: str) -> list[UsageInfo]:
        """
        查找所有例化指定模块的位置

        即搜索所有模块的 instances 列表，找到 module_type == module_name 的条目

        Args:
            module_name: 目标模块名

        Returns:
            list[UsageInfo]: 使用位置列表
        """
        results: list[UsageInfo] = []
        target_lower = module_name.lower()

        for mod in self._index_store.get_all_modules():
            for inst in mod.instances:
                if inst.module_type.lower() == target_lower:
                    port_count = len(inst.port_connections)
                    param_overrides = ""
                    if inst.param_overrides:
                        params = ", ".join(f"{k}={v}" for k, v in inst.param_overrides.items())
                        param_overrides = f" (#{params})"
                    results.append(UsageInfo(
                        usage_type="module_instantiation",
                        module_name=mod.name,
                        file_path=inst.file_path or mod.file_path,
                        line=inst.line,
                        description=(
                            f"例化 {inst.instance_name} → {inst.module_type}"
                            f"{param_overrides}, {port_count} 个端口连接"
                        ),
                    ))

        return results

    # ── where_used_signal ──

    def where_used_signal(self, signal_name: str) -> list[UsageInfo]:
        """
        查找所有引用指定信号的位置

        搜索范围包括：
        - 端口定义
        - 信号定义
        - assign 语句的 LHS/RHS
        - always 块中的引用
        - 例化端口连接中的实际信号

        Args:
            signal_name: 目标信号名

        Returns:
            list[UsageInfo]: 使用位置列表
        """
        results: list[UsageInfo] = []
        target_lower = signal_name.lower()

        for mod in self._index_store.get_all_modules():
            # 1. 端口定义
            for port in mod.ports:
                if port.name.lower() == target_lower:
                    results.append(UsageInfo(
                        usage_type="port_declaration",
                        module_name=mod.name,
                        file_path=mod.file_path,
                        description=(
                            f"{port.direction} {port.var_type}"
                            f"{f' {port.width_range}' if port.width_range else ''} {port.name}"
                        ),
                    ))

            # 2. 信号定义
            for sig in mod.signals:
                if sig.name.lower() == target_lower:
                    results.append(UsageInfo(
                        usage_type="signal_declaration",
                        module_name=mod.name,
                        file_path=mod.file_path,
                        description=(
                            f"{sig.var_type}"
                            f"{f' {sig.width_range}' if sig.width_range else ''} {sig.name}"
                        ),
                    ))

            # 3. assign 语句
            for assign in mod.assignments:
                if target_lower in assign.lhs.lower():
                    results.append(UsageInfo(
                        usage_type="assign_lhs",
                        module_name=mod.name,
                        file_path=assign.file_path or mod.file_path,
                        line=assign.line,
                        description=f"assign {assign.lhs} = {assign.rhs}",
                    ))
                if target_lower in assign.rhs.lower():
                    results.append(UsageInfo(
                        usage_type="assign_rhs",
                        module_name=mod.name,
                        file_path=assign.file_path or mod.file_path,
                        line=assign.line,
                        description=f"assign {assign.lhs} = {assign.rhs} (RHS)",
                    ))

            # 4. always 块
            for always in mod.always_blocks:
                if target_lower in always.sensitivity_list.lower():
                    results.append(UsageInfo(
                        usage_type="always_block",
                        module_name=mod.name,
                        file_path=mod.file_path,
                        description=(
                            f"always @({always.sensitivity_list}) 中的敏感列表"
                        ),
                    ))
                for stmt in always.statements:
                    if target_lower in stmt.lower():
                        results.append(UsageInfo(
                            usage_type="always_block",
                            module_name=mod.name,
                            file_path=mod.file_path,
                            description=f"always 块语句: {stmt.strip()}",
                        ))

            # 5. 例化端口连接
            for inst in mod.instances:
                for formal_port, actual_signal in inst.port_connections.items():
                    if target_lower == actual_signal.lower():
                        child_mod = self._index_store.get_module(inst.module_type)
                        port_dir = ""
                        if child_mod:
                            for p in child_mod.ports:
                                if p.name == formal_port:
                                    port_dir = p.direction
                                    break
                        results.append(UsageInfo(
                            usage_type="instance_connection",
                            module_name=mod.name,
                            file_path=inst.file_path or mod.file_path,
                            line=inst.line,
                            description=(
                                f"例化 {inst.instance_name} ({inst.module_type}) "
                                f"的端口 .{formal_port}({actual_signal}) [{port_dir}]"
                            ),
                        ))

        return results

    # ── instance_connections ──

    def instance_connections(
        self,
        instance_name: str,
        module_name: str,
    ) -> list[ConnectionDetail]:
        """
        获取指定模块中某例化的端口连接详情

        会解析每个形式端口的方向和宽度，匹配实际连接信号

        Args:
            instance_name: 例化名
            module_name: 所在模块名

        Returns:
            list[ConnectionDetail]: 端口连接详情列表
        """
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在")

        target_inst: Optional[InstanceDef] = None
        for inst in mod.instances:
            if inst.instance_name == instance_name:
                target_inst = inst
                break

        if not target_inst:
            raise ValueError(f"在模块 '{module_name}' 中未找到例化 '{instance_name}'")

        # 获取被例化模块的端口定义
        child_mod = self._index_store.get_module(target_inst.module_type)

        results: list[ConnectionDetail] = []
        for formal_port, actual_signal in target_inst.port_connections.items():
            width = None
            direction = ""
            if child_mod:
                for p in child_mod.ports:
                    if p.name == formal_port:
                        width = p.width_range
                        direction = p.direction
                        break

            results.append(ConnectionDetail(
                formal_port=formal_port,
                direction=direction or "unknown",
                actual_signal=actual_signal,
                width=width,
                description=f".{formal_port}({actual_signal})",
            ))

        return results

    # ── resolve_port_path ──

    def resolve_port_path(
        self,
        port_name: str,
        start_module: str,
        direction: str = "fan_in",
        max_depth: int = 10,
    ) -> PortTraceResult:
        """
        端口穿透：将模块的端口信号穿透到驱动端或负载端

        例如，对于模块 A 的 output 端口 data_out：
        - fan_in: 追踪到 A 内部驱动 data_out 的信号源
        - fan_out: 追踪到顶层模块中 data_out 最终连接的负载

        Args:
            port_name: 端口名
            start_module: 起始模块名
            direction: "fan_in" 或 "fan_out"
            max_depth: 最大穿透深度

        Returns:
            PortTraceResult: 解析结果
        """
        mod = self._index_store.get_module(start_module)
        if not mod:
            raise ValueError(f"模块 '{start_module}' 不存在")

        port: Optional[PortDef] = None
        for p in mod.ports:
            if p.name == port_name:
                port = p
                break

        if not port:
            raise ValueError(f"模块 '{start_module}' 中没有端口 '{port_name}'")

        result = PortTraceResult(
            original_port=port_name,
            start_module=start_module,
        )

        visited: set[tuple[str, str]] = set()

        if direction == "fan_in":
            if port.direction == "output" or port.direction == "inout":
                result.path_description = (
                    f"从模块 {start_module} 的 output 端口 {port_name} "
                    f"向内追踪内部驱动源"
                )
                self._resolve_port_fan_in(result, port_name, start_module, start_module, 0, max_depth, visited)
            elif port.direction == "input":
                result.path_description = (
                    f"从模块 {start_module} 的 input 端口 {port_name} "
                    f"向上追踪到父模块的驱动源"
                )
                self._resolve_port_upward(result, port_name, start_module, start_module, 0, max_depth, visited)
        else:  # fan_out
            if port.direction == "input" or port.direction == "inout":
                result.path_description = (
                    f"从模块 {start_module} 的 input 端口 {port_name} "
                    f"向内追踪内部负载"
                )
                self._resolve_port_fan_out(result, port_name, start_module, start_module, 0, max_depth, visited)
            elif port.direction == "output":
                result.path_description = (
                    f"从模块 {start_module} 的 output 端口 {port_name} "
                    f"向上追踪到父模块中的后续负载"
                )
                self._resolve_port_upward_fan_out(result, port_name, start_module, start_module, 0, max_depth, visited)

        return result

    def _resolve_port_fan_in(
        self,
        result: PortTraceResult,
        signal_name: str,
        module_name: str,
        instance_path: str,
        depth: int,
        max_depth: int,
        visited: set[tuple[str, str]],
    ):
        """output 端口 fan-in：在模块内部查找驱动源"""
        if depth > max_depth:
            return

        visit_key = (module_name, signal_name)
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod = self._index_store.get_module(module_name)
        if not mod:
            return

        sig = None
        for s in mod.signals:
            if s.name == signal_name:
                sig = s
                break

        if sig and sig.drivers:
            for drv in sig.drivers:
                resolved = ResolvedSignal(
                    signal_name=signal_name,
                    module_name=module_name,
                    instance_path=instance_path,
                    role=f"driver_{drv.type}",
                    file_path=drv.file_path or mod.file_path,
                    line=drv.line,
                )
                result.resolved_signals.append(resolved)

    def _resolve_port_upward(
        self,
        result: PortTraceResult,
        port_name: str,
        module_name: str,
        instance_path: str,
        depth: int,
        max_depth: int,
        visited: set[tuple[str, str]],
    ):
        """input 端口 fan-in：向上查找父模块中的驱动"""
        if depth > max_depth:
            return

        visit_key = (module_name, port_name)
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod_name_lower = module_name.lower()
        for parent_mod in self._index_store.get_all_modules():
            for inst in parent_mod.instances:
                if inst.module_type.lower() == mod_name_lower:
                    actual_signal = inst.port_connections.get(port_name)
                    if actual_signal:
                        resolved = ResolvedSignal(
                            signal_name=actual_signal,
                            module_name=parent_mod.name,
                            instance_path=parent_mod.name,
                            role="upward_driver",
                            file_path=inst.file_path or parent_mod.file_path,
                            line=inst.line,
                        )
                        result.resolved_signals.append(resolved)

                        # 继续往上追
                        self._resolve_port_upward(
                            result, actual_signal, parent_mod.name,
                            parent_mod.name, depth + 1, max_depth, visited,
                        )

    def _resolve_port_fan_out(
        self,
        result: PortTraceResult,
        signal_name: str,
        module_name: str,
        instance_path: str,
        depth: int,
        max_depth: int,
        visited: set[tuple[str, str]],
    ):
        """input 端口 fan-out：在模块内部查找负载"""
        if depth > max_depth:
            return

        visit_key = (module_name, signal_name)
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod = self._index_store.get_module(module_name)
        if not mod:
            return

        sig = None
        for s in mod.signals:
            if s.name == signal_name:
                sig = s
                break

        if sig and sig.loads:
            for load in sig.loads:
                resolved = ResolvedSignal(
                    signal_name=signal_name,
                    module_name=module_name,
                    instance_path=instance_path,
                    role=f"load_{load.type}",
                    file_path=load.file_path or mod.file_path,
                    line=load.line,
                )
                result.resolved_signals.append(resolved)

    def _resolve_port_upward_fan_out(
        self,
        result: PortTraceResult,
        port_name: str,
        module_name: str,
        instance_path: str,
        depth: int,
        max_depth: int,
        visited: set[tuple[str, str]],
    ):
        """output 端口 fan-out：向上查找父模块中的负载"""
        if depth > max_depth:
            return

        visit_key = (module_name, port_name)
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod_name_lower = module_name.lower()
        for parent_mod in self._index_store.get_all_modules():
            for inst in parent_mod.instances:
                if inst.module_type.lower() == mod_name_lower:
                    actual_signal = inst.port_connections.get(port_name)
                    if actual_signal:
                        resolved = ResolvedSignal(
                            signal_name=actual_signal,
                            module_name=parent_mod.name,
                            instance_path=parent_mod.name,
                            role="upward_load",
                            file_path=inst.file_path or parent_mod.file_path,
                            line=inst.line,
                        )
                        result.resolved_signals.append(resolved)

                        # 继续往上追
                        self._resolve_port_upward_fan_out(
                            result, actual_signal, parent_mod.name,
                            parent_mod.name, depth + 1, max_depth, visited,
                        )

    # ── 格式化输出 ──

    @staticmethod
    def format_usage_results(results: list[UsageInfo], title: str = "引用位置") -> str:
        """格式化引用位置结果"""
        if not results:
            return "未找到任何引用"

        lines: list[str] = []
        lines.append(f"📌 {title}: 共 {len(results)} 处引用")
        lines.append("")

        for i, usage in enumerate(results, 1):
            lines.append(f"  {i}. [{usage.usage_type}]")
            lines.append(f"     模块: {usage.module_name}")
            if usage.file_path:
                lines.append(f"     文件: {usage.file_path}" + (f" 行 {usage.line}" if usage.line else ""))
            if usage.description:
                lines.append(f"     详情: {usage.description}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_connection_details(details: list[ConnectionDetail], title: str = "端口连接详情") -> str:
        """格式化端口连接详情"""
        if not details:
            return "无端口连接"

        lines: list[str] = []
        lines.append(f"🔌 {title}: {len(details)} 个端口")
        lines.append("")

        for detail in details:
            width_info = f" {detail.width}" if detail.width else ""
            lines.append(f"  .{detail.formal_port:<20}({detail.actual_signal})  [{detail.direction}{width_info}]")

        return "\n".join(lines)

    @staticmethod
    def format_port_trace(result: PortTraceResult) -> str:
        """格式化端口穿透结果"""
        lines: list[str] = []
        lines.append(f"🔍 端口穿透: {result.original_port} @ {result.start_module}")
        lines.append(f"   {result.path_description}")
        lines.append("")

        if not result.resolved_signals:
            lines.append("  未找到解析信号")
        else:
            for sig in result.resolved_signals:
                loc = f"  [{sig.file_path}:{sig.line}]" if sig.line else ""
                lines.append(f"  [{sig.role}] {sig.signal_name} @ {sig.module_name} ({sig.instance_path}){loc}")

        return "\n".join(lines)
