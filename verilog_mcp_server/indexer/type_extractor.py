"""
类型提取器 — 提取 struct / enum / typedef 定义
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text, get_node_line, iter_module_body_deep
from ..database.models import TypeDef

logger = logging.getLogger(__name__)


class TypeExtractor:
    """提取模块体中的 struct/enum/typedef 定义"""

    def extract_types(self, module_body_node, source_text: str, file_path: str) -> list[TypeDef]:
        """从模块体中提取所有类型定义"""
        types: list[TypeDef] = []

        for child in iter_module_body_deep(module_body_node):
            kind = child.kind()

            if kind == "data_declaration":
                # data_declaration 可能包含 type_declaration (typedef) 或 enum/struct 声明
                self._extract_from_data_decl(child, source_text, file_path, types)

        return types

    def _extract_from_data_decl(self, node, source_text: str, file_path: str,
                                 results: list[TypeDef]):
        """从 data_declaration 中提取类型"""
        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "type_declaration":
                # typedef enum/struct
                self._extract_typedef(child, source_text, file_path, results)
                return

    def _extract_typedef(self, node, source_text: str, file_path: str,
                          results: list[TypeDef]):
        """从 type_declaration 提取 typedef enum/struct"""
        name = ""
        kind = "typedef"
        members: list[str] = []

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "data_type":
                for j in range(child.child_count()):
                    gc = child.child(j)
                    if gc.kind() == "enum":
                        members = self._extract_enum_members(child, source_text)
                        kind = "enum"
                    elif gc.kind() == "struct_union":
                        # struct_union contains 'struct' keyword, struct members are in data_type
                        members = self._extract_struct_members(child, source_text)
                        kind = "struct"

            elif child.kind() == "simple_identifier":
                name = get_node_text(child, source_text)

        if name and kind != "typedef":
            results.append(TypeDef(
                name=name, kind=kind, members=members,
                source_text=get_node_text(node, source_text)[:512],
                file_path=file_path, line=get_node_line(node),
            ))

    def _extract_enum_members(self, data_type_node, source_text: str) -> list[str]:
        """从 data_type (含 enum) 提取成员标识符列表"""
        members: list[str] = []

        def _walk(n, depth=0):
            if depth > 30:
                return
            if n.kind() == "enum_name_declaration":
                for i in range(n.child_count()):
                    if n.child(i).kind() == "simple_identifier":
                        text = get_node_text(n.child(i), source_text)
                        if text not in members:
                            members.append(text)
            for i in range(n.child_count()):
                _walk(n.child(i), depth + 1)

        _walk(data_type_node)
        return members

    def _extract_struct_members(self, data_type_node, source_text: str) -> list[str]:
        """从 data_type (含 struct) 提取字段名列表"""
        members: list[str] = []

        def _walk(n, depth=0):
            if depth > 30:
                return
            if n.kind() == "struct_union_member":
                for i in range(n.child_count()):
                    c = n.child(i)
                    if c.kind() in ("list_of_variable_decl_assignments",
                                     "list_of_net_decl_assignments"):
                        for j in range(c.child_count()):
                            gc = c.child(j)
                            if gc.kind() in ("variable_decl_assignment",
                                              "net_decl_assignment"):
                                for k in range(gc.child_count()):
                                    if gc.child(k).kind() == "simple_identifier":
                                        members.append(get_node_text(gc.child(k), source_text))
            for i in range(n.child_count()):
                _walk(n.child(i), depth + 1)

        _walk(data_type_node)
        return members
