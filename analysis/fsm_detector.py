"""
Phase 3 — FSM 状态机检测引擎 (FSM Detector)

基于索引数据检测 Verilog 模块中的有限状态机：
- 从时序 always 块识别状态寄存器
- 从组合 always 块提取状态转移表和输出逻辑
- 自动识别编码风格（binary / one-hot / gray / symbolic）
- 区分 Mealy 与 Moore 型状态机
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from database.index_store import IndexStore
from database.models import ModuleDef, AlwaysBlockInfo, SignalDef


# ── 数据模型 ──

@dataclass
class Transition:
    """状态转移"""
    from_state: str
    to_state: str
    condition: str = ""


@dataclass
class FSM:
    """单个 FSM 信息"""
    name: str
    module_name: str
    state_register: str
    next_state_signal: Optional[str] = None
    encoding: str = "unknown"
    states: list[str] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    is_mealy: bool = False
    is_moore: bool = True

    def to_text(self, indent: int = 2) -> str:
        prefix = " " * indent
        lines = [
            f"{prefix}FSM: {self.name}",
            f"{prefix}  状态寄存器: {self.state_register}",
            f"{prefix}  次态信号: {self.next_state_signal or '(未识别)'}",
            f"{prefix}  编码: {self.encoding}",
            f"{prefix}  类型: {'Mealy' if self.is_mealy else 'Moore'}",
            f"{prefix}  状态数: {len(self.states)}",
            f"{prefix}  状态列表: {', '.join(self.states)}",
        ]
        if self.transitions:
            lines.append(f"{prefix}  状态转移表:")
            for t in self.transitions:
                cond = f" [{t.condition}]" if t.condition else ""
                lines.append(f"{prefix}    {t.from_state} → {t.to_state}{cond}")
        return "\n".join(lines)


@dataclass
class FSMResult:
    """FSM 检测结果"""
    fsm_count: int = 0
    fsms: list[FSM] = field(default_factory=list)


# ── FSM 检测器 ──

class FSMDetector:
    """有限状态机检测器"""

    _CLOCK_PATTERNS = {"clk", "clock", "clkp", "clkn", "sys_clk", "ref_clk", "mclk", "pclk", "hclk", "aclk"}

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store

    def detect_fsms(self, module_name: str) -> FSMResult:
        """
        检测指定模块中的所有有限状态机

        算法：
        1. 找出所有时序 always 块（posedge 敏感）
        2. 从时序块推断状态寄存器（被赋值且带有 next_state 信号的寄存器）
        3. 在组合 always 块中查找 case(state) 语句
        4. 提取状态名、转移条件、输出逻辑
        5. 检测编码风格，区分 Mealy/Moore
        """
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在于索引中")

        sequential_blocks = self._find_sequential_blocks(mod)
        combinational_blocks = self._find_combinational_blocks(mod)

        # 从时序块推断状态寄存器候选
        state_reg_candidates = self._find_state_reg_candidates(
            mod, sequential_blocks
        )

        fsms: list[FSM] = []
        for state_reg in state_reg_candidates:
            fsm = self._build_fsm(mod, state_reg, sequential_blocks, combinational_blocks)
            if fsm:
                fsms.append(fsm)

        return FSMResult(fsm_count=len(fsms), fsms=fsms)

    # ── 辅助方法 ──

    def _find_sequential_blocks(self, mod: ModuleDef) -> list[AlwaysBlockInfo]:
        """找出所有时序逻辑 always 块"""
        result = []
        for ab in mod.always_blocks:
            if ab.block_type == "sequential":
                result.append(ab)
            else:
                sens = ab.sensitivity_list.lower()
                if "posedge" in sens or "negedge" in sens:
                    result.append(ab)
        return result

    def _find_combinational_blocks(self, mod: ModuleDef) -> list[AlwaysBlockInfo]:
        """找出所有组合逻辑 always 块"""
        result = []
        for ab in mod.always_blocks:
            if ab.block_type == "combinational":
                result.append(ab)
            else:
                sens = ab.sensitivity_list.lower().replace(" ", "")
                if sens in ("*", "(*)", "@*", "@(*)"):
                    result.append(ab)
        return result

    def _get_block_text(self, block: AlwaysBlockInfo) -> str:
        """获取 always 块的完整文本"""
        parts = [s for s in block.statements if s.strip()]
        if not parts:
            return ""
        return "\n".join(parts)

    def _find_state_reg_candidates(
        self,
        mod: ModuleDef,
        sequential_blocks: list[AlwaysBlockInfo],
    ) -> list[str]:
        """
        从时序 always 块推断状态寄存器候选

        规则：
        1. 在时序块中找非 reset 赋值的寄存器
        2. 如果 reg 被赋值为 next_reg 模式，则 reg 是状态寄存器
        3. 如果 reg 在组合块中作为 case 表达式，也是候选
        """
        candidates: set[str] = set()

        # 收集组合块中的 case 表达式
        case_exprs_in_comb = self._find_all_case_exprs_in_blocks(
            self._find_combinational_blocks(mod)
        )

        for seq_block in sequential_blocks:
            text = self._get_block_text(seq_block)
            if not text:
                continue

            # 找 <= 赋值
            for assign in re.finditer(
                r'(\w+)\s*<=\s*(\w+)', text
            ):
                lhs = assign.group(1)
                rhs = assign.group(2)
                # state <= next_state 模式
                if rhs.startswith("next_"):
                    candidates.add(lhs)
                # 或者 state 在组合块中作为 case 表达式
                if lhs in case_exprs_in_comb:
                    candidates.add(lhs)

            # 如果没找到 next_state 模式，收集所有 <= 赋值的 LHS
            # 看它们是否在组合块中作为 case 表达式
            for lhs in re.findall(r'(\w+)\s*<=', text):
                if lhs in case_exprs_in_comb:
                    candidates.add(lhs)

        return list(candidates)

    def _find_all_case_exprs_in_blocks(
        self, blocks: list[AlwaysBlockInfo]
    ) -> set[str]:
        """从组合 always 块中提取所有 case 表达式"""
        exprs: set[str] = set()
        for block in blocks:
            text = self._get_block_text(block)
            if not text:
                continue
            for m in re.finditer(r'\bcases?\s*\(\s*(\w+)\s*\)', text):
                exprs.add(m.group(1))
        return exprs

    def _find_case_in_text(self, text: str) -> Optional[re.Match]:
        """在文本中查找 case 语句，返回 match 对象 (expr=group1, body=group2)"""
        pattern = r'\bcases?\s*\(\s*(.*?)\s*\)\s*(.*?)(?=\bendcase\b)'
        return re.search(pattern, text, re.DOTALL)

    def _extract_case_items(self, case_body: str) -> dict[str, str]:
        """从 case body 中提取 case items: {state_name: action_text}"""
        items: dict[str, str] = {}
        prev_end = 0
        for m in re.finditer(
            r'(?P<label>\w+)\s*:\s*(?P<action>.*?)(?=\n\s*\w+\s*:|\n\s*default\s*:|\bendcase\b)',
            case_body, re.DOTALL
        ):
            label = m.group("label")
            if label.lower() == "default":
                continue
            action = m.group("action").strip()
            items[label] = action
        return items

    def _extract_transitions(
        self, state_items: dict[str, str], state_names: list[str]
    ) -> list[Transition]:
        """从 case items 提取状态转移表"""
        transitions: list[Transition] = []
        for from_state, action in state_items.items():
            action_clean = action.strip(" ;\n\t")
            # 找 next_state_xxx = 的赋值
            for m in re.finditer(r'\bnext_\w+\s*=\s*(.+?)(?:;|$)', action_clean):
                rhs = m.group(1).strip()
                ternary = re.match(r'\s*(.*?)\s*\?\s*(\w+)\s*:\s*(\w+)\s*', rhs)
                if ternary:
                    cond = ternary.group(1).strip()
                    to_if_true = ternary.group(2)
                    to_if_false = ternary.group(3)
                    if to_if_true in state_names:
                        transitions.append(Transition(
                            from_state=from_state,
                            to_state=to_if_true,
                            condition=cond,
                        ))
                    if to_if_false in state_names:
                        transitions.append(Transition(
                            from_state=from_state,
                            to_state=to_if_false,
                            condition=f"!{cond}",
                        ))
                elif rhs in state_names:
                    transitions.append(Transition(
                        from_state=from_state,
                        to_state=rhs,
                    ))
                else:
                    words = rhs.split()
                    if len(words) == 1 and words[0] in state_names:
                        transitions.append(Transition(
                            from_state=from_state,
                            to_state=words[0],
                        ))
            # 如果没有 next_state 赋值，检查直接 state <= xxx
            if not any(t.from_state == from_state for t in transitions):
                for m in re.finditer(r'\bstate\s*<=\s*(\w+)', action_clean):
                    to_state = m.group(1)
                    if to_state in state_names:
                        transitions.append(Transition(
                            from_state=from_state,
                            to_state=to_state,
                        ))
        return transitions

    def _detect_encoding(
        self, state_names: list[str], state_signal: Optional[SignalDef]
    ) -> str:
        """检测状态机编码风格"""
        n = len(state_names)
        if n <= 1:
            return "unknown"

        has_bit_patterns = any(
            re.match(r"^[01'xbBzZ?]+$", s) or re.match(r"^\d+'[bdh]", s.lower())
            for s in state_names
        )

        if has_bit_patterns:
            if state_signal and state_signal.width_range:
                try:
                    w = int(state_signal.width_range)
                    if w > 1:
                        if n >= w - 1 and n <= w:
                            return "one_hot"
                        if n >= 2 and n <= 2**w:
                            return "binary"
                except (ValueError, TypeError):
                    pass
            if any("'b" in s for s in state_names):
                return "binary"
            return "binary"

        has_numeric_suffix = any(re.search(r'\d+$', s) for s in state_names)
        if has_numeric_suffix:
            return "gray"

        return "symbolic"

    def _detect_mealy(
        self,
        mod: ModuleDef,
        comb_blocks: list[AlwaysBlockInfo],
        state_register: str,
    ) -> bool:
        """
        检测是否为 Mealy 状态机

        Mealy: 输出依赖状态 + 输入
        Moore: 输出仅依赖状态
        """
        for block in comb_blocks:
            text = self._get_block_text(block)
            if not text:
                continue
            case_m = self._find_case_in_text(text)
            if not case_m:
                continue
            case_expr = case_m.group(1).strip()
            if state_register not in case_expr:
                continue
            case_body = case_m.group(2)

            # 在 case 内部的赋值 RHS 中查找输入信号
            for item_match in re.finditer(r'\b(\w+)\s*=\s*(.+?);', case_body):
                rhs = item_match.group(2)
                if state_register not in rhs:
                    for sig in mod.signals:
                        if sig.name in rhs and sig.name != state_register:
                            return True
        return False

    def _build_fsm(
        self,
        mod: ModuleDef,
        state_register: str,
        sequential_blocks: list[AlwaysBlockInfo],
        combinational_blocks: list[AlwaysBlockInfo],
    ) -> Optional[FSM]:
        """构建单个 FSM 信息"""
        state_signal = self._find_signal(mod, state_register)

        # 在所有组合块中找 case(state_register) 的语句
        next_state_block_body: str | None = None
        output_block_bodies: list[str] = []
        next_state_candidates: set[str] = set()

        for comb_block in combinational_blocks:
            text = self._get_block_text(comb_block)
            if not text:
                continue
            case_m = self._find_case_in_text(text)
            if not case_m:
                continue
            expr = case_m.group(1).strip()
            if state_register not in expr:
                continue

            # 判断此块是 next_state 逻辑还是输出逻辑
            has_next_state = bool(re.search(r'\bnext_\w+\s*=', text))
            if has_next_state:
                next_state_block_body = case_m.group(2)
                for m in re.finditer(r'\b(\w+)\s*=', text):
                    sig_name = m.group(1)
                    if sig_name.startswith("next_") or sig_name == f"next_{state_register}":
                        next_state_candidates.add(sig_name)
            else:
                output_block_bodies.append(case_m.group(2))

        # 优先使用 next_state 逻辑块
        case_body = next_state_block_body
        if not case_body:
            case_body = output_block_bodies[0] if output_block_bodies else None

        if not case_body:
            return None

        items = self._extract_case_items(case_body)
        if not items:
            return None

        state_names = list(items.keys())
        encoding = self._detect_encoding(state_names, state_signal)
        transitions = self._extract_transitions(items, state_names)
        is_mealy = self._detect_mealy(mod, combinational_blocks, state_register)
        next_state_signal = next(
            (s for s in next_state_candidates),
            f"next_{state_register}" if state_register else None,
        )
        fsm_name = f"{state_register}_fsm"

        return FSM(
            name=fsm_name,
            module_name=mod.name,
            state_register=state_register,
            next_state_signal=next_state_signal,
            encoding=encoding,
            states=state_names,
            transitions=transitions,
            is_mealy=is_mealy,
            is_moore=not is_mealy,
        )

    def _find_signal(self, mod: ModuleDef, name: str) -> Optional[SignalDef]:
        """在模块中查找信号定义"""
        for sig in mod.signals:
            if sig.name == name:
                return sig
        return None


# ── 便捷函数 ──

def detect_fsms_in_module(store: IndexStore, module_name: str) -> FSMResult:
    """便捷调用"""
    detector = FSMDetector(store)
    return detector.detect_fsms(module_name)
