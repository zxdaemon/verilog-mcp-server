"""
Function / Task 提取器 — 提取 function 和 task 声明
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text, find_child, find_children, get_node_line
from ..database.models import FunctionDef, PortDef

logger = logging.getLogger(__name__)

# function/task 端口方向映射
_PORT_DIR_MAP = {
    "input": "input",
    "output": "output",
    "inout": "inout",
    "ref": "ref",
}


class FunctionTaskExtractor:
    """提取 function 和 task 声明"""

    def extract_from_module(self, module_node, source_text: str, file_path: str) -> list[FunctionDef]:
        """从模块体中提取所有 function/task"""
        results = []
        for child in _iter_children(module_node):
            kind = child.type
            if kind == "function_declaration":
                func = self._extract_function(child, source_text, file_path, "function")
                if func:
                    results.append(func)
            elif kind == "task_declaration":
                func = self._extract_function(child, source_text, file_path, "task")
                if func:
                    results.append(func)
        return results

    def _extract_function(self, node, source_text: str, file_path: str, kind: str) -> FunctionDef | None:
        """提取单个 function/task"""
        try:
            name = ""
            return_type = ""
            ports = []

            for child in _iter_children(node):
                ckind = child.type
                if ckind == "simple_identifier":
                    name = get_node_text(child, source_text)
                elif ckind in ("function_body_declaration", "task_body_declaration"):
                    name, return_type, ports = self._parse_body_decl(child, source_text)
                elif ckind == "tf_port_list":
                    ports = self._parse_tf_ports(child, source_text)

            if not name:
                return None

            body = get_node_text(node, source_text)

            return FunctionDef(
                name=name,
                kind=kind,
                return_type=return_type,
                ports=ports,
                body=body,
                file_path=file_path,
                line=get_node_line(node),
            )
        except Exception as e:
            logger.debug(f"提取 {kind} 失败: {e}")
            return None

    def _parse_body_decl(self, node, source_text: str) -> tuple[str, str, list[PortDef]]:
        """解析 function_body_declaration"""
        name = ""
        return_type = ""
        ports = []

        for child in _iter_children(node):
            ckind = child.type
            if ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "data_type_or_void":
                return_type = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                ports = self._parse_tf_ports(child, source_text)
            elif ckind == "tf_item_declaration":
                # function 内部变量声明中的端口
                pass

        return name, return_type, ports

    def _parse_tf_ports(self, node, source_text: str) -> list[PortDef]:
        """解析 tf_port_list"""
        ports = []
        for child in _iter_children(node):
            if child.type == "tf_port_item":
                port = self._parse_tf_port_item(child, source_text)
                if port:
                    ports.append(port)
        return ports

    def _parse_tf_port_item(self, node, source_text: str) -> PortDef | None:
        """解析单个 tf_port_item"""
        direction = "input"
        var_type = ""
        width = ""
        name = ""

        for child in _iter_children(node):
            ckind = child.type
            if ckind in _PORT_DIR_MAP:
                direction = _PORT_DIR_MAP[ckind]
            elif ckind == "tf_port_direction":
                dir_text = get_node_text(child, source_text)
                for k, v in _PORT_DIR_MAP.items():
                    if k in dir_text:
                        direction = v
                        break
            elif ckind == "data_type":
                var_type = get_node_text(child, source_text)
            elif ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "packed_dimension":
                width = get_node_text(child, source_text)

        if not name:
            return None

        return PortDef(
            name=name,
            direction=direction,
            var_type=var_type,
            width_range=width,
        )


def _iter_children(node):
    """遍历节点所有子节点"""
    for i in range(node.child_count):
        yield node.child(i)
