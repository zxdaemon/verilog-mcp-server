"""
信号 Fan-in 追踪引擎 (上游回溯)

从信号回溯到最终驱动源。与 fan_out.py 组合提供完整的双向追踪。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..database.index_store import IndexStore
from ..database.models import ModuleDef, PortDef, SignalDef


@dataclass
class TraceNode:
    """追踪路径中的一个节点"""
    signal_name: str
    module_name: str
    instance_path: str                    # 当前层次路径
    role: str                             # port_input / port_output / instance_connection / assign_lhs / assign_rhs / always_lhs / always_sensitivity
    description: str = ""
    file_path: str = ""
    line: int = 0
    depth: int = 0
    children: list[TraceNode] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "signal_name": self.signal_name, "module_name": self.module_name,
            "instance_path": self.instance_path, "role": self.role,
            "description": self.description, "file_path": self.file_path,
            "line": self.line, "depth": self.depth,
            "children": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return f"TraceNode({self.signal_name}@{self.module_name}, {self.role})"


@dataclass
class TraceResult:
    """追踪结果"""
    root: TraceNode
    nodes_count: int = 0
    max_depth: int = 0
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "root": self.root.to_dict(), "nodes_count": self.nodes_count,
            "max_depth": self.max_depth, "truncated": self.truncated,
        }


def _count_nodes(node: TraceNode) -> int:
    total = 1
    for child in node.children:
        total += _count_nodes(child)
    return total


def _max_depth_of(node: TraceNode) -> int:
    if not node.children:
        return node.depth
    return max(_max_depth_of(c) for c in node.children)


class DataflowTracer:
    """信号数据流追踪器 — fan-in (上游回溯) 基础实现"""

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store

    def trace_signal(
        self, signal_name: str, start_module: str,
        direction: str = "fan_in", max_depth: int = 10,
    ) -> TraceResult:
        """追踪信号的驱动源链 (fan_in) 或负载链 (fan_out)"""
        mod = self._index_store.get_module(start_module)
        if not mod:
            raise ValueError(f"模块 '{start_module}' 不存在于索引中")

        visited: set[tuple[str, str, str]] = set()

        root = TraceNode(
            signal_name=signal_name, module_name=start_module,
            instance_path=start_module, role="start",
            description=f"追踪起点: {signal_name} 在模块 {start_module} 中",
            file_path=mod.file_path,
        )

        if direction == "fan_in":
            self._trace_fan_in(root, signal_name, start_module, start_module, 1, max_depth, visited)
        elif direction == "fan_out":
            visited_fanout: set[tuple[str, str, str]] = set()
            self._trace_fan_out(root, signal_name, start_module, start_module, 1, max_depth, visited_fanout)
        else:
            raise ValueError(f"无效的方向: '{direction}'，应为 'fan_in' 或 'fan_out'")

        total_nodes = _count_nodes(root)
        md = _max_depth_of(root)
        return TraceResult(root=root, nodes_count=total_nodes, max_depth=md,
                          truncated=md >= max_depth)

    def trace_port_to_internal(self, module_name: str, port_name: str) -> Optional[TraceResult]:
        """追踪端口信号的内部连接"""
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在")
        port = self._get_port(mod, port_name)
        if not port:
            return None
        direction = "fan_in" if port.direction == "output" else "fan_out"
        return self.trace_signal(port_name, module_name, direction)

    def trace_port_dataflow(
        self,
        module_name: str,
        port_name: str,
        direction: str = "both",
        max_depth: int = 5,
    ) -> TraceResult:
        """端口数据流跨层级穿透追踪

        Args:
            module_name: 模块名称
            port_name: 端口名称
            direction: "fan_in" — 向上追踪驱动源（input 端口）;
                       "fan_out" — 向上追踪负载（output 端口）;
                       "both" — 双向追踪
            max_depth: 最大穿透深度

        Returns:
            TraceResult: 追踪结果树
        """
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在")

        port = self._get_port(mod, port_name)
        if not port:
            raise ValueError(f"模块 '{module_name}' 中没有端口 '{port_name}'")

        root = TraceNode(
            signal_name=port_name,
            module_name=module_name,
            instance_path=module_name,
            role="port",
            description=f"{port.direction} 端口 {port_name} ({port.var_type}{f' {port.width_range}' if port.width_range else ''})",
            file_path=mod.file_path,
            depth=0,
        )

        visited: set[tuple[str, str, str]] = set()

        if direction in ("fan_in", "both"):
            if port.direction in ("input", "inout"):
                self._trace_port_fan_in_upward(
                    root, port_name, module_name, module_name,
                    1, max_depth, visited,
                )
            elif port.direction == "output":
                # For output: trace internal drivers first
                self._trace_fan_in(root, port_name, module_name, module_name, 1, max_depth, visited)

        if direction in ("fan_out", "both"):
            if port.direction in ("output", "inout"):
                self._trace_port_fan_out_upward(
                    root, port_name, module_name, module_name,
                    1, max_depth, visited,
                )
            elif port.direction == "input":
                # For input: trace internal loads
                self._trace_fan_out(root, port_name, module_name, module_name, 1, max_depth, visited)

        total_nodes = _count_nodes(root)
        md = _max_depth_of(root)
        return TraceResult(
            root=root, nodes_count=total_nodes, max_depth=md,
            truncated=md >= max_depth,
        )

    def _trace_port_fan_in_upward(
        self, parent, port_name, module_name, instance_path,
        depth, max_depth, visited,
    ):
        """input 端口向上追踪：穿过父模块例化，找到实际信号，再 trace fan_in"""
        if depth > max_depth:
            return
        visit_key = (module_name, port_name, "port_fan_in_up")
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod_name_lower = module_name.lower()
        found_parent = False

        for parent_mod in self._index_store.get_all_modules():
            for inst in parent_mod.instances:
                if inst.module_type.lower() != mod_name_lower:
                    continue
                actual_signal = inst.port_connections.get(port_name)
                if actual_signal is None:
                    # Try positional port mapping
                    child_mod = self._index_store.get_module(inst.module_type)
                    if child_mod:
                        port_idx = -1
                        for i, p in enumerate(child_mod.ports):
                            if p.name == port_name:
                                port_idx = i
                                break
                        if port_idx >= 0:
                            ports_list = list(inst.port_connections.items())
                            if port_idx < len(ports_list):
                                actual_signal = ports_list[port_idx][1]

                if actual_signal:
                    found_parent = True
                    child = TraceNode(
                        signal_name=actual_signal,
                        module_name=parent_mod.name,
                        instance_path=f"{parent_mod.name}.{inst.instance_name}",
                        role="port_input_up",
                        description=f"input 端口 {port_name} 在例化 {inst.instance_name} 中连接到 {actual_signal}",
                        file_path=inst.file_path or parent_mod.file_path,
                        line=inst.line,
                        depth=depth,
                    )
                    parent.children.append(child)
                    # Continue tracing the actual signal's fan_in in parent
                    self._trace_fan_in(child, actual_signal, parent_mod.name,
                                       parent_mod.name, depth + 1, max_depth, visited)

        if not found_parent:
            # No parent instantiation found — this is a top-level input
            child = TraceNode(
                signal_name=port_name,
                module_name=module_name,
                instance_path=instance_path,
                role="top_level_input",
                description=f"顶层 input 端口 {port_name}（无父模块例化）",
                depth=depth,
            )
            parent.children.append(child)

    def _trace_port_fan_out_upward(
        self, parent, port_name, module_name, instance_path,
        depth, max_depth, visited,
    ):
        """output 端口向上追踪：穿过父模块例化，找到实际信号，再 trace fan_out"""
        if depth > max_depth:
            return
        visit_key = (module_name, port_name, "port_fan_out_up")
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod_name_lower = module_name.lower()
        found_parent = False

        for parent_mod in self._index_store.get_all_modules():
            for inst in parent_mod.instances:
                if inst.module_type.lower() != mod_name_lower:
                    continue
                actual_signal = inst.port_connections.get(port_name)
                if actual_signal:
                    found_parent = True
                    child = TraceNode(
                        signal_name=actual_signal,
                        module_name=parent_mod.name,
                        instance_path=f"{parent_mod.name}.{inst.instance_name}",
                        role="port_output_up",
                        description=f"output 端口 {port_name} 在例化 {inst.instance_name} 中连接到 {actual_signal}",
                        file_path=inst.file_path or parent_mod.file_path,
                        line=inst.line,
                        depth=depth,
                    )
                    parent.children.append(child)
                    # Continue tracing the actual signal's fan_out in parent
                    self._trace_fan_out(child, actual_signal, parent_mod.name,
                                        parent_mod.name, depth + 1, max_depth, visited)

        if not found_parent:
            child = TraceNode(
                signal_name=port_name,
                module_name=module_name,
                instance_path=instance_path,
                role="top_level_output",
                description=f"顶层 output 端口 {port_name}（无父模块例化）",
                depth=depth,
            )
            parent.children.append(child)

    # ── Fan-in 追踪 ──

    def _trace_fan_in(self, parent, signal_name, module_name, instance_path, depth, max_depth, visited):
        if depth > max_depth:
            return
        visit_key = (module_name, signal_name, "fan_in")
        if visit_key in visited:
            return
        visited.add(visit_key)

        mod = self._index_store.get_module(module_name)
        if not mod:
            return

        is_port = self._is_port(mod, signal_name)
        is_signal = self._is_signal(mod, signal_name)

        if is_port:
            port = self._get_port(mod, signal_name)
            if port and port.direction == "input":
                self._trace_input_port_fan_in(parent, signal_name, module_name, instance_path, depth, max_depth, visited)
            elif port and port.direction == "output":
                self._trace_output_port_fan_in(parent, signal_name, module_name, instance_path, depth, max_depth, visited)
            elif port and port.direction == "inout":
                self._trace_input_port_fan_in(parent, signal_name, module_name, instance_path, depth, max_depth, visited)
                self._trace_output_port_fan_in(parent, signal_name, module_name, instance_path, depth, max_depth, visited)

        if is_signal or is_port:
            sig = self._get_signal(mod, signal_name)
            if sig and sig.drivers:
                for drv in sig.drivers:
                    if drv.type == "assign":
                        self._trace_assign_rhs(parent, signal_name, module_name, instance_path, mod, depth, max_depth, drv, visited)
                    elif drv.type == "always_block":
                        self._trace_always_rhs(parent, signal_name, module_name, instance_path, mod, depth, max_depth, drv, visited)
                    elif drv.type in ("port_connection", "instance_output"):
                        child = TraceNode(
                            signal_name=signal_name, module_name=module_name,
                            instance_path=instance_path, role=drv.type,
                            description=f"{'端口连接' if drv.type == 'port_connection' else '子模块输出'}驱动: {drv.source}",
                            file_path=drv.file_path or mod.file_path,
                            line=drv.line, depth=depth,
                        )
                        parent.children.append(child)

        self._trace_instance_port_fan_in(parent, signal_name, module_name, instance_path, depth, max_depth, visited)

    def _trace_input_port_fan_in(self, parent, signal_name, module_name, instance_path, depth, max_depth, visited):
        for parent_mod_name in self._index_store.find_instantiators(module_name):
            parent_mod = self._index_store.get_module(parent_mod_name)
            if not parent_mod:
                continue
            for inst in parent_mod.instances:
                if inst.module_type.lower() != module_name.lower():
                    continue
                actual_signal = inst.port_connections.get(signal_name)
                if actual_signal is None:
                    child_mod = self._index_store.get_module(inst.module_type)
                    if child_mod:
                        port_idx = -1
                        for i, p in enumerate(child_mod.ports):
                            if p.name == signal_name:
                                port_idx = i
                                break
                        if port_idx >= 0:
                            ports_list = list(inst.port_connections.items())
                            if port_idx < len(ports_list):
                                actual_signal = list(ports_list[port_idx])[1]

                if actual_signal is not None:
                    child = TraceNode(
                        signal_name=actual_signal, module_name=parent_mod.name,
                        instance_path=f"{parent_mod.name}.{inst.instance_name}" if parent_mod.name != instance_path else instance_path,
                        role="port_input_up",
                        description=f"input端口 {signal_name} 在例化 {inst.instance_name} 中连接到 {actual_signal}",
                        file_path=inst.file_path or parent_mod.file_path,
                        line=inst.line, depth=depth,
                    )
                    parent.children.append(child)
                    self._trace_fan_in(child, actual_signal, parent_mod.name, parent_mod.name, depth + 1, max_depth, visited)

    def _trace_output_port_fan_in(self, parent, signal_name, module_name, instance_path, depth, max_depth, visited):
        mod = self._index_store.get_module(module_name)
        if not mod:
            return
        sig = self._get_signal(mod, signal_name)
        if sig:
            for drv in sig.drivers:
                child = TraceNode(
                    signal_name=signal_name, module_name=module_name,
                    instance_path=instance_path, role=f"output_fan_in_{drv.type}",
                    description=f"内部驱动 ({drv.type}): {drv.source}",
                    file_path=drv.file_path or mod.file_path, line=drv.line, depth=depth,
                )
                parent.children.append(child)
                if drv.type == "assign":
                    self._trace_assign_rhs(child, signal_name, module_name, instance_path, mod, depth + 1, max_depth, drv, visited)

    def _trace_instance_port_fan_in(self, parent, signal_name, module_name, instance_path, depth, max_depth, visited):
        mod = self._index_store.get_module(module_name)
        if not mod:
            return
        for inst in mod.instances:
            for formal_port, actual_signal in inst.port_connections.items():
                if actual_signal == signal_name:
                    child_mod = self._index_store.get_module(inst.module_type)
                    if child_mod:
                        child_port = self._get_port(child_mod, formal_port)
                        if child_port and child_port.direction == "output":
                            child = TraceNode(
                                signal_name=formal_port, module_name=child_mod.name,
                                instance_path=f"{instance_path}.{inst.instance_name}",
                                role="instance_output_cross",
                                description=f"子模块 {inst.module_type}.{inst.instance_name} 的 output 端口 {formal_port} 连接到 {signal_name}",
                                file_path=inst.file_path or child_mod.file_path,
                                line=inst.line, depth=depth,
                            )
                            parent.children.append(child)
                            self._trace_fan_in(child, formal_port, child_mod.name,
                                             f"{instance_path}.{inst.instance_name}", depth + 1, max_depth, visited)

    # ── Fan-out 占位 (子类覆盖) ──

    def _trace_fan_out(self, parent, signal_name, module_name, instance_path, depth, max_depth, visited):
        """子类覆盖实现 fan-out 追踪"""
        pass

    # ── Assign / Always 辅助 ──

    def _trace_assign_rhs(self, parent, signal_name, module_name, instance_path, mod, depth, max_depth, drv, visited):
        for assign in mod.assignments:
            if assign.lhs == signal_name:
                rhs_signals = self._extract_signal_names(assign.rhs)
                for rhs_sig in rhs_signals:
                    child = TraceNode(
                        signal_name=rhs_sig, module_name=module_name,
                        instance_path=instance_path, role="assign_rhs",
                        description=f"assign {assign.lhs} = {assign.rhs} 中的驱动信号",
                        file_path=assign.file_path or mod.file_path,
                        line=assign.line, depth=depth,
                    )
                    parent.children.append(child)
                    self._trace_fan_in(child, rhs_sig, module_name, instance_path, depth + 1, max_depth, visited)
                break

    def _trace_always_rhs(self, parent, signal_name, module_name, instance_path, mod, depth, max_depth, drv, visited):
        for always in mod.always_blocks:
            for stmt in always.statements:
                if "=" in stmt or "<=" in stmt:
                    delim = "<=" if "<=" in stmt else "="
                    parts = stmt.split(delim, 1)
                    lhs = parts[0].strip()
                    if lhs == signal_name or lhs.endswith(f".{signal_name}"):
                        rhs = parts[1].strip().rstrip(";")
                        rhs_signals = self._extract_signal_names(rhs)
                        for rhs_sig in rhs_signals:
                            child = TraceNode(
                                signal_name=rhs_sig, module_name=module_name,
                                instance_path=instance_path, role="always_rhs",
                                description=f"always 块中 {signal_name} <= {rhs} 的驱动信号，敏感表: ({always.sensitivity_list})",
                                file_path=mod.file_path, depth=depth,
                            )
                            parent.children.append(child)
                            self._trace_fan_in(child, rhs_sig, module_name, instance_path, depth + 1, max_depth, visited)

    # ── 辅助方法 ──

    def _is_port(self, mod: ModuleDef, name: str) -> bool:
        return any(p.name == name for p in mod.ports)

    def _get_port(self, mod: ModuleDef, name: str) -> Optional[PortDef]:
        for p in mod.ports:
            if p.name == name:
                return p
        return None

    def _is_signal(self, mod: ModuleDef, name: str) -> bool:
        return any(s.name == name for s in mod.signals)

    def _get_signal(self, mod: ModuleDef, name: str) -> Optional[SignalDef]:
        for s in mod.signals:
            if s.name == name:
                return s
        return None

    @staticmethod
    def _extract_signal_names(expression: str) -> list[str]:
        from .expr_walker import extract_signal_refs
        return extract_signal_refs(expression)

    @staticmethod
    def format_trace_result(result: TraceResult, title: str = "信号追踪结果") -> str:
        lines: list[str] = [f"📡 {title}", ""]

        def _format_node(node: TraceNode, prefix: str = "", is_last: bool = True, depth: int = 0):
            if depth == 0:
                lines.append(f"  [{node.role}] {node.signal_name} @ {node.module_name}")
                if node.description:
                    lines.append(f"    └─ {node.description}")
                for i, child in enumerate(node.children):
                    _format_node(child, "", i == len(node.children) - 1, 1)
                return
            connector = "└── " if is_last else "├── "
            extension = "   " if is_last else "│  "
            sig_info = f"{node.signal_name}"
            loc = f"  [{node.file_path}:{node.line}]" if node.line else ""
            lines.append(f"{prefix}{connector}[{node.role}] {sig_info} @ {node.module_name}{loc}")
            if node.description:
                lines.append(f"{prefix}{extension}└─ {node.description}")
            if node.children:
                for i, child in enumerate(node.children):
                    _format_node(child, prefix + extension, i == len(node.children) - 1, depth + 1)

        _format_node(result.root)
        lines.append("")
        lines.append(f"节点数: {result.nodes_count}, 最大深度: {result.max_depth}")
        if result.truncated:
            lines.append("⚠️ 已到达最大追踪深度，结果可能不完整")
        if result.nodes_count == 1:
            lines.append("💡 未找到更多追踪路径")
        return "\n".join(lines)
