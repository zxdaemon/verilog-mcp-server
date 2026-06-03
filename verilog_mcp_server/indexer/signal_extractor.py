"""
信号提取器 — 提取 wire/reg/logic 声明、assign、always
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line, iter_module_body_deep
from ..database.models import SignalDef, AlwaysBlockInfo, AssignmentInfo, DriverInfo, LoadInfo

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

        for child in iter_module_body_deep(module_body_node):
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

        for child in iter_module_body_deep(module_body_node):
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

    # ── Driver / Load Extraction ──

    def extract_drivers_and_loads(self, module_body_node, source_text: str,
                                   file_path: str) -> tuple[dict[str, list[DriverInfo]], dict[str, list[LoadInfo]]]:
        """提取模块体中所有信号的驱动源和负载端

        遍历 module_body 中的 always 块和 continuous_assign 节点，
        从 AST 中提取驱动/负载关系。

        Returns:
            (drivers_map, loads_map): 信号名 → 驱动/负载列表
        """
        drivers_map: dict[str, list[DriverInfo]] = {}
        loads_map: dict[str, list[LoadInfo]] = {}

        for child in iter_module_body_deep(module_body_node):
            kind = child.kind()
            if kind == "continuous_assign":
                self._extract_assign_drivers_loads(child, source_text, file_path,
                                                   drivers_map, loads_map)
            elif kind == "always_construct":
                self._extract_always_drivers_loads(child, source_text, file_path,
                                                   drivers_map, loads_map)

        return drivers_map, loads_map

    def _extract_assign_drivers_loads(self, node, source_text: str, file_path: str,
                                       drivers_map: dict, loads_map: dict):
        """从 continuous_assign 提取驱动和负载"""
        from ..analysis.expr_walker import extract_signal_refs
        line = get_node_line(node)

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
                            driver_sigs = extract_signal_refs(lhs)
                            for sig in driver_sigs:
                                drv = DriverInfo(
                                    type="assign",
                                    source=f"assign {lhs} = {rhs}",
                                    file_path=file_path, line=line,
                                )
                                drivers_map.setdefault(sig, []).append(drv)
                            if rhs:
                                for sig in extract_signal_refs(rhs):
                                    ld = LoadInfo(
                                        type="assign",
                                        target=f"assign {lhs} = {rhs}",
                                        file_path=file_path, line=line,
                                    )
                                    loads_map.setdefault(sig, []).append(ld)

    def _extract_always_drivers_loads(self, node, source_text: str, file_path: str,
                                       drivers_map: dict, loads_map: dict):
        """从 always 块（含 always_comb/ff/latch）提取驱动和负载"""
        from ..analysis.expr_walker import extract_signal_refs
        block_line = get_node_line(node)

        def _has_for_ancestor(n, depth: int = 0) -> bool:
            if depth > 10:
                return False
            if n.kind() == "for_statement":
                return True
            p = getattr(n, 'parent', None)
            if p is not None:
                return _has_for_ancestor(p, depth + 1)
            return False

        def _walk_assignments(n, depth: int = 0):
            if depth > 40:
                return
            kind = n.kind()
            if kind in ("nonblocking_assignment", "blocking_assignment"):
                lhs = ""
                rhs = ""
                for idx in range(n.child_count()):
                    c = n.child(idx)
                    if c.kind() == "net_lvalue" or (c.kind() == "simple_identifier" and not lhs):
                        lhs = get_node_text(c, source_text)
                    elif c.kind() == "expression":
                        rhs = get_node_text(c, source_text)
                    elif c.kind() == "simple_identifier" and not lhs:
                        lhs = get_node_text(c, source_text)

                if lhs and not _has_for_ancestor(n):
                    lhs_sigs = extract_signal_refs(lhs)
                    for sig in lhs_sigs:
                        drv = DriverInfo(
                            type="always_block",
                            source=f"always block ({kind})",
                            file_path=file_path, line=get_node_line(n),
                        )
                        drivers_map.setdefault(sig, []).append(drv)
                    if rhs:
                        for sig in extract_signal_refs(rhs):
                            ld = LoadInfo(
                                type="always_block",
                                target=f"always block RHS ({kind})",
                                file_path=file_path, line=get_node_line(n),
                            )
                            loads_map.setdefault(sig, []).append(ld)

            elif kind == "if_statement":
                for idx in range(n.child_count()):
                    c = n.child(idx)
                    if c.kind() in ("expression", "parenthesized_expression"):
                        expr_text = get_node_text(c, source_text)
                        for sig in extract_signal_refs(expr_text):
                            ld = LoadInfo(
                                type="always_block",
                                target="if condition",
                                file_path=file_path, line=get_node_line(n),
                            )
                            loads_map.setdefault(sig, []).append(ld)
                        break

            elif kind in ("case_statement", "casez_statement", "casex_statement"):
                for idx in range(n.child_count()):
                    c = n.child(idx)
                    if c.kind() in ("expression", "parenthesized_expression"):
                        expr_text = get_node_text(c, source_text)
                        for sig in extract_signal_refs(expr_text):
                            ld = LoadInfo(
                                type="always_block",
                                target=f"{kind} expression",
                                file_path=file_path, line=get_node_line(n),
                            )
                            loads_map.setdefault(sig, []).append(ld)
                        break

            elif kind == "event_control":
                expr_text = get_node_text(n, source_text)
                for sig in extract_signal_refs(expr_text):
                    ld = LoadInfo(
                        type="always_block",
                        target=f"event_control: {expr_text[:60]}",
                        file_path=file_path, line=get_node_line(n),
                    )
                    loads_map.setdefault(sig, []).append(ld)

            for idx in range(n.child_count()):
                _walk_assignments(n.child(idx), depth + 1)

        _walk_assignments(node)

    def extract_always_blocks(self, module_body_node, source_text: str) -> list[AlwaysBlockInfo]:
        """提取 always 块 (always_construct，含 always_comb/ff/latch)"""
        blocks = []

        for child in iter_module_body_deep(module_body_node):
            if child.kind() == "always_construct":
                block = self._extract_always_block(child, source_text)
                if block:
                    blocks.append(block)

        return blocks

    def _extract_always_block(self, node, source_text: str) -> Optional[AlwaysBlockInfo]:
        """提取单个 always_construct（含 always_comb/always_ff/always_latch）"""
        block_type = "combinational"
        sensitivity = ""
        statements = []
        sv_keyword = ""

        for i in range(node.child_count()):
            child = node.child(i)

            if child.kind() == "always_keyword":
                sv_keyword = get_node_text(child, source_text).strip()

            elif child.kind() == "statement":
                sens = self._find_event_control(child, source_text)
                if sens:
                    sensitivity = sens

                text = get_node_text(child, source_text)
                statements.append(text[:4096])

        # 根据 SystemVerilog 关键字确定类型
        if sv_keyword == "always_comb":
            block_type = "combinational"
            if not sensitivity:
                sensitivity = "@*"
        elif sv_keyword == "always_ff":
            block_type = "sequential"
        elif sv_keyword == "always_latch":
            block_type = "latch"
            if not sensitivity:
                sensitivity = "@*"
        elif sensitivity:
            if "posedge" in sensitivity or "negedge" in sensitivity:
                block_type = "sequential"

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
