"""
Phase 3 — Always 块分类引擎 (Always Block Classifier)

对模块中所有 always 块进行分类：
- sequential: 时序逻辑（posedge/negedge 时钟敏感）
- combinational: 组合逻辑（@* 或 @(*) 敏感）
- latch: 锁存器（posedge/negedge 的非时钟信号敏感）

并提取每个块的赋值信号和读取信号。
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from database.index_store import IndexStore
from database.models import ModuleDef, AlwaysBlockInfo


@dataclass
class AlwaysBlockDetail:
    """Always 块详细信息"""
    sensitivity: str              # 敏感列表原文
    type: str                     # "sequential" / "combinational" / "latch"
    clock: str | None             # 时钟信号（时序块）
    signals_assigned: list[str]   # 块中赋值的信号
    signals_read: list[str]       # 块中读取的信号

    def to_dict(self) -> dict:
        return {
            "sensitivity": self.sensitivity,
            "type": self.type,
            "clock": self.clock,
            "signals_assigned": self.signals_assigned,
            "signals_read": self.signals_read,
        }


@dataclass
class AlwaysClassification:
    """Always 块分类结果"""
    module_name: str
    sequential_blocks: list[AlwaysBlockDetail]
    combinational_blocks: list[AlwaysBlockDetail]
    latch_blocks: list[AlwaysBlockDetail]

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "sequential_blocks": [b.to_dict() for b in self.sequential_blocks],
            "combinational_blocks": [b.to_dict() for b in self.combinational_blocks],
            "latch_blocks": [b.to_dict() for b in self.latch_blocks],
        }


class AlwaysClassifier:
    """Always 块分类器"""

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store

    # ── public API ──

    def classify(self, module_name: str) -> AlwaysClassification:
        """
        对指定模块的所有 always 块进行分类

        Args:
            module_name: 模块名

        Returns:
            AlwaysClassification

        Raises:
            ValueError: 如果模块不存在
        """
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在于索引中")

        sequential: list[AlwaysBlockDetail] = []
        combinational: list[AlwaysBlockDetail] = []
        latches: list[AlwaysBlockDetail] = []

        for ab in mod.always_blocks:
            sens = ab.sensitivity_list
            block_text = "\n".join(ab.statements)

            # 分类
            block_type = self._classify_block(ab, mod)
            clock = self._extract_clock(sens, mod)
            assigned = self._extract_assigned_signals(block_text)
            read = self._extract_read_signals(block_text, assigned)

            info = AlwaysBlockDetail(
                sensitivity=sens,
                type=block_type,
                clock=clock,
                signals_assigned=assigned,
                signals_read=read,
            )

            if block_type == "sequential":
                sequential.append(info)
            elif block_type == "combinational":
                combinational.append(info)
            elif block_type == "latch":
                latches.append(info)

        return AlwaysClassification(
            module_name=module_name,
            sequential_blocks=sequential,
            combinational_blocks=combinational,
            latch_blocks=latches,
        )

    # ── 分类逻辑 ──

    def _classify_block(self, ab: AlwaysBlockInfo, mod: ModuleDef) -> str:
        """
        判断 always 块的类型

        Rules:
        1. sequential: 敏感列表包含 posedge/negedge + 信号是时钟
        2. combinational: 敏感列表是 @* 或 @(*)
        3. latch: 敏感列表是 posedge/negedge 但信号不是时钟

        如果已有 block_type 标记，优先使用
        """
        sens_lower = ab.sensitivity_list.lower().replace(" ", "")
        sens_original = ab.sensitivity_list.lower()

        # 显式标记优先
        if ab.block_type == "sequential":
            return "sequential"
        if ab.block_type == "combinational":
            return "combinational"
        if ab.block_type == "latch":
            return "latch"

        # 检查组合逻辑
        if sens_lower in ("*", "(*)", "@*", "@(*)", "always_comb"):
            return "combinational"

        # 检查时钟敏感
        if "posedge" in sens_original or "negedge" in sens_original:
            # 提取敏感列表中的信号
            signals = re.findall(
                r'(?:posedge|negedge)\s+([a-zA-Z_][a-zA-Z0-9_$.\[\]]*)',
                sens_original,
                re.IGNORECASE,
            )
            # 检查是否有时钟信号
            clocks = [s for s in signals if self._is_clock_signal(s, mod)]
            if clocks:
                return "sequential"
            else:
                # 敏感列表中有 posedge/negedge 但无时钟 → 可能是 latch
                return "latch"

        # 默认：可能是组合逻辑（没有 posedge/negedge）
        if "posedge" not in sens_original and "negedge" not in sens_original:
            return "combinational"

        return "combinational"

    def _is_clock_signal(self, signal_name: str, mod: ModuleDef) -> bool:
        """
        判断信号是否为时钟

        启发式规则：
        - 信号名包含 'clk' 或 'clock'（不区分大小写）
        - 信号是 input 端口
        - 出现在多个 always 块的敏感列表中
        """
        name_lower = signal_name.lower()

        # 命名启发
        if 'clk' in name_lower or 'clock' in name_lower:
            return True

        # 检查端口
        for p in mod.ports:
            if p.name == signal_name and p.direction == "input":
                return True

        # 检查是否出现在多个 always 块的敏感列表中
        count = 0
        for ab in mod.always_blocks:
            if signal_name.lower() in ab.sensitivity_list.lower():
                count += 1
        if count >= 2:
            return True

        return False

    def _extract_clock(self, sensitivity: str, mod: ModuleDef) -> Optional[str]:
        """从敏感列表中提取时钟信号"""
        signals = re.findall(
            r'(?:posedge|negedge)\s+([a-zA-Z_][a-zA-Z0-9_$.\[\]]*)',
            sensitivity,
            re.IGNORECASE,
        )
        for sig in signals:
            if self._is_clock_signal(sig, mod):
                return sig
        return None

    # ── 赋值和读取信号提取 ──

    def _extract_assigned_signals(self, block_text: str) -> list[str]:
        """
        提取 always 块中被赋值的信号（LHS of <= or =）

        过滤掉：
        - for 循环变量
        - case 表达式
        - 关键字
        """
        signals: set[str] = set()

        # 去掉 case 语句区域（其内部的赋值可能干扰）
        text = re.sub(
            r'case\s*\([^)]+\)\s*.*?\s*endcase',
            '',
            block_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # 匹配 non-blocking: signal <= expr
        for m in re.finditer(
            r'^\s*(?P<sig>[a-zA-Z_][a-zA-Z0-9_$.\[\]]*)\s*<=\s*',
            text,
            re.MULTILINE,
        ):
            sig = m.group("sig").strip()
            if not self._is_keyword(sig):
                signals.add(sig)

        # 匹配 blocking: signal = expr
        for m in re.finditer(
            r'^\s*(?P<sig>[a-zA-Z_][a-zA-Z0-9_$.\[\]]*)\s*=\s*',
            text,
            re.MULTILINE,
        ):
            sig = m.group("sig").strip()
            if not self._is_keyword(sig):
                signals.add(sig)

        return sorted(signals)

    def _extract_read_signals(self, block_text: str, assigned: list[str]) -> list[str]:
        """
        提取 always 块中读取的信号（RHS 中的信号）

        排除：
        - LHS 中已赋值的信号
        - 关键字
        - 数字常量
        """
        signals: set[str] = set()

        # 匹配 RHS 中的标识符
        # 查找 = 或 <= 右侧的单词标识符
        for m in re.finditer(
            r'(?:<=|=)\s*(?P<rhs>[^;]+)',
            block_text,
        ):
            rhs = m.group("rhs").strip()
            # 提取 RHS 中的所有标识符
            for id_match in re.finditer(
                r'(?P<name>[a-zA-Z_][a-zA-Z0-9_$.\[\]]*)',
                rhs,
            ):
                name = id_match.group("name").strip()
                if not self._is_keyword(name) and not self._is_constant(name):
                    signals.add(name)

        # 敏感列表中的信号也视为读取
        sens_signals = re.findall(
            r'(?:posedge|negedge|,)\s*([a-zA-Z_][a-zA-Z0-9_$.\[\]]*)',
            block_text[:200],  # 敏感列表通常在块开头
        )
        for s in sens_signals:
            if not self._is_keyword(s):
                signals.add(s.strip())

        # 排除已赋值的信号
        assigned_set = set(assigned)
        read_only = signals - assigned_set

        return sorted(read_only)

    def _is_keyword(self, name: str) -> bool:
        """判断是否为 Verilog 关键字"""
        keywords = {
            'if', 'else', 'for', 'while', 'case', 'endcase',
            'begin', 'end', 'repeat', 'forever', 'posedge', 'negedge',
            'or', 'and', 'not', 'input', 'output', 'inout', 'wire', 'reg',
            'assign', 'always', 'module', 'endmodule', 'parameter',
            'localparam', 'integer', 'real', 'time', 'genvar', 'generate',
            'endgenerate', 'fork', 'join', 'disable', 'wait', 'assert',
            'assume', 'cover', 'property', 'sequence',
        }
        return name.lower() in keywords

    def _is_constant(self, name: str) -> bool:
        """判断是否为数字常量"""
        return bool(re.match(r'^\d+\'[bBdDhHoO][0-9a-fA-F_xXzZ?]+$', name)) or \
               bool(re.match(r'^\d+$', name))

    # ── 格式化输出 ──

    @staticmethod
    def format_classification(result: AlwaysClassification, title: str = "") -> str:
        """将分类结果格式化为可读 Markdown"""
        lines: list[str] = []
        if title:
            lines.append(f"# {title}")
        else:
            lines.append("# Always 块分类结果")
        lines.append("")

        lines.append(f"**模块**: {result.module_name}")
        lines.append("")

        # 时序块
        seq_count = len(result.sequential_blocks)
        lines.append(f"## 时序逻辑块 ({seq_count} 个)")
        lines.append("")
        if result.sequential_blocks:
            for i, blk in enumerate(result.sequential_blocks):
                lines.append(f"### 时序块 #{i + 1}")
                lines.append(f"- 敏感列表: `{blk.sensitivity}`")
                lines.append(f"- 时钟: `{blk.clock or 'N/A'}`")
                if blk.signals_assigned:
                    lines.append(f"- 赋值信号: {', '.join(f'`{s}`' for s in blk.signals_assigned)}")
                if blk.signals_read:
                    lines.append(f"- 读取信号: {', '.join(f'`{s}`' for s in blk.signals_read)}")
                lines.append("")
        else:
            lines.append("无时序逻辑块。")
            lines.append("")

        # 组合块
        comb_count = len(result.combinational_blocks)
        lines.append(f"## 组合逻辑块 ({comb_count} 个)")
        lines.append("")
        if result.combinational_blocks:
            for i, blk in enumerate(result.combinational_blocks):
                lines.append(f"### 组合块 #{i + 1}")
                sens_display = blk.sensitivity if blk.sensitivity else "@*"
                lines.append(f"- 敏感列表: `{sens_display}`")
                if blk.signals_assigned:
                    lines.append(f"- 赋值信号: {', '.join(f'`{s}`' for s in blk.signals_assigned)}")
                if blk.signals_read:
                    lines.append(f"- 读取信号: {', '.join(f'`{s}`' for s in blk.signals_read)}")
                lines.append("")
        else:
            lines.append("无组合逻辑块。")
            lines.append("")

        # 锁存器
        latch_count = len(result.latch_blocks)
        lines.append(f"## ⚠️ 锁存器块 ({latch_count} 个)")
        lines.append("")
        if result.latch_blocks:
            for i, blk in enumerate(result.latch_blocks):
                lines.append(f"### 锁存器 #{i + 1}")
                lines.append(f"- 敏感列表: `{blk.sensitivity}`")
                if blk.signals_assigned:
                    lines.append(f"- 赋值信号: {', '.join(f'`{s}`' for s in blk.signals_assigned)}")
                if blk.signals_read:
                    lines.append(f"- 读取信号: {', '.join(f'`{s}`' for s in blk.signals_read)}")
                lines.append("")
        else:
            lines.append("未检测到锁存器。")
            lines.append("")

        return "\n".join(lines)
