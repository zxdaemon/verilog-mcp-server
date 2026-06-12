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

from ..database.index_store import IndexStore
from ..database.models import ModuleDef, AlwaysBlockInfo, SignalDef
from .signal_classifier import SignalClassifier


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

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store
        self._classifier = SignalClassifier()

    def detect_fsms(self, module_name: str) -> FSMResult:
        """
        检测指定模块中的所有有限状态机

        合并两种检测方法：
        1. case+next_state 模式检测（传统方法）
        2. 寄存器+分支模式检测（支持 one-hot、if-else 链）

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

        # 方法1: case+next_state 模式
        state_reg_candidates = self._find_state_reg_candidates(
            mod, sequential_blocks
        )

        fsms: list[FSM] = []
        seen_regs: set[str] = set()
        for state_reg in state_reg_candidates:
            fsm = self._build_fsm(mod, state_reg, sequential_blocks, combinational_blocks)
            if fsm:
                fsms.append(fsm)
                seen_regs.add(state_reg)

        # 方法2: 寄存器+分支模式（非 case）
        register_fsms = self._detect_fsm_by_register(mod)
        for fsm in register_fsms:
            if fsm.state_register not in seen_regs:
                fsms.append(fsm)
                seen_regs.add(fsm.state_register)

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
        """从时序 always 块推断状态寄存器候选

        使用 SignalDef.drivers 找到时序块中赋值的寄存器，
        再用 SignalDef.loads 检查它们是否在组合块中作为 case 表达式。
        """
        combinational_blocks = self._find_combinational_blocks(mod)
        comb_block_texts = [self._get_block_text(b) for b in combinational_blocks
                           if self._get_block_text(b)]

        # 收集组合块中的 case/casez/casex 表达式
        case_exprs: set[str] = set()
        for text in comb_block_texts:
            for m in re.finditer(r'\bcase[zx]?\s*\(\s*(\w+)\s*\)', text):
                case_exprs.add(m.group(1))

        candidates: set[str] = set()

        for sig in mod.signals:
            if not sig.drivers:
                continue
            for drv in sig.drivers:
                if drv.type == "always_block":
                    # 被时序块驱动的信号 + 在组合块中作为 case 表达式 → 状态寄存器候选
                    if sig.name in case_exprs:
                        candidates.add(sig.name)
                    # 同时检查 RHS 是否有 next_ 前缀（兼容旧代码风格）
                    if "next_" in drv.source:
                        candidates.add(sig.name)

        return list(candidates)

    def _detect_fsm_by_register(
        self, mod: ModuleDef
    ) -> list[FSM]:
        """基于寄存器识别的 FSM 检测（不依赖 case 语句）

        检测 one-hot 直接赋值、二进制编码 if-else 链等模式。

        算法：
        1. 扫描时序 always 块，找到被非复位条件赋值的寄存器
        2. 检查该寄存器是否在组合逻辑中被读取（条件判断或赋值 RHS）
        3. 检查组合逻辑是否有分支行为（if-else 或 case）
        4. 从赋值中提取状态值，排除计数器/移位寄存器模式
        """
        sequential_blocks = self._find_sequential_blocks(mod)
        combinational_blocks = self._find_combinational_blocks(mod)

        if not sequential_blocks:
            return []

        # Allow FSMs with only sequential blocks (e.g. binary encoded in always_ff)

        # 步骤1: 找到时序块中赋值的寄存器
        seq_assigned_regs: set[str] = set()
        for block in sequential_blocks:
            text = self._get_block_text(block)
            if not text:
                continue
            # 匹配 reg <= value 模式，过滤复位赋值
            for m in re.finditer(
                r'\b(\w+)\s*<\s*=\s*([^;\n]+)',
                text
            ):
                reg_name = m.group(1)
                # 排除复位赋值：检查整行是否包含 rst 或赋值为 0
                line_start = text.rfind('\n', 0, m.start()) + 1
                line = text[line_start:m.end()]
                line_lower = line.lower()
                if 'rst' in line_lower:
                    continue
                if re.search(r"\b0+'?[bdh]?0+\b", line):
                    continue
                seq_assigned_regs.add(reg_name)

        # 步骤2: 检查寄存器在组合逻辑或时序逻辑中的读取
        fsms: list[FSM] = []
        for reg_name in seq_assigned_regs:
            # 查找组合块中是否读取该寄存器
            is_read_in_comb = False
            branch_states: set[str] = set()

            # 先检查组合块
            for block in combinational_blocks:
                text = self._get_block_text(block)
                if not text:
                    continue
                # 检查是否在 if/else if 条件中读取
                if re.search(rf'\bif\s*\([^)]*\b{re.escape(reg_name)}\b', text):
                    is_read_in_comb = True
                    # 提取分支中的赋值状态值
                    for m in re.finditer(
                        rf'{re.escape(reg_name)}\s*<\s*=\s*([^;\n]+)',
                        text
                    ):
                        state_val = m.group(1).strip()
                        if self._is_valid_state_value(state_val):
                            branch_states.add(state_val)
                    for m in re.finditer(
                        rf'{re.escape(reg_name)}\s*=\s*([^;\n]+)',
                        text
                    ):
                        state_val = m.group(1).strip()
                        if self._is_valid_state_value(state_val):
                            branch_states.add(state_val)

            # 如果没有组合块，也检查时序块中的分支行为
            if not is_read_in_comb:
                for block in sequential_blocks:
                    text = self._get_block_text(block)
                    if not text:
                        continue
                    # 检查时序块中是否有基于该寄存器的 if-else 分支
                    if re.search(rf'\bif\s*\([^)]*\b{re.escape(reg_name)}\b', text):
                        is_read_in_comb = True
                        for m in re.finditer(
                            rf'{re.escape(reg_name)}\s*<\s*=\s*([^;\n]+)',
                            text
                        ):
                            line_start = text.rfind('\n', 0, m.start()) + 1
                            line = text[line_start:m.end()]
                            if 'rst' not in line.lower():
                                state_val = m.group(1).strip()
                                if self._is_valid_state_value(state_val):
                                    branch_states.add(state_val)

            # 步骤3: 过滤计数器和移位寄存器
            if is_read_in_comb and self._is_fsm_pattern(reg_name, branch_states):
                # 步骤4: 构建 FSM
                blocks_to_search = combinational_blocks if combinational_blocks else sequential_blocks
                fsm = self._build_fsm_from_register(
                    mod, reg_name, blocks_to_search, branch_states
                )
                if fsm and len(fsm.states) >= 2:
                    fsms.append(fsm)

        return fsms

    def _is_valid_state_value(self, value: str) -> bool:
        """检查赋值右侧是否为有效的状态值"""
        value = value.strip()
        # 排除算术表达式（计数器模式）
        if re.search(r'[\+\-\*\/]', value):
            return False
        # 排除移位操作（移位寄存器）
        if re.search(r'<<|>>', value):
            return False
        # 排除变量引用（非立即数状态）
        if re.match(r'^[a-zA-Z_]\w*$', value):
            return True  # 符号状态名
        # 数字常量
        if re.match(r"^\d+'[bdho][\dabcdefxz?]+$", value, re.I):
            return True
        # 二进制/十六进制字面量
        if re.match(r"^[01'xbz?]+$", value, re.I):
            return True
        return False

    def _is_fsm_pattern(self, reg_name: str, branch_states: set[str]) -> bool:
        """排除计数器和移位寄存器模式"""
        if len(branch_states) < 2:
            return False
        # 检查是否所有状态值都是连续整数（计数器特征）
        numeric_states = []
        for s in branch_states:
            m = re.match(r"(\d+)'[bdho]([\dabcdef]+)$", s, re.I)
            if m:
                try:
                    base = {"b": 2, "d": 10, "h": 16, "o": 8}.get(m.group(1).lower(), 10)
                    numeric_states.append(int(m.group(2), base))
                except ValueError:
                    pass
        if len(numeric_states) == len(branch_states) and len(numeric_states) >= 2:
            numeric_states.sort()
            # 如果是连续整数，可能是计数器
            is_consecutive = all(
                numeric_states[i] + 1 == numeric_states[i + 1]
                for i in range(len(numeric_states) - 1)
            )
            if is_consecutive and len(numeric_states) > 4:
                return False
        return True

    def _build_fsm_from_register(
        self,
        mod: ModuleDef,
        reg_name: str,
        combinational_blocks: list[AlwaysBlockInfo],
        branch_states: set[str],
    ) -> Optional[FSM]:
        """从寄存器和分支状态构建 FSM"""
        state_names = sorted(branch_states)
        transitions: list[Transition] = []

        # 从组合块中提取转移条件
        for block in combinational_blocks:
            text = self._get_block_text(block)
            if not text:
                continue
            # 查找 if 分支中的状态赋值
            for m in re.finditer(
                rf'\bif\s*\(([^)]+)\)[^;]*?{re.escape(reg_name)}\s*<\s*=\s*([^;\n]+)',
                text, re.DOTALL
            ):
                cond = m.group(1).strip()
                to_state = m.group(2).strip()
                if to_state in state_names:
                    transitions.append(Transition(
                        from_state="", to_state=to_state, condition=cond,
                    ))
            # 查找 else 分支中的状态赋值
            for m in re.finditer(
                rf'{re.escape(reg_name)}\s*<\s*=\s*([^;\n]+)',
                text
            ):
                to_state = m.group(1).strip()
                if to_state in state_names:
                    transitions.append(Transition(
                        from_state="", to_state=to_state, condition="",
                    ))

        # 检测编码风格
        encoding = self._detect_encoding_from_states(state_names)

        # 检测 Mealy/Moore
        is_mealy = False
        for block in combinational_blocks:
            text = self._get_block_text(block)
            if text and reg_name in text:
                # 检查是否有输出赋值与状态相关
                for m in re.finditer(r'\b(\w+)\s*=\s*([^;\n]+)', text):
                    rhs = m.group(2)
                    if reg_name in rhs:
                        is_mealy = True
                        break

        return FSM(
            name=f"{reg_name}_fsm",
            module_name=mod.name,
            state_register=reg_name,
            next_state_signal=f"next_{reg_name}",
            encoding=encoding,
            states=state_names,
            transitions=transitions,
            is_mealy=is_mealy,
            is_moore=not is_mealy,
        )

    def _detect_encoding_from_states(self, state_names: list[str]) -> str:
        """从状态值检测编码风格"""
        if not state_names:
            return "unknown"
        # 检查 one-hot 特征
        one_hot_count = 0
        for s in state_names:
            m = re.match(r"(\d+)'b([01]+)$", s, re.I)
            if m:
                bits = m.group(2)
                if bits.count('1') == 1:
                    one_hot_count += 1
        if one_hot_count == len(state_names) and len(state_names) >= 2:
            return "one_hot"
        # 检查二进制编码
        binary_count = 0
        for s in state_names:
            if re.match(r"^\d+'[bdh][\dabcdef]+$", s, re.I):
                binary_count += 1
        if binary_count == len(state_names):
            return "binary"
        return "symbolic"

    def _find_all_case_exprs_in_blocks(
        self, blocks: list[AlwaysBlockInfo]
    ) -> set[str]:
        """从组合 always 块中提取所有 case/casez/casex 表达式"""
        exprs: set[str] = set()
        for block in blocks:
            text = self._get_block_text(block)
            if not text:
                continue
            for m in re.finditer(r'\bcase[zx]?\s*\(\s*(\w+)\s*\)', text):
                exprs.add(m.group(1))
        return exprs

    def _find_case_in_text(self, text: str) -> Optional[re.Match]:
        """在文本中查找 case/casez/casex 语句，返回 match 对象 (expr=group1, body=group2)"""
        pattern = r'\bcase[zx]?\s*\(\s*(.*?)\s*\)\s*(.*?)(?=\bendcase\b)'
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
        """构建单个 FSM 信息

        优先使用 SignalDef.loads 定位 case 块，回退到文本搜索。
        """
        state_signal = self._find_signal(mod, state_register)

        next_state_block_body: str | None = None
        output_block_bodies: list[str] = []
        next_state_candidates: set[str] = set()

        # 如果 loads 中有 case_statement 引用，使用它定位组合块
        case_block_texts: set[str] = set()
        if state_signal and state_signal.loads:
            for ld in state_signal.loads:
                if ld.type == "always_block" and "case" in ld.target.lower():
                    for comb_block in combinational_blocks:
                        text = self._get_block_text(comb_block)
                        if text and state_register in text and "case" in text:
                            case_block_texts.add(text)

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

            has_next_state = bool(re.search(r'\bnext_\w+\s*=', text))
            if has_next_state:
                next_state_block_body = case_m.group(2)
                for m in re.finditer(r'\b(\w+)\s*=', text):
                    sig_name = m.group(1)
                    if sig_name.startswith("next_") or sig_name == f"next_{state_register}":
                        next_state_candidates.add(sig_name)
            else:
                output_block_bodies.append(case_m.group(2))

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
