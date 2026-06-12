"""
Module 定义提取器
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line, get_node_line_end, find_child, iter_module_body
from ..database.models import ModuleDef, ParamDef

logger = logging.getLogger(__name__)


class ModuleExtractor:
    """从 tree-sitter AST 中提取 module 定义"""

    def extract(self, tree, source_text: str, file_path: str) -> list[tuple[ModuleDef, object]]:
        """
        从 AST 中提取所有 module 定义，同时返回 AST 节点引用避免重复遍历

        Returns:
            list[tuple[ModuleDef, AST node]]: (模块定义, module_declaration AST 节点) 列表
        """
        modules: list[tuple[ModuleDef, object]] = []
        decls = self._find_all_module_declarations(tree.root_node())
        for node in decls:
            mod = self._extract_single_module(node, source_text, file_path)
            if mod:
                modules.append((mod, node))
        return modules

    def _find_all_module_declarations(self, node) -> list:
        """递归查找所有 module_declaration 节点"""
        results = []
        self._collect_module_decls(node, results)
        return results

    def _collect_module_decls(self, node, results: list) -> None:
        if node.kind() == "module_declaration":
            results.append(node)
            return  # 不递归到内部
        for i in range(node.child_count()):
            self._collect_module_decls(node.child(i), results)

    def _extract_single_module(self, node, source_text: str, file_path: str) -> Optional[ModuleDef]:
        """从单个 module_declaration 节点提取信息"""
        module_name = None
        line_start = get_node_line(node)
        line_end = get_node_line_end(node)

        header = find_child(node, "module_ansi_header")
        if not header:
            header = find_child(node, "module_nonansi_header")
        if header:
            for i in range(header.child_count()):
                child = header.child(i)
                if child.kind() == "simple_identifier":
                    module_name = get_node_text(child, source_text)
                    break

        if not module_name:
            for i in range(node.child_count()):
                child = node.child(i)
                if child.kind() == "simple_identifier":
                    module_name = get_node_text(child, source_text)
                    break

        if not module_name:
            return None

        parameters = self._extract_parameters(node, source_text)

        return ModuleDef(
            name=module_name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            parameters=parameters,
        )

    def _extract_parameters(self, module_node, source_text: str) -> list[ParamDef]:
        """提取模块 parameter/localparam 声明"""
        params: list[ParamDef] = []

        # 1. 从 module header 的 parameter_port_list 中提取 #(...)
        header = find_child(module_node, "module_ansi_header")
        if not header:
            header = find_child(module_node, "module_nonansi_header")
        if header:
            param_list = find_child(header, "parameter_port_list")
            if param_list:
                for i in range(param_list.child_count()):
                    child = param_list.child(i)
                    if child.kind() == "parameter_declaration":
                        p = self._parse_param_decl(child, source_text, "parameter")
                        if p:
                            params.append(p)
                    elif child.kind() == "parameter_port_declaration":
                        # wrapper: parameter_port_declaration → parameter_declaration
                        for j in range(child.child_count()):
                            gc = child.child(j)
                            if gc.kind() == "parameter_declaration":
                                p = self._parse_param_decl(gc, source_text, "parameter")
                                if p:
                                    params.append(p)

        # 2. 从 module body 中提取 parameter 和 localparam
        for child in iter_module_body(module_node):
            if child.kind() == "parameter_declaration":
                p = self._parse_param_decl(child, source_text, "parameter")
                if p:
                    params.append(p)
            elif child.kind() == "local_parameter_declaration":
                p = self._parse_param_decl(child, source_text, "localparam")
                if p:
                    params.append(p)

        return params

    def _parse_param_decl(self, node, source_text: str, param_type: str) -> ParamDef | None:
        """解析单个 parameter/localparam 声明"""
        name = ""
        default_value = None

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() in ("list_of_param_assignments", "list_of_variable_decl_assignments"):
                for j in range(child.child_count()):
                    gc = child.child(j)
                    if gc.kind() in ("param_assignment", "variable_decl_assignment"):
                        for k in range(gc.child_count()):
                            kc = gc.child(k)
                            if kc.kind() == "simple_identifier" and not name:
                                name = get_node_text(kc, source_text)
                            elif kc.kind() in ("expression", "constant_param_expression",
                                                "constant_expression",
                                                "constant_mintypmax_expression"):
                                default_value = get_node_text(kc, source_text)

        if not name:
            # fallback: 找第一个 simple_identifier
            for i in range(node.child_count()):
                c = node.child(i)
                if c.kind() == "simple_identifier":
                    name = get_node_text(c, source_text)
                    break

        if not name:
            return None

        return ParamDef(name=name, type=param_type, default_value=default_value)
