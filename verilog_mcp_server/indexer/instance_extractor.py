"""
例化提取器 — 提取 module_instantiation 节点
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line, iter_module_body_deep
from ..database.models import InstanceDef

logger = logging.getLogger(__name__)


class InstanceExtractor:
    """提取模块体中的子模块例化"""

    def extract_from_module_body(self, module_body_node, source_text: str, file_path: str) -> list[InstanceDef]:
        """
        从 module body 中提取所有子模块例化
        
        Args:
            module_body_node: module body AST 节点（或整个 module_declaration 节点）
            source_text: 源码文本
            file_path: 文件路径
            
        Returns:
            list[InstanceDef]: 例化列表
        """
        instances = []

        for child in iter_module_body_deep(module_body_node):
            if child.type == "module_instantiation":
                insts = self._extract_instantiation(child, source_text, file_path)
                instances.extend(insts)
            elif child.type == "gate_instantiation":
                insts = self._extract_gate_instantiation(child, source_text, file_path)
                instances.extend(insts)
            elif child.type == "continuous_assign":
                pass  # defparam handled separately

        return instances

    def _extract_instantiation(self, node, source_text: str, file_path: str) -> list[InstanceDef]:
        """从单个 module_instantiation 节点提取所有例化"""
        module_type = None
        param_overrides: dict[str, str] = {}
        instances: list[InstanceDef] = []
        line = get_node_line(node)

        for i in range(node.child_count):
            child = node.child(i)

            if child.type == "simple_identifier":
                # 第一个 simple_identifier 是被例化的模块名
                if module_type is None:
                    module_type = get_node_text(child, source_text)
                module_type = get_node_text(child, source_text)

            elif child.type == "parameter_value_assignment":
                param_overrides = self._extract_param_overrides(child, source_text)

            elif child.type == "hierarchical_instance":
                if module_type:
                    inst = self._extract_hierarchical_instance(child, source_text, file_path, module_type, param_overrides)
                    if inst:
                        instances.append(inst)

        return instances

    def _extract_hierarchical_instance(
        self, node, source_text: str, file_path: str,
        module_type: str, param_overrides: dict[str, str]
    ) -> Optional[InstanceDef]:
        """从 hierarchical_instance 节点提取单个例化（含位置端口支持）"""
        instance_name = None
        port_connections: dict[str, str] = {}
        line = get_node_line(node)

        for i in range(node.child_count):
            child = node.child(i)

            if child.type == "name_of_instance":
                instance_name = get_node_text(child, source_text)

            elif child.type == "list_of_port_connections":
                self._extract_port_connections(child, source_text, module_type,
                                                port_connections)

        if instance_name:
            return InstanceDef(
                module_type=module_type,
                instance_name=instance_name,
                port_connections=port_connections,
                param_overrides=param_overrides,
                file_path=file_path,
                line=line,
            )
        return None

    def _extract_port_connections(self, list_node, source_text: str,
                                    module_type: str, result: dict[str, str]):
        """提取端口连接，支持命名和位置混合"""
        pos_index = 0

        for j in range(list_node.child_count):
            pc = list_node.child(j)
            if pc.type == "named_port_connection":
                formal, actual = self._extract_named_port(pc, source_text)
                if formal:
                    result[formal] = actual
            elif pc.type == "ordered_port_connection":
                actual = get_node_text(pc, source_text)
                formal = self._resolve_positional_port(module_type, pos_index)
                result[formal] = actual
                pos_index += 1

    def _resolve_positional_port(self, module_type: str, pos: int) -> str:
        """按位置解析形式端口名，如果子模块已索引则查找，否则用占位名"""
        if hasattr(self, '_index_store') and self._index_store:
            child_mod = self._index_store.get_module(module_type)
            if child_mod and pos < len(child_mod.ports):
                return child_mod.ports[pos].name
        return f"__pos_{pos}"

    def _extract_named_port(self, node, source_text: str) -> tuple[str, str]:
        """从 named_port_connection 提取 (formal_port_name, actual_signal)"""
        formal = ""
        actual = ""

        for i in range(node.child_count):
            child = node.child(i)

            if child.type == "simple_identifier":
                # 第一个 simple_identifier 是形式端口名
                if not formal:
                    formal = get_node_text(child, source_text)
                else:
                    # 第二个可能是信号名（在 .name(value) 中）
                    pass

            elif child.type == "expression":
                actual = get_node_text(child, source_text)

        return formal, actual

    def _extract_param_overrides(self, node, source_text: str) -> dict[str, str]:
        """提取参数覆盖值 #(...)

        支持两种语法：
        - #(param1=val1, param2=val2)
        - #(.param1(val1), .param2(val2))
        """
        text = get_node_text(node, source_text)
        overrides = {}

        # 简单解析 #(param1=val1, param2=val2)
        inner = text.strip()
        if inner.startswith("#"):
            inner = inner[1:]
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]

        # 按逗号分割（考虑嵌套括号）
        items = []
        depth = 0
        current = ""
        for ch in inner:
            if ch == '(':
                depth += 1
                current += ch
            elif ch == ')':
                depth -= 1
                current += ch
            elif ch == ',' and depth == 0:
                items.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            items.append(current.strip())

        for item in items:
            item = item.strip()
            if not item:
                continue
            # 格式1: param=val
            if '=' in item and not item.startswith("."):
                k, v = item.split('=', 1)
                overrides[k.strip()] = v.strip()
            # 格式2: .param(val)
            elif item.startswith(".") and '(' in item and item.endswith(")"):
                dot_end = item.find("(")
                name = item[1:dot_end].strip()
                value = item[dot_end + 1:-1].strip()
                overrides[name] = value

        return overrides

    # ── 门级原语 ──

    _GATE_PRIMITIVES = {
        "and", "or", "nand", "nor", "xor", "xnor",
        "buf", "not", "bufif0", "bufif1", "notif0", "notif1",
    }

    def _extract_gate_instantiation(self, node, source_text: str, file_path: str) -> list[InstanceDef]:
        """提取门级原语例化"""
        instances = []
        gate_type = None
        line = get_node_line(node)

        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type
            if ckind == "simple_identifier":
                gate_type = get_node_text(child, source_text)
            elif ckind in ("gatetype_switch", "cmos_switchtype"):
                gate_type = get_node_text(child, source_text).lower()

        if not gate_type or gate_type not in self._GATE_PRIMITIVES:
            # 通过 AST 类型名判断
            first = node.child(0)
            if first:
                text = get_node_text(first, source_text).lower().split()[0]
                if text in self._GATE_PRIMITIVES:
                    gate_type = text

        if not gate_type:
            return instances

        # 提取端口连接（位置绑定）
        pos_index = 0
        inst_name = f"__gate_{gate_type}_{line}"
        port_connections = {}

        for child in _iter_children(node):
            if child.type in ("name_of_instance", "simple_identifier"):
                name = get_node_text(child, source_text)
                if name != gate_type and not name.startswith("("):
                    inst_name = name
            elif child.type in ("list_of_port_connections", "gate_instance"):
                for gc in _iter_children(child):
                    if gc.type in ("expression", "simple_identifier"):
                        port_connections[f"__pos_{pos_index}"] = get_node_text(gc, source_text)
                        pos_index += 1

        instances.append(InstanceDef(
            module_type=gate_type,
            instance_name=inst_name,
            port_connections=port_connections,
            param_overrides={},
            file_path=file_path,
            line=line,
            is_primitive=True,
        ))
        return instances

    # ── defparam ──

    def collect_defparams(self, module_node, source_text: str) -> dict[str, str]:
        """从模块体收集所有 defparam 语句"""
        overrides = {}
        for child in iter_module_body_deep(module_node):
            if child.type in ("non_port_module_item", "module_item"):
                for gc in _iter_children(child):
                    if gc.type == "defparam_assignment":
                        self._parse_defparam(gc, source_text, overrides)
        return overrides

    def _parse_defparam(self, node, source_text: str, overrides: dict[str, str]):
        """解析单个 defparam 赋值"""
        text = get_node_text(node, source_text)
        if "=" in text:
            path, _, value = text.partition("=")
            overrides[path.strip()] = value.strip()


def _iter_children(node):
    for i in range(node.child_count):
        yield node.child(i)
