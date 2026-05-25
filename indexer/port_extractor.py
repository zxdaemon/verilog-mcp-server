"""
端口提取器 — 从 module_ansi_header 中提取端口
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, find_child
from database.models import PortDef

logger = logging.getLogger(__name__)


class PortExtractor:
    """
    提取模块的 input/output/inout 端口
    
    支持 ANSI 风格: module mymod (input [7:0] a, output reg b);
    （tree-sitter-systemverilog 只产生一种解析结果：list_of_port_declarations → ansi_port_declaration）
    """

    def extract_from_module(self, module_node, source_text: str) -> list[PortDef]:
        """
        从 module_declaration 节点提取所有端口
        
        Args:
            module_node: module_declaration AST 节点
            source_text: 源码文本
            
        Returns:
            list[PortDef]: 端口列表
        """
        ports = []

        # 从 module_ansi_header 提取端口
        header = find_child(module_node, "module_ansi_header")
        if header:
            ports.extend(self._extract_from_header(header, source_text))

        return ports

    def _extract_from_header(self, header_node, source_text: str) -> list[PortDef]:
        """从 module_ansi_header 节点提取所有端口"""
        ports = []

        list_of_ports = find_child(header_node, "list_of_port_declarations")
        if list_of_ports is None:
            return ports

        for i in range(list_of_ports.child_count()):
            child = list_of_ports.child(i)
            if child.kind() == "ansi_port_declaration":
                port = self._extract_ansi_port(child, source_text)
                if port:
                    ports.append(port)

        return ports

    def _extract_ansi_port(self, node, source_text: str) -> Optional[PortDef]:
        """从单个 ansi_port_declaration 节点提取"""
        direction = "inout"
        var_type = "wire"
        name = None
        width_range = None
        signed = False

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "net_port_header":
                # input/output/inout + wire/logic (implicit)
                hdr_dir, hdr_type, hdr_width, hdr_signed = self._parse_port_header(child, source_text)
                direction = hdr_dir
                var_type = hdr_type if hdr_type else "wire"
                if hdr_width:
                    width_range = hdr_width
                if hdr_signed:
                    signed = True

            elif child.kind() == "variable_port_header":
                # output reg [...] / output logic [...]
                hdr_dir, hdr_type, hdr_width, hdr_signed = self._parse_port_header(child, source_text)
                direction = hdr_dir
                if hdr_type:
                    var_type = hdr_type
                if hdr_width:
                    width_range = hdr_width
                if hdr_signed:
                    signed = True

            elif child.kind() == "simple_identifier":
                name = get_node_text(child, source_text)

        if name:
            return PortDef(
                name=name,
                direction=direction,
                width_range=width_range,
                var_type=var_type,
                signed=signed,
            )
        return None

    def _parse_port_header(self, header_node, source_text: str) -> tuple[str, str, Optional[str], bool]:
        """解析端口头部，返回 (direction, var_type, width_range, signed)"""
        direction = "inout"
        var_type = ""
        width_range = None
        signed = False

        for i in range(header_node.child_count()):
            child = header_node.child(i)

            if child.kind() == "port_direction":
                direction = get_node_text(child, source_text).strip()

            elif child.kind() == "net_port_type":
                w, s = self._parse_port_type(child, source_text)
                if w:
                    width_range = w
                if s:
                    signed = True

            elif child.kind() == "variable_port_type":
                vt, w, s = self._parse_variable_port_type(child, source_text)
                if vt:
                    var_type = vt
                if w:
                    width_range = w
                if s:
                    signed = True

            # 直接 wire/reg/logic 关键字
            elif child.kind() in ("wire", "reg", "logic", "integer"):
                var_type = child.kind()

            # 直接 packed_dimension
            elif child.kind() == "packed_dimension":
                width_range = get_node_text(child, source_text)

            elif child.kind() == "signed":
                signed = True

        return direction, var_type, width_range, signed

    def _parse_port_type(self, node, source_text: str) -> tuple[Optional[str], bool]:
        """解析 net_port_type 节点，递归查找 packed_dimension"""
        width_range = None
        signed = False

        def _search(n, depth=0):
            nonlocal width_range, signed
            if depth > 6:
                return
            if n.kind() == "packed_dimension":
                width_range = get_node_text(n, source_text)
            for i in range(n.child_count()):
                _search(n.child(i), depth + 1)

        _search(node)
        return width_range, signed

    def _parse_variable_port_type(self, node, source_text: str) -> tuple[str, Optional[str], bool]:
        """解析 variable_port_type 节点，返回 (var_type, width_range, signed)"""
        var_type = ""
        width_range = None
        signed = False

        def _search(n, depth=0):
            nonlocal var_type, width_range, signed
            if depth > 6:
                return
            if n.kind() in ("reg", "logic", "integer"):
                var_type = n.kind()
            elif n.kind() == "packed_dimension":
                width_range = get_node_text(n, source_text)
            elif n.kind() == "signed":
                signed = True
            for i in range(n.child_count()):
                _search(n.child(i), depth + 1)

        _search(node)
        return var_type, width_range, signed
