"""
Phase 3 — 时钟域与复位域分析引擎 (Clock & Reset Domain Analyzer)

扫描所有 always 块的敏感列表，提取时钟和复位信息，进行时钟域分组、
复位类型检测、跨时钟域信号分析。
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from ..database.index_store import IndexStore
from ..database.models import ModuleDef, AlwaysBlockInfo
from .signal_classifier import SignalClassifier


@dataclass
class ResetInfo:
    """复位信号信息"""
    signal: str
    type: str                     # "async" or "sync"
    polarity: str                 # "high" or "low"
    domain_of_reset: str | None   # 关联的时钟域（异步复位通常关联时钟域）

    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "type": self.type,
            "polarity": self.polarity,
            "domain_of_reset": self.domain_of_reset,
        }


@dataclass
class ClockDomain:
    """时钟域"""
    clock_name: str               # 时钟信号名
    edge: str                     # "posedge" or "negedge"
    signals: list[str]            # 该时钟域驱动的信号
    resets: list[ResetInfo]       # 该时钟域中的复位

    def to_dict(self) -> dict:
        return {
            "clock_name": self.clock_name,
            "edge": self.edge,
            "signals": self.signals,
            "resets": [r.to_dict() for r in self.resets],
        }


@dataclass
class ClockAnalysis:
    """时钟分析结果"""
    module_name: str
    clock_domains: list[ClockDomain]
    async_resets: list[ResetInfo]
    sync_resets: list[ResetInfo]
    cross_domain_signals: list[dict]  # 跨时钟域信号

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "clock_domains": [d.to_dict() for d in self.clock_domains],
            "async_resets": [r.to_dict() for r in self.async_resets],
            "sync_resets": [r.to_dict() for r in self.sync_resets],
            "cross_domain_signals": self.cross_domain_signals,
        }


class ClockAnalyzer:
    """时钟域与复位域分析器"""

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store
        self._classifier = SignalClassifier()

    # ── 敏感列表解析 ──

    # 正则：匹配敏感列表中的 posedge/negedge 信号
    _RE_SENS_ITEM = re.compile(
        r'(?P<edge>posedge|negedge)\s+(?P<signal>[a-zA-Z_][a-zA-Z0-9_$.\[\]]*)',
        re.IGNORECASE,
    )

    # 匹配 always @(posedge clk or negedge rst_n) 中的完整敏感列表
    _RE_SENS_LIST = re.compile(
        r'(?:posedge|negedge)\s+[a-zA-Z_][a-zA-Z0-9_$.\[\]]*',
        re.IGNORECASE,
    )

    def _parse_sensitivity(self, sensitivity_list: str) -> list[dict]:
        """
        解析敏感列表，返回边缘和信号列表

        Returns:
            [{"edge": "posedge", "signal": "clk"}, ...]
        """
        items = []
        for match in self._RE_SENS_ITEM.finditer(sensitivity_list):
            items.append({
                "edge": match.group("edge").lower(),
                "signal": match.group("signal").strip(),
            })
        return items

    # ── public API ──

    def analyze(self, module_name: str) -> ClockAnalysis:
        """
        分析指定模块的时钟域和复位域

        Args:
            module_name: 模块名

        Returns:
            ClockAnalysis

        Raises:
            ValueError: 如果模块不存在
        """
        mod = self._index_store.get_module(module_name)
        if not mod:
            raise ValueError(f"模块 '{module_name}' 不存在于索引中")

        clock_domains: dict[str, ClockDomain] = {}
        all_resets: list[ResetInfo] = []
        async_resets: list[ResetInfo] = []
        sync_resets: list[ResetInfo] = []

        for ab in mod.always_blocks:
            sens = ab.sensitivity_list
            sens_items = self._parse_sensitivity(sens)
            block_text = "\n".join(ab.statements)

            # 提取本块中赋值的信号
            assigned_signals = self._extract_assigned_signals(block_text)

            # 分离时钟和复位信号
            clock_items = [s for s in sens_items if self._classifier.is_clock(s["signal"], mod)]
            reset_items = [s for s in sens_items if not self._classifier.is_clock(s["signal"], mod)]

            # 处理时钟
            for ci in clock_items:
                clk_name = ci["signal"]
                edge = ci["edge"]
                if clk_name not in clock_domains:
                    clock_domains[clk_name] = ClockDomain(
                        clock_name=clk_name,
                        edge=edge,
                        signals=[],
                        resets=[],
                    )
                clock_domains[clk_name].signals.extend(
                    s for s in assigned_signals if s not in clock_domains[clk_name].signals
                )

            # 处理复位
            # 敏感列表中的非时钟信号可能是异步复位
            for ri in reset_items:
                rst_signal = ri["signal"]
                rst_edge = ri["edge"]

                # 极性推断：posedge rst_n → active low async reset
                # negedge rst_n → active low async reset
                polarity = self._classifier.infer_reset_polarity(rst_signal, rst_edge)
                rst_type = "async"  # 在敏感列表中的复位通常是异步的

                rst_info = ResetInfo(
                    signal=rst_signal,
                    type=rst_type,
                    polarity=polarity,
                    domain_of_reset=clock_items[0]["signal"] if clock_items else None,
                )
                async_resets.append(rst_info)

                if clock_items:
                    clk_name = clock_items[0]["signal"]
                    if clk_name in clock_domains:
                        clock_domains[clk_name].resets.append(rst_info)

            # 检查同步复位（在 always 块内部检查 if(!rst_n) 但不在敏感列表中）
            if clock_items and not reset_items:
                sync_rsts = self._detect_sync_reset(block_text, mod)
                for sr in sync_rsts:
                    sync_resets.append(sr)

        # 跨时钟域信号检测
        cross_domain = self._detect_cross_domain(list(clock_domains.values()))

        return ClockAnalysis(
            module_name=module_name,
            clock_domains=list(clock_domains.values()),
            async_resets=async_resets,
            sync_resets=sync_resets,
            cross_domain_signals=cross_domain,
        )

    def detect_cross_domain_signals(self, module_name: str) -> list[dict]:
        """
        检测指定模块中的跨时钟域信号

        Args:
            module_name: 模块名

        Returns:
            list[dict]: 跨时钟域信号列表
        """
        analysis = self.analyze(module_name)
        return analysis.cross_domain_signals

    # ── 辅助方法 ──

    def _extract_assigned_signals(self, block_text: str) -> list[str]:
        """从 always 块文本中提取被赋值的信号（<= 或 = 的 LHS）"""
        from .expr_walker import extract_signal_refs

        signals: set[str] = set()

        text_no_case = re.sub(
            r'case[zx]?\s*\([^)]+\)\s*.*?\s*endcase',
            '',
            block_text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        for m in re.finditer(
            r'(\w+(?:\s*\[[^\]]+\])?)\s*(<=|=(?!\s*0\s*;))\s*',
            text_no_case,
        ):
            lhs = m.group(1).strip()
            refs = extract_signal_refs(lhs)
            if refs:
                signals.add(refs[0])

        return list(signals)

    def _detect_sync_reset(self, block_text: str, mod: ModuleDef) -> list[ResetInfo]:
        """
        检测同步复位

        在 always @(posedge clk) 块中查找 if (!rst_n) 或 if (rst) 模式
        """
        resets: list[ResetInfo] = []

        # 查找 if (!rst_n) 或 if (rst) 或 if (rst == 1'b1)
        reset_patterns = [
            r'if\s*\(\s*!\s*(?P<sig1>[a-zA-Z_][a-zA-Z0-9_]*)\s*\)',
            r'if\s*\(\s*(?P<sig2>[a-zA-Z_][a-zA-Z0-9_]*)\s*\)',
            r'if\s*\(\s*(?P<sig3>[a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*1\'b1\s*\)',
            r'if\s*\(\s*(?P<sig4>[a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*1\'b0\s*\)',
        ]

        for pat in reset_patterns:
            for m in re.finditer(pat, block_text):
                for key, sig in m.groupdict().items():
                    if sig and self._classifier.is_reset(sig):
                        # 确定极性
                        is_neg = '!' in m.group(0) or '1\'b0' in m.group(0)
                        polarity = "low" if is_neg else "high"
                        # 检查信号名
                        if sig.lower().endswith(('_n', '_b')) or 'rst_n' in sig.lower():
                            polarity = "low"
                        resets.append(ResetInfo(
                            signal=sig,
                            type="sync",
                            polarity=polarity,
                            domain_of_reset=None,
                        ))
                        break
                break  # 只取第一个匹配的信号

        return resets

    def _detect_cross_domain(self, domains: list[ClockDomain]) -> list[dict]:
        """
        检测跨时钟域信号

        如果某个信号出现在多个时钟域中，则标记为跨时钟域信号
        """
        cross_domain = []

        if len(domains) < 2:
            return cross_domain

        # 构建信号到时钟域的映射
        signal_domains: dict[str, list[str]] = {}
        for domain in domains:
            for sig in domain.signals:
                if sig not in signal_domains:
                    signal_domains[sig] = []
                if domain.clock_name not in signal_domains[sig]:
                    signal_domains[sig].append(domain.clock_name)

        # 找出跨时钟域信号
        for sig, clks in signal_domains.items():
            if len(clks) >= 2:
                cross_domain.append({
                    "signal": sig,
                    "clock_domains": clks,
                    "risk": "高" if "posedge" in str(clks) else "中",
                    "note": "信号在多个时钟域中被驱动，可能需要同步器",
                })

        return cross_domain

    @staticmethod
    def _get_clock_name(signal_name: str) -> str:
        """标准化时钟名"""
        return signal_name.strip()

    # ── 格式化输出 ──

    @staticmethod
    def format_clock_analysis(analysis: ClockAnalysis, title: str = "") -> str:
        """将时钟分析结果格式化为可读 Markdown"""
        lines: list[str] = []
        if title:
            lines.append(f"# {title}")
        else:
            lines.append("# ⏰ 时钟域与复位域分析")
        lines.append("")

        lines.append(f"**模块**: {analysis.module_name}")
        lines.append("")

        # 时钟域
        lines.append(f"## 时钟域 ({len(analysis.clock_domains)} 个)")
        lines.append("")
        for i, domain in enumerate(analysis.clock_domains):
            lines.append(f"### 时钟域 {i + 1}: `{domain.clock_name}` ({domain.edge})")
            lines.append("")
            lines.append(f"- **时钟信号**: `{domain.clock_name}`")
            lines.append(f"- **时钟边沿**: {domain.edge}")
            lines.append(f"- **驱动的信号数**: {len(domain.signals)}")
            if domain.signals:
                lines.append(f"- **信号列表**:")
                for sig in domain.signals:
                    lines.append(f"  - `{sig}`")

            if domain.resets:
                for rst in domain.resets:
                    polarity_str = "高有效" if rst.polarity == "high" else "低有效"
                    lines.append(f"- **复位**: `{rst.signal}` ({rst.type}, {polarity_str})")
            lines.append("")

        # 复位域
        if analysis.async_resets or analysis.sync_resets:
            lines.append(f"## 复位域")
            lines.append("")

            if analysis.async_resets:
                lines.append(f"### 异步复位 ({len(analysis.async_resets)} 个)")
                for rst in analysis.async_resets:
                    polarity_str = "高有效" if rst.polarity == "high" else "低有效"
                    domain_str = f" (关联时钟: {rst.domain_of_reset})" if rst.domain_of_reset else ""
                    lines.append(f"- `{rst.signal}` ({polarity_str}){domain_str}")
                lines.append("")

            if analysis.sync_resets:
                lines.append(f"### 同步复位 ({len(analysis.sync_resets)} 个)")
                for rst in analysis.sync_resets:
                    polarity_str = "高有效" if rst.polarity == "high" else "低有效"
                    lines.append(f"- `{rst.signal}` ({polarity_str})")
                lines.append("")

        # 跨时钟域信号
        if analysis.cross_domain_signals:
            lines.append(f"## ⚡ 跨时钟域信号 ({len(analysis.cross_domain_signals)} 个)")
            lines.append("")
            for cd in analysis.cross_domain_signals:
                lines.append(f"- `{cd['signal']}`: 出现在 {', '.join(cd['clock_domains'])}")
                lines.append(f"  - 风险: {cd['risk']}")
                lines.append(f"  - 建议: {cd['note']}")
            lines.append("")
        else:
            lines.append("## ⚡ 跨时钟域信号")
            lines.append("")
            lines.append("未检测到跨时钟域信号。")
            lines.append("")

        return "\n".join(lines)
