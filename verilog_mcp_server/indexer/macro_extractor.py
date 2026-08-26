"""
宏提取器 — 提取 `define 宏定义、宏使用和条件编译分支
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text
from ..database.models import MacroDef, ConditionalBranch

logger = logging.getLogger(__name__)


class MacroExtractor:
    """提取 `define 宏定义、宏使用和条件编译结构"""

    def extract_defines(self, tree, source_text: str, file_path: str) -> list[MacroDef]:
        """从 source_file 提取所有 `define 宏定义"""
        defines = []
        root = tree.root_node

        for i in range(root.child_count):
            child = root.child(i)
            if child.type == "text_macro_definition":
                md = self._parse_define(child, source_text, file_path)
                if md:
                    defines.append(md)

        return defines

    def extract_conditionals(self, tree, source_text: str) -> list[ConditionalBranch]:
        """从 source_file 提取条件编译分支结构"""
        root = tree.root_node
        branches = []
        stack: list[ConditionalBranch] = []

        for i in range(root.child_count):
            child = root.child(i)
            if child.type != "conditional_compilation_directive":
                continue

            first_child = child.child(0) if child.child_count > 0 else None
            if first_child is None:
                continue

            kind = first_child.type
            line = child.start_point.row + 1

            if kind in ("`ifdef", "`ifndef"):
                branch_type = "ifdef" if kind == "`ifdef" else "ifndef"
                condition = self._extract_ifdef_condition(child, source_text)
                branch = ConditionalBranch(
                    condition=condition,
                    branch_type=branch_type,
                    start_line=line,
                )
                if stack:
                    stack[-1].children.append(branch)
                else:
                    branches.append(branch)
                stack.append(branch)

            elif kind == "`elsif":
                if stack:
                    stack[-1].end_line = line
                    branch = ConditionalBranch(
                        condition=self._extract_elsif_condition(child, source_text),
                        branch_type="elsif",
                        start_line=line,
                    )
                    stack[-1].children.append(branch)
                    stack[-1] = branch

            elif kind == "`else":
                if stack:
                    stack[-1].end_line = line
                    branch = ConditionalBranch(
                        condition="",
                        branch_type="else",
                        start_line=line,
                    )
                    stack[-1].children.append(branch)
                    stack[-1] = branch

            elif kind == "`endif":
                if stack:
                    stack[-1].end_line = line
                    stack.pop()

        return branches

    @staticmethod
    def _extract_ifdef_condition(node, source_text: str) -> str:
        """从 conditional_compilation_directive 提取 ifdef/ifndef 条件"""
        for i in range(node.child_count):
            c = node.child(i)
            if c.type == "ifdef_condition":
                for j in range(c.child_count):
                    gc = c.child(j)
                    if gc.type == "simple_identifier":
                        return get_node_text(gc, source_text)
        return ""

    @staticmethod
    def _extract_elsif_condition(node, source_text: str) -> str:
        """从 conditional_compilation_directive 提取 elsif 条件"""
        for i in range(node.child_count):
            c = node.child(i)
            if c.type == "elsif_condition":
                for j in range(c.child_count):
                    gc = c.child(j)
                    if gc.type == "simple_identifier":
                        return get_node_text(gc, source_text)
        return ""

    def extract_macro_usages(self, module_node, source_text: str) -> list[dict]:
        """从模块中提取宏使用，返回 [{"name": ..., "line": ...}]"""
        usages = []

        def _walk(n, depth=0):
            if depth > 12:
                return
            if n.type == "text_macro_usage":
                for i in range(n.child_count):
                    c = n.child(i)
                    if c.type == "simple_identifier":
                        name = get_node_text(c, source_text)
                        line = n.start_point.row + 1
                        usages.append({"name": name, "line": line})
                        break
            for i in range(n.child_count):
                _walk(n.child(i), depth + 1)

        _walk(module_node)
        return usages

    def _parse_define(self, node, source_text: str, file_path: str) -> MacroDef | None:
        """解析 text_macro_definition 节点"""
        name = ""
        params = []
        value = ""

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "text_macro_name":
                for j in range(child.child_count):
                    gc = child.child(j)
                    if gc.type == "simple_identifier":
                        name = get_node_text(gc, source_text)
                    elif gc.type == "list_of_formal_arguments":
                        for k in range(gc.child_count):
                            arg = gc.child(k)
                            if arg.type == "formal_argument":
                                for m in range(arg.child_count):
                                    am = arg.child(m)
                                    if am.type == "simple_identifier":
                                        params.append(get_node_text(am, source_text))
            elif child.type == "macro_text":
                value = get_node_text(child, source_text).strip()

        if name:
            line = node.start_point.row + 1
            return MacroDef(name=name, params=params, value=value,
                            file_path=file_path, line=line)
        return None
