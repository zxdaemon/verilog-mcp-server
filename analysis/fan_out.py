"""
信号 Fan-out 追踪引擎 (下游扩展)

在 fan_in.py 基础上添加 fan-out 追踪能力。
"""

from __future__ import annotations

from .fan_in import (
    DataflowTracer as _BaseTracer, TraceNode, TraceResult,
)

from database.models import ModuleDef


class DataflowTracer(_BaseTracer):
    """完整的数据流追踪器 — 继承 fan_in 基类，添加 fan_out 方法"""

    def _trace_fan_out(self, parent: TraceNode, signal_name: str, module_name: str,
                       instance_path: str, depth: int, max_depth: int):
        if depth > max_depth:
            return
        visit_key = (module_name, signal_name, "fan_out")
        if visit_key in self._visited:
            return
        self._visited.add(visit_key)

        mod = self._index_store.get_module(module_name)
        if not mod:
            return

        is_port = self._is_port(mod, signal_name)
        if is_port:
            port = self._get_port(mod, signal_name)
            if port and port.direction == "output":
                self._trace_output_port_fan_out(parent, signal_name, module_name, instance_path, depth, max_depth)
            elif port and port.direction == "input":
                self._trace_input_port_fan_out(parent, signal_name, module_name, instance_path, depth, max_depth)

        sig = self._get_signal(mod, signal_name)
        if sig and sig.loads:
            for load in sig.loads:
                child = TraceNode(
                    signal_name=signal_name, module_name=module_name,
                    instance_path=instance_path, role=f"load_{load.type}",
                    description=f"负载 ({load.type}): {load.target}",
                    file_path=load.file_path or mod.file_path,
                    line=load.line, depth=depth,
                )
                parent.children.append(child)
                if load.type == "assign":
                    self._trace_assign_lhs_fan_out(child, signal_name, module_name, instance_path, mod, depth + 1, max_depth, load)
                elif load.type == "always_block":
                    self._trace_always_lhs_fan_out(child, signal_name, module_name, instance_path, mod, depth + 1, max_depth, load)

        self._trace_instance_port_fan_out(parent, signal_name, module_name, instance_path, depth, max_depth)

    def _trace_output_port_fan_out(self, parent, signal_name, module_name, instance_path, depth, max_depth):
        mod_name_lower = module_name.lower()
        for parent_mod in self._index_store.get_all_modules():
            for inst in parent_mod.instances:
                if inst.module_type.lower() == mod_name_lower:
                    actual_signal = inst.port_connections.get(signal_name)
                    if actual_signal:
                        child = TraceNode(
                            signal_name=actual_signal, module_name=parent_mod.name,
                            instance_path=parent_mod.name, role="port_output_down",
                            description=f"output端口 {signal_name} 在例化 {inst.instance_name} 中连接到 {actual_signal}",
                            file_path=inst.file_path or parent_mod.file_path,
                            line=inst.line, depth=depth,
                        )
                        parent.children.append(child)
                        self._trace_fan_out(child, actual_signal, parent_mod.name, parent_mod.name, depth + 1, max_depth)

    def _trace_input_port_fan_out(self, parent, signal_name, module_name, instance_path, depth, max_depth):
        mod = self._index_store.get_module(module_name)
        if not mod:
            return
        sig = self._get_signal(mod, signal_name)
        if sig and sig.loads:
            for load in sig.loads:
                child = TraceNode(
                    signal_name=signal_name, module_name=module_name,
                    instance_path=instance_path, role=f"input_fan_out_{load.type}",
                    description=f"内部负载 ({load.type}): {load.target}",
                    file_path=load.file_path or mod.file_path,
                    line=load.line, depth=depth,
                )
                parent.children.append(child)

    def _trace_instance_port_fan_out(self, parent, signal_name, module_name, instance_path, depth, max_depth):
        mod = self._index_store.get_module(module_name)
        if not mod:
            return
        for inst in mod.instances:
            for formal_port, actual_signal in inst.port_connections.items():
                if actual_signal == signal_name:
                    child_mod = self._index_store.get_module(inst.module_type)
                    if child_mod:
                        child_port = self._get_port(child_mod, formal_port)
                        if child_port and child_port.direction == "input":
                            child = TraceNode(
                                signal_name=formal_port, module_name=child_mod.name,
                                instance_path=f"{instance_path}.{inst.instance_name}",
                                role="instance_input_cross",
                                description=f"进入子模块 {inst.module_type}.{inst.instance_name} 的 input 端口 {formal_port}",
                                file_path=inst.file_path or child_mod.file_path,
                                line=inst.line, depth=depth,
                            )
                            parent.children.append(child)
                            self._trace_fan_out(child, formal_port, child_mod.name,
                                              f"{instance_path}.{inst.instance_name}", depth + 1, max_depth)

    # ── Assign / Always fan-out 辅助 ──

    def _trace_assign_lhs_fan_out(self, parent, signal_name, module_name, instance_path, mod, depth, max_depth, load):
        for assign in mod.assignments:
            rhs_sigs = self._extract_signal_names(assign.rhs)
            if signal_name in rhs_sigs:
                child = TraceNode(
                    signal_name=assign.lhs, module_name=module_name,
                    instance_path=instance_path, role="assign_lhs",
                    description=f"assign {assign.lhs} = {assign.rhs} 中的负载",
                    file_path=assign.file_path or mod.file_path,
                    line=assign.line, depth=depth,
                )
                parent.children.append(child)
                self._trace_fan_out(child, assign.lhs, module_name, instance_path, depth + 1, max_depth)
                break

    def _trace_always_lhs_fan_out(self, parent, signal_name, module_name, instance_path, mod, depth, max_depth, load):
        for always in mod.always_blocks:
            sens_list = always.sensitivity_list
            if signal_name in sens_list.replace("posedge ", "").replace("negedge ", "").split(" or "):
                for stmt in always.statements:
                    if "=" in stmt or "<=" in stmt:
                        delim = "<=" if "<=" in stmt else "="
                        parts = stmt.split(delim, 1)
                        lhs = parts[0].strip()
                        if not lhs.startswith("//"):
                            child = TraceNode(
                                signal_name=lhs, module_name=module_name,
                                instance_path=instance_path, role="always_lhs",
                                description=f"always 块中赋值目标: {lhs}，敏感列表包含 {signal_name}",
                                file_path=mod.file_path, depth=depth,
                            )
                            parent.children.append(child)
                            self._trace_fan_out(child, lhs, module_name, instance_path, depth + 1, max_depth)
