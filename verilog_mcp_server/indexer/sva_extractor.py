"""
SVA 断言提取器 — 提取 immediate/concurrent 断言及 property/sequence 定义
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text
from ..database.models import SvaDef

logger = logging.getLogger(__name__)


class SvaExtractor:
    """提取 SVA 断言（immediate、concurrent、property、sequence）"""

    def extract_from_module(self, module_node, source_text: str) -> list[SvaDef]:
        """从 module_declaration 提取所有断言"""
        assertions = []

        for i in range(module_node.child_count):
            child = module_node.child(i)

            # Module-level concurrent assertions
            if child.type == "concurrent_assertion_item":
                sva = self._extract_concurrent_assertion(child, source_text)
                if sva:
                    assertions.append(sva)

            # Property and sequence declarations
            elif child.type == "property_declaration":
                sva = self._extract_property_decl(child, source_text)
                if sva:
                    assertions.append(sva)
            elif child.type == "sequence_declaration":
                sva = self._extract_sequence_decl(child, source_text)
                if sva:
                    assertions.append(sva)

            # Immediate assertions in procedural blocks (recursive)
            elif child.type == "always_construct" or child.type == "initial_construct":
                for sva in self._extract_immediate_from_block(child, source_text):
                    assertions.append(sva)

            # Also check module_item for always/initial blocks
            elif child.type == "module_item":
                for j in range(child.child_count):
                    gc = child.child(j)
                    if gc.type in ("always_construct", "initial_construct"):
                        for sva in self._extract_immediate_from_block(gc, source_text):
                            assertions.append(sva)

        return assertions

    def _extract_concurrent_assertion(self, node, source_text: str) -> SvaDef | None:
        """提取 concurrent assertion item"""
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "assert_property_statement":
                return self._parse_property_statement(child, source_text, "assert")
            elif child.type == "assume_property_statement":
                return self._parse_property_statement(child, source_text, "assume")
            elif child.type == "cover_property_statement":
                return self._parse_property_statement(child, source_text, "cover")
        return None

    def _parse_property_statement(self, node, source_text: str, keyword: str) -> SvaDef:
        """解析 assert/assume/cover property 语句"""
        clock = ""
        prop = ""
        action = ""

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "property_spec":
                for j in range(child.child_count):
                    gc = child.child(j)
                    if gc.type == "clocking_event":
                        clock = get_node_text(gc, source_text).strip()
                    elif gc.type == "property_expr":
                        prop = get_node_text(gc, source_text).strip()
            elif child.type == "action_block":
                action = get_node_text(child, source_text).strip()

        return SvaDef(type="concurrent", keyword=keyword,
                      property=prop, clock=clock, action=action)

    def _extract_property_decl(self, node, source_text: str) -> SvaDef:
        """提取 property 声明"""
        name = ""
        body = ""

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "simple_identifier":
                name = get_node_text(child, source_text)
            elif child.type == "property_spec":
                body = get_node_text(child, source_text).strip()

        return SvaDef(type="property", keyword="property", name=name, body=body)

    def _extract_sequence_decl(self, node, source_text: str) -> SvaDef:
        """提取 sequence 声明"""
        name = ""
        body = ""

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "simple_identifier":
                name = get_node_text(child, source_text)
            elif child.type == "sequence_expr":
                body = get_node_text(child, source_text).strip()

        return SvaDef(type="sequence", keyword="sequence", name=name, body=body)

    def _extract_immediate_from_block(self, node, source_text: str) -> list[SvaDef]:
        """从 always/initial 块递归提取 immediate assertion"""
        results = []

        def _walk(n, depth=0):
            if depth > 12:
                return
            kind = n.type
            if kind == "simple_immediate_assert_statement":
                results.append(self._extract_immediate_assert(n, source_text, "assert"))
            elif kind == "simple_immediate_assume_statement":
                results.append(self._extract_immediate_assert(n, source_text, "assume"))
            elif kind == "simple_immediate_cover_statement":
                results.append(self._extract_immediate_assert(n, source_text, "cover"))
            elif kind == "immediate_assert_statement":
                results.append(self._extract_immediate_assert(n, source_text, "assert"))
            for i in range(n.child_count):
                _walk(n.child(i), depth + 1)

        _walk(node)
        return results

    def _extract_immediate_assert(self, node, source_text: str, keyword: str) -> SvaDef:
        """提取 immediate assertion (assert/assume/cover)"""
        expression = ""
        action = ""

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "expression":
                expression = get_node_text(child, source_text).strip()
            elif child.type == "action_block":
                action = get_node_text(child, source_text).strip()

        return SvaDef(type="immediate", keyword=keyword,
                      expression=expression, action=action)
