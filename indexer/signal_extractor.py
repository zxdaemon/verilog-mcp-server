"""
信号提取器 — 提取 wire/reg/logic 声明、assign、always
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line
from database.models import SignalDef, AlwaysBlockInfo, AssignmentInfo

logger = logging.getLogger(__name__)


class SignalExtractor:
    """
    从 module body 中提取:
    - wire / reg / logic 声明 (net_declaration / data_declaration)
    - 连续赋值 assign (continuous_assign)
    - always 块 (always_construct)
    """

    def extract_signals(self, module_body_node, source_text: str) -> list[SignalDef]:
        """提取 wire/reg/logic 声明"""
        signals = []

        for i in range(module_body_node.child_count()):
            child = module_body_node.child(i)

            if child.kind() == "net_declaration":
                signals.extend(self._extract_net_declaration(child, source_text))

            elif child.kind() == "data_declaration":
                signals.extend(self._extract_data_declaration(child, source_text))

        return signals

    def _extract_net_declaration(self, node, source_text: str) -> list[SignalDef]:
        """从 net_declaration (wire) 提取信号"""
        var_type = "wire"
        width_range = None
        signed = False
        signals = []

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "net_type":
                # wire / wand / wor / tri 等
                for j in range(child.child_count()):
                    ntype = child.child(j)
                    if ntype.kind() in ("wire", "wand", "wor", "tri"):
                        var_type = ntype.kind()

            elif child.kind() == "data_type_or_implicit":
                # 可能的宽度 [31:0]
                for j in range(child.child_count()):
                    dt_child = child.child(j)
                    if dt_child.kind() == "implicit_data_type":
                        for k in range(dt_child.child_count()):
                            if dt_child.child(k).kind() == "packed_dimension":
                                width_range = get_node_text(dt_child.child(k), source_text)
                            elif dt_child.child(k).kind() == "signed":
                                signed = True

            elif child.kind() == "list_of_net_decl_assignments":
                decl_names = self._extract_names_from_assignments(child, source_text)
                for name in decl_names:
                    signals.append(SignalDef(
                        name=name, var_type=var_type,
                        width_range=width_range, signed=signed,
                    ))

        return signals

    def _extract_data_declaration(self, node, source_text: str) -> list[SignalDef]:
        """从 data_declaration (reg/logic) 提取信号"""
        var_type = "reg"
        width_range = None
        signed = False
        signals = []

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "data_type_or_implicit":
                for j in range(child.child_count()):
                    dt = child.child(j)
                    if dt.kind() == "data_type":
                        for k in range(dt.child_count()):
                            dtc = dt.child(k)
                            if dtc.kind() in ("reg", "logic", "integer", "real"):
                                var_type = dtc.kind()
                            elif dtc.kind() == "packed_dimension":
                                width_range = get_node_text(dtc, source_text)
                            elif dtc.kind() == "signed":
                                signed = True
                    elif dt.kind() == "implicit_data_type":
                        for k in range(dt.child_count()):
                            if dt.child(k).kind() == "packed_dimension":
                                width_range = get_node_text(dt.child(k), source_text)

            elif child.kind() == "list_of_variable_decl_assignments":
                decl_names = self._extract_names_from_assignments(child, source_text)
                for name in decl_names:
                    signals.append(SignalDef(
                        name=name, var_type=var_type,
                        width_range=width_range, signed=signed,
                    ))

        return signals

    def _extract_names_from_assignments(self, list_node, source_text: str) -> list[str]:
        """从 list_of_*_decl_assignments 中提取变量名"""
        names = []
        for i in range(list_node.child_count()):
            child = list_node.child(i)
            if child.kind() in ("net_decl_assignment", "variable_decl_assignment"):
                for j in range(child.child_count()):
                    gc = child.child(j)
                    if gc.kind() == "simple_identifier":
                        names.append(get_node_text(gc, source_text))
        return names

    # ── Assignments ──

    def extract_assignments(self, module_body_node, source_text: str, file_path: str) -> list[AssignmentInfo]:
        """提取连续赋值 continuous_assign"""
        assignments = []

        for i in range(module_body_node.child_count()):
            child = module_body_node.child(i)
            if child.kind() == "continuous_assign":
                assign = self._extract_one_assign(child, source_text, file_path)
                if assign:
                    assignments.append(assign)

        return assignments

    def _extract_one_assign(self, node, source_text: str, file_path: str) -> Optional[AssignmentInfo]:
        """提取单个 continuous_assign"""
        for i in range(node.child_count()):
            child = node.child(i)
            if child.kind() == "list_of_net_assignments":
                for j in range(child.child_count()):
                    gc = child.child(j)
                    if gc.kind() == "net_assignment":
                        lhs = ""
                        rhs = ""
                        for k in range(gc.child_count()):
                            ggc = gc.child(k)
                            if ggc.kind() == "net_lvalue":
                                lhs = get_node_text(ggc, source_text)
                            elif ggc.kind() == "expression":
                                rhs = get_node_text(ggc, source_text)
                        if lhs:
                            return AssignmentInfo(
                                lhs=lhs, rhs=rhs,
                                file_path=file_path,
                                line=get_node_line(node),
                            )
        return None

    # ── Always Blocks ──

    def extract_always_blocks(self, module_body_node, source_text: str) -> list[AlwaysBlockInfo]:
        """提取 always 块 (always_construct)"""
        blocks = []

        for i in range(module_body_node.child_count()):
            child = module_body_node.child(i)
            if child.kind() == "always_construct":
                block = self._extract_always_block(child, source_text)
                if block:
                    blocks.append(block)

        return blocks

    def _extract_always_block(self, node, source_text: str) -> Optional[AlwaysBlockInfo]:
        """提取单个 always_construct 的信息"""
        block_type = "combinational"
        sensitivity = ""
        statements = []

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "always_keyword":
                pass  # 确认是 always

            elif child.kind() == "statement":
                # 递归查找 event_control（敏感列表）
                sens = self._find_event_control(child, source_text)
                if sens:
                    sensitivity = sens
                    if "posedge" in sens or "negedge" in sens:
                        block_type = "sequential"

                # 提取 body 文本
                text = get_node_text(child, source_text)
                statements.append(text[:4096])

        return AlwaysBlockInfo(
            sensitivity_list=sensitivity,
            block_type=block_type,
            statements=statements,
        )

    def _find_event_control(self, node, source_text: str, depth: int = 0) -> str:
        """递归查找 event_control 节点"""
        if depth > 8:
            return ""
        if node.kind() == "event_control":
            return get_node_text(node, source_text)
        for i in range(node.child_count()):
            result = self._find_event_control(node.child(i), source_text, depth + 1)
            if result:
                return result
        return ""
