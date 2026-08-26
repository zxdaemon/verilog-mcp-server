"""
Package/import 提取器 — 提取 package 定义和 import 声明
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text, find_child as _find_child
from ..database.models import PackageImportDef, PackageDef, TypeDef, ParamDef

logger = logging.getLogger(__name__)


class PackageExtractor:
    """提取 package 定义和 import 声明"""

    def extract_package_defs(self, tree, source_text: str, file_path: str) -> list[PackageDef]:
        """从 source_file 顶层提取 package 定义"""
        packages = []
        root = tree.root_node

        for i in range(root.child_count):
            child = root.child(i)
            if child.type == "package_declaration":
                pkg = self._extract_package(child, source_text, file_path)
                if pkg:
                    packages.append(pkg)

        return packages

    def extract_imports_from_module(self, module_node, source_text: str) -> list[PackageImportDef]:
        """从 module_declaration 提取 import 声明"""
        imports = []

        def _scan(node):
            for i in range(node.child_count):
                child = node.child(i)
                if child.type == "data_declaration":
                    for j in range(child.child_count):
                        gc = child.child(j)
                        if gc.type == "package_import_declaration":
                            imp = self._parse_import(gc, source_text)
                            if imp:
                                imports.append(imp)
                elif child.type == "module_item":
                    _scan(child)

        _scan(module_node)
        return imports

    def _parse_import(self, node, source_text: str) -> PackageImportDef | None:
        """解析 import_declaration 节点"""
        pkg_name = ""
        symbol = "*"
        wildcard = True

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "package_import_item":
                # import pkg::identifier
                idents = self._collect_simple_identifiers(child, source_text)
                if len(idents) >= 2:
                    pkg_name = idents[0]
                    symbol = idents[1]
                    wildcard = (symbol == "*")
                elif len(idents) == 1:
                    pkg_name = idents[0]

        if pkg_name:
            return PackageImportDef(package=pkg_name, symbol=symbol, wildcard=wildcard)
        return None

    def _extract_package(self, node, source_text: str, file_path: str) -> PackageDef | None:
        """解析 package_declaration 节点"""
        pkg_name = ""
        typedefs = []
        parameters = []

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "simple_identifier":
                pkg_name = get_node_text(child, source_text)

        if not pkg_name:
            return None

        # 提取 package 体内的 typedef 和 parameter
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "package_item":
                for j in range(child.child_count):
                    item = child.child(j)
                    if item.type in ("typedef_declaration", "type_declaration"):
                        td = self._extract_typedef(item, source_text, file_path)
                        if td:
                            typedefs.append(td)
                    elif item.type == "parameter_declaration":
                        params = self._extract_params(item, source_text)
                        parameters.extend(params)

        return PackageDef(name=pkg_name, file_path=file_path, typedefs=typedefs, parameters=parameters)

    def _extract_typedef(self, node, source_text: str, file_path: str) -> TypeDef | None:
        """从 typedef_declaration 提取 TypeDef"""
        name = ""
        kind = "typedef"
        members = []

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "simple_identifier":
                name = get_node_text(child, source_text)
            elif child.type == "enum_declaration":
                kind = "enum"
                for j in range(child.child_count):
                    enum_child = child.child(j)
                    if enum_child.type == "enum_name_list":
                        members = self._collect_enum_members(enum_child, source_text)
            elif child.type == "struct_declaration":
                kind = "struct"
            elif child.type == "union_declaration":
                kind = "union"

        if name:
            source = get_node_text(node, source_text) if hasattr(node, 'start_byte') else ""
            return TypeDef(name=name, kind=kind, members=members, source_text=source[:200],
                           file_path=file_path, line=node.start_point[0] + 1 if hasattr(node, 'start_point') else 0)
        return None

    def _extract_params(self, node, source_text: str) -> list[ParamDef]:
        """从 parameter_declaration 提取参数"""
        params = []

        def _collect(n, depth=0):
            if depth > 8:
                return
            if n.type == "list_of_param_assignments":
                for ci in range(n.child_count):
                    _collect(n.child(ci), depth + 1)
            elif n.type == "param_assignment":
                name = ""
                default = None
                for ci in range(n.child_count):
                    gc = n.child(ci)
                    if gc.type == "simple_identifier":
                        name = get_node_text(gc, source_text)
                ce = self._find_recursive(n, "constant_expression")
                if ce:
                    default = get_node_text(ce, source_text)
                if name:
                    params.append(ParamDef(name=name, default_value=default, type="parameter"))
            else:
                for ci in range(n.child_count):
                    _collect(n.child(ci), depth + 1)

        _collect(node)
        return params

    @staticmethod
    def _find_recursive(node, kind_name: str, max_depth: int = 8):
        """递归查找指定 kind 的子节点"""
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == kind_name:
                return child
        for i in range(node.child_count):
            if max_depth > 0:
                result = PackageExtractor._find_recursive(node.child(i), kind_name, max_depth - 1)
                if result:
                    return result
        return None

    def _collect_enum_members(self, node, source_text: str) -> list[str]:
        """收集枚举成员名称"""
        members = []
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "enum_name":
                name_node = _find_child(child, "simple_identifier")
                if name_node:
                    members.append(get_node_text(name_node, source_text))
        return members

    @staticmethod
    def _collect_simple_identifiers(node, source_text: str = "") -> list[str]:
        """收集节点内所有 simple_identifier 文本"""
        idents = []

        def _walk(n, depth=0):
            if depth > 6:
                return
            if n.type == "simple_identifier":
                idents.append(get_node_text(n, source_text))
            for ci in range(n.child_count):
                _walk(n.child(ci), depth + 1)

        _walk(node)
        return idents
