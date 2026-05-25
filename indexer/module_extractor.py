"""
Module 定义提取器
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line, get_node_line_end, find_child
from database.models import ModuleDef

logger = logging.getLogger(__name__)


class ModuleExtractor:
    """从 tree-sitter AST 中提取 module 定义"""

    def extract(self, tree, source_text: str, file_path: str) -> list[ModuleDef]:
        """
        从 AST 中提取所有 module 定义
        
        Args:
            tree: tree-sitter 解析树
            source_text: 源码文本
            file_path: 文件路径
            
        Returns:
            list[ModuleDef]: 提取到的模块列表
        """
        modules = []
        decls = self._find_all_module_declarations(tree.root_node())
        for node in decls:
            mod = self._extract_single_module(node, source_text, file_path)
            if mod:
                modules.append(mod)
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

        # 在 module_ansi_header 中查找模块名
        header = find_child(node, "module_ansi_header")
        if header:
            for i in range(header.child_count()):
                child = header.child(i)
                if child.kind() == "simple_identifier":
                    module_name = get_node_text(child, source_text)
                    break

        if not module_name:
            # 尝试从 module_declaration 的子节点直接找
            for i in range(node.child_count()):
                child = node.child(i)
                if child.kind() == "simple_identifier":
                    module_name = get_node_text(child, source_text)
                    break

        if not module_name:
            return None

        return ModuleDef(
            name=module_name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
        )
