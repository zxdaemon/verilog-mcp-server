"""
端口提取器 — 从 module_ansi_header 中提取端口
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, find_child
from ..database.models import PortDef

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
        else:
            # 非 ANSI 风格: module_nonansi_header + port_declaration
            nonansi_header = find_child(module_node, "module_nonansi_header")
            if nonansi_header:
                ports.extend(self._extract_nonansi(module_node, nonansi_header, source_text))

        return ports

    def _extract_nonansi(self, module_node, header_node, source_text: str) -> list[PortDef]:
        """从非 ANSI 风格模块声明中提取端口"""
        # 1. 从 list_of_ports 获取端口名列表
        port_names = []
        list_of_ports = find_child(header_node, "list_of_ports")
        if list_of_ports:
            for i in range(list_of_ports.child_count()):
                child = list_of_ports.child(i)
                if child.kind() == "port":
                    name_node = find_child(child, "simple_identifier")
                    if name_node:
                        port_names.append(get_node_text(name_node, source_text))

        # 2. 从 module_item → port_declaration 获取方向和类型
        port_info: dict[str, dict] = {name: {"direction": "inout", "var_type": "wire"} for name in port_names}
        for i in range(module_node.child_count()):
            child = module_node.child(i)
            if child.kind() != "module_item":
                continue
            port_decl = find_child(child, "port_declaration")
            if port_decl is None:
                continue
            # 提取方向
            for decl_kind, direction in [("input_declaration", "input"),
                                          ("output_declaration", "output"),
                                          ("inout_declaration", "inout")]:
                decl = find_child(port_decl, decl_kind)
                if decl:
                    # 获取类型
                    for j in range(decl.child_count()):
                        dc = decl.child(j)
                        if dc.kind() == "list_of_port_identifiers":
                            for k in range(dc.child_count()):
                                id_child = dc.child(k)
                                if id_child.kind() == "simple_identifier":
                                    ident_name = get_node_text(id_child, source_text)
                                    if ident_name in port_info:
                                        port_info[ident_name]["direction"] = direction
                    break

        # 3. 构建 PortDef 列表
        ports = []
        for name in port_names:
            info = port_info.get(name, {"direction": "inout", "var_type": "wire"})
            ports.append(PortDef(
                name=name,
                direction=info["direction"],
                var_type=info.get("var_type", "wire"),
            ))
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
        """从单个 ansi_port_declaration 节点提取（含 interface_port 支持）"""
        direction = "inout"
        var_type = "wire"
        name = None
        width_range = None
        signed = False
        description = ""

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "interface_port_header":
                # interface 端口: axis_if.slave rx
                # interface_port_header 包含 interface 类型名和 modport
                iface_type, iface_name = self._parse_interface_port(node, source_text, i)
                if iface_type:
                    description = f"interface:{iface_type}"
                    var_type = "interface"
                    name = iface_name

            elif child.kind() == "net_port_header":
                hdr_dir, hdr_type, hdr_width, hdr_signed = self._parse_port_header(child, source_text)
                direction = hdr_dir
                var_type = hdr_type if hdr_type else "wire"
                if hdr_width:
                    width_range = hdr_width
                if hdr_signed:
                    signed = True

            elif child.kind() == "variable_port_header":
                hdr_dir, hdr_type, hdr_width, hdr_signed = self._parse_port_header(child, source_text)
                direction = hdr_dir
                if hdr_type:
                    var_type = hdr_type
                if hdr_width:
                    width_range = hdr_width
                if hdr_signed:
                    signed = True

                # 检测简单 interface 端口（无 modport）：header 内容为 interface 类型名
                if not hdr_type and not hdr_width and direction == "inout":
                    hdr_text = get_node_text(child, source_text)
                    if hdr_text and hdr_text not in ("wire", "reg", "logic", "integer",
                                                      "input", "output", "inout"):
                        description = f"interface:{hdr_text}"
                        var_type = "interface"

            elif child.kind() == "simple_identifier":
                name = get_node_text(child, source_text)

        if name:
            return PortDef(
                name=name,
                direction=direction,
                width_range=width_range,
                var_type=var_type,
                signed=signed,
                description=description,
            )
        return None

    def _parse_interface_port(self, ansi_port_node, source_text: str, iface_header_idx: int) -> tuple[str, str]:
        """解析 interface_port_header 及其后的端口名，返回 (interface_type, port_name)

        interface_port_header 下是 simple_identifier 列表: type_name [, modport_name]
        端口名是紧随其后的 simple_identifier
        """
        iface_type = ""
        port_name = ""
        header = ansi_port_node.child(iface_header_idx)

        # 从 interface_port_header 中提取类型名和 modport
        for j in range(header.child_count()):
            child = header.child(j)
            if child.kind() == "simple_identifier":
                text = get_node_text(child, source_text)
                if not iface_type:
                    iface_type = text
                else:
                    iface_type += f".{text}"

        # 从 ansi_port_declaration 中提取端口名（header 之后的 simple_identifier）
        for j in range(iface_header_idx + 1, ansi_port_node.child_count()):
            child = ansi_port_node.child(j)
            if child.kind() == "simple_identifier":
                port_name = get_node_text(child, source_text)
                break

        return iface_type, port_name

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
