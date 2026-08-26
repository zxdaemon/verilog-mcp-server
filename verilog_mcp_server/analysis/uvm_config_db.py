"""
UVM Config DB 追踪器 — 分析 uvm_config_db::set/get 调用和配对
"""

from __future__ import annotations
import logging

from ..database.models import UvmConfigEntry
from ..indexer.uvm_extractor import UvmExtractor

logger = logging.getLogger(__name__)


class UvmConfigDbTracer:
    """追踪 uvm_config_db#(type)::set/get 调用"""

    def __init__(self):
        self._extractor = UvmExtractor()

    def analyze_file(self, tree, source_text: str, file_path: str) -> list[UvmConfigEntry]:
        """分析单个文件中的 config_db 调用"""
        entries = []
        calls = self._extractor.find_config_db_calls(tree.root_node, source_text)

        for call in calls:
            entries.append(UvmConfigEntry(
                field_name=call["field_name"],
                type_param=call["type_param"],
                scope=call["scope"],
                operation=call["operation"],
                component="",
                value_hint=call["value_hint"],
                file_path=file_path,
                line=call.get("line", 0),
            ))

        return entries

    def match_pairs(self, entries: list[UvmConfigEntry]) -> dict:
        """匹配 set/get 配对

        Returns:
            {
                "matched": [(set_entry, get_entry), ...],
                "unmatched_sets": [...],
                "unmatched_gets": [...],
            }
        """
        sets = [e for e in entries if e.operation == "set"]
        gets = [e for e in entries if e.operation == "get"]

        matched = []
        unmatched_sets = list(sets)
        unmatched_gets = list(gets)

        for s in sets[:]:
            for g in gets[:]:
                if s.field_name == g.field_name and s.type_param == g.type_param:
                    matched.append((s, g))
                    if s in unmatched_sets:
                        unmatched_sets.remove(s)
                    if g in unmatched_gets:
                        unmatched_gets.remove(g)

        return {
            "matched": matched,
            "unmatched_sets": unmatched_sets,
            "unmatched_gets": unmatched_gets,
        }

    def format_report(self, entries: list[UvmConfigEntry]) -> str:
        """格式化 config_db 追踪报告"""
        match_result = self.match_pairs(entries)
        lines = ["UVM Config DB Trace Report", "=" * 40]

        if match_result["matched"]:
            lines.append(f"\nMatched Pairs ({len(match_result['matched'])}):")
            for s, g in match_result["matched"]:
                lines.append(
                    f"  {s.field_name} [{s.type_param}]: "
                    f"set({s.value_hint}) -> get({g.value_hint}) "
                    f"scope={s.scope}"
                )

        if match_result["unmatched_sets"]:
            lines.append(f"\nUnmatched Sets ({len(match_result['unmatched_sets'])}):")
            for s in match_result["unmatched_sets"]:
                lines.append(
                    f"  {s.field_name} [{s.type_param}] = {s.value_hint} "
                    f"(scope={s.scope}, line={s.line})"
                )

        if match_result["unmatched_gets"]:
            lines.append(f"\nUnmatched Gets ({len(match_result['unmatched_gets'])}):")
            for g in match_result["unmatched_gets"]:
                lines.append(
                    f"  {g.field_name} [{g.type_param}] -> {g.value_hint} "
                    f"(scope={g.scope}, line={g.line})"
                )

        if not entries:
            lines.append("\nNo uvm_config_db calls found.")

        return "\n".join(lines)
