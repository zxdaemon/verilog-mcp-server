"""
统一的时钟/复位信号分类引擎 (Signal Classifier)

合并 clock_analyzer、always_classify、fsm_detector 三处
独立维护的时钟/复位识别规则，提供一致的判断接口。
"""

from __future__ import annotations
from ..database.models import ModuleDef

_CLOCK_PATTERNS = {"clk", "clock", "clkp", "clkn", "sys_clk", "ref_clk", "mclk", "pclk", "hclk", "aclk"}
_RESET_PATTERNS = {"rst", "rst_n", "reset", "reset_n", "rstn", "rstn_n", "rstb",
                   "reset_n", "reset_b", "nrst", "n_reset", "rst_ni", "reset_ni"}


class SignalClassifier:
    """时钟/复位信号统一识别器"""

    def is_clock(self, signal_name: str, module: ModuleDef) -> bool:
        """判断信号是否为时钟候选

        规则:
        1. 信号名包含已知时钟模式
        2. 信号是 input 端口且非复位
        3. 出现在 2+ 个 always 块的敏感列表中
        """
        name_lower = signal_name.lower()

        if self.is_reset(signal_name):
            return False

        for pat in _CLOCK_PATTERNS:
            if pat in name_lower:
                return True

        for p in module.ports:
            if p.name == signal_name and p.direction == "input":
                return True

        clk_count = sum(
            1 for ab in module.always_blocks
            if signal_name.lower() in ab.sensitivity_list.lower()
        )
        if clk_count >= 2:
            return True

        return False

    def is_reset(self, signal_name: str) -> bool:
        """判断信号是否为复位候选（基于命名）"""
        name_lower = signal_name.lower()
        return any(kw in name_lower for kw in _RESET_PATTERNS)

    def infer_reset_polarity(self, signal_name: str, edge: str) -> str:
        """推断复位极性

        规则:
        - 信号名以 _n / _b 结尾 → active low
        - 信号名包含 rst_n → active low
        - edge 为 negedge → active low
        - 否则 active high
        """
        name_lower = signal_name.lower()
        if name_lower.endswith(("_n", "_b", "_neg")):
            return "low"
        if "rst_n" in name_lower:
            return "low"
        if edge == "negedge":
            return "low"
        return "high"
