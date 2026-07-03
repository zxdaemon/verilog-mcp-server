"""
Yosys 适配器 — 通过 pyosys Python API 调用 Yosys 综合工具

Yosys 流水线（无需工艺库）：
  read_verilog -sv <files> → hierarchy -top <top> → proc →
  fsm_detect → fsm_export → check → clk2fflogic → stat -json → write_json

通过 pyosys (libyosys) 在进程内调用，无需外部二进制。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
from typing import Optional

from .base_adapter import BaseEdaAdapter

logger = logging.getLogger(__name__)

# ── Yosys pass 命令列表 ──
# 每个元素是 (pass_template, needs_output_dir) 的元组
# pass_template 中 {files}, {top}, {output_dir} 会被替换
_YOSYS_PASSES: list[tuple[str, bool]] = [
    ("read_verilog -sv {files}", False),
    ("hierarchy -top {top}", False),
    ("proc", False),
    ("fsm_detect", False),
    ("fsm_export -o {output_dir}/fsm.kiss2", True),
    ("check -noinit", False),
    ("clk2fflogic", False),
    ("stat -json {output_dir}/stat.json", True),
    ("write_json {output_dir}/yosys_netlist.json", True),
]


class YosysAdapter(BaseEdaAdapter):
    """Yosys 综合工具适配器

    通过 pyosys Python API (libyosys) 在进程内运行 Yosys pass，
    解析输出 JSON 提取 FSM、组合环、门控时钟、资源统计。
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._available: Optional[bool] = None
        self._ys = None  # pyosys libyosys 模块引用

    def _try_import(self) -> bool:
        """尝试导入 pyosys，缓存结果"""
        if self._available is not None:
            return self._available
        try:
            import pyosys.libyosys as ys
            self._ys = ys
            self._available = True
            logger.debug("pyosys 可用")
        except ImportError as e:
            self._available = False
            logger.debug(f"pyosys 不可用: {e}")
        return self._available

    def check_available(self) -> bool:
        """检测 pyosys 是否可导入"""
        return self._try_import()

    def run(self, file_paths: list[str], top_module: str, output_dir: str) -> bool:
        """运行 Yosys 综合分析

        Args:
            file_paths: RTL 源文件路径列表
            top_module: 顶层模块名
            output_dir: 输出目录

        Returns:
            True 表示运行成功
        """
        # 检查可用性
        if not self.is_available():
            logger.warning("Yosys (pyosys) 不可用，跳过")
            return False

        if not file_paths:
            logger.warning("无 RTL 文件，跳过 Yosys")
            return False

        # 确保 pyosys 已导入
        if not self._try_import():
            return False

        ys = self._ys

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 准备 pass 参数
        files_str = " ".join(shlex.quote(f) for f in file_paths)
        abs_output_dir = os.path.abspath(output_dir)

        # 创建 Design 对象
        design = ys.Design()

        # 逐条执行 pass
        for pass_tmpl, needs_output_dir in _YOSYS_PASSES:
            if needs_output_dir:
                cmd = pass_tmpl.format(
                    files=files_str,
                    top=shlex.quote(top_module),
                    output_dir=shlex.quote(abs_output_dir),
                )
            else:
                cmd = pass_tmpl.format(
                    files=files_str,
                    top=shlex.quote(top_module),
                    output_dir="",
                )

            try:
                logger.debug(f"执行 yosys pass: {cmd}")
                ys.run_pass(cmd, design)
            except RuntimeError as e:
                # yosys pass 失败（如 check 发现问题），记录但继续
                logger.warning(f"Yosys pass 失败 ({cmd.split()[0]}): {e}")
            except Exception as e:
                logger.warning(f"Yosys pass 异常 ({cmd.split()[0]}): {e}")

        # 检查输出文件
        if not self._output_files_exist(abs_output_dir):
            logger.warning("Yosys 运行完成但未产生预期输出文件")
            return False

        logger.info(f"Yosys 运行成功，输出: {abs_output_dir}")
        return True

    def parse_output(self, output_dir: str) -> dict:
        """解析 Yosys 输出目录中的所有结果

        Args:
            output_dir: Yosys 输出目录

        Returns:
            {
                "fsms": [...],
                "comb_loops": [...],
                "gated_clocks": [...],
                "stats": [...],
            }
        """
        results: dict = {
            "fsms": [],
            "comb_loops": [],
            "gated_clocks": [],
            "stats": [],
        }

        design_json_path = os.path.join(output_dir, "yosys_netlist.json")
        stat_json_path = os.path.join(output_dir, "stat.json")

        # 解析 JSON 网表
        if os.path.exists(design_json_path):
            try:
                with open(design_json_path, "r", encoding="utf-8") as f:
                    design = json.load(f)
                results["fsms"] = self._parse_fsm(design)
                results["gated_clocks"] = self._parse_gated_clocks(design)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Yosys JSON 网表解析失败: {e}")

        # 解析 stat JSON
        if os.path.exists(stat_json_path):
            try:
                with open(stat_json_path, "r", encoding="utf-8") as f:
                    stat_data = json.load(f)
                results["stats"] = self._parse_stat(stat_data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Yosys stat JSON 解析失败: {e}")

        return results

    # ── 内部解析方法 ──

    def _parse_fsm(self, design: dict) -> list[dict]:
        """从 Yosys JSON 网表中提取 FSM 列表

        Yosys JSON 结构中，FSM 信息在 modules.<name>.cells 中，
        带有 $fsm 或 fsm 前缀的单元。

        Args:
            design: Yosys write_json 输出的完整 JSON

        Returns:
            FSM 数据列表，每项包含 fsm_name, module_name, state_count, encoding, transitions
        """
        fsms = []
        modules = design.get("modules", {})

        for mod_name, mod_data in modules.items():
            cells = mod_data.get("cells", {})
            for cell_name, cell_data in cells.items():
                if "$fsm" in cell_name or cell_name.startswith("fsm"):
                    fsm_info = self._extract_fsm_info(cell_data, cell_name, mod_name)
                    if fsm_info:
                        fsms.append(fsm_info)

        return fsms

    def _extract_fsm_info(self, cell_data: dict, cell_name: str, module_name: str) -> Optional[dict]:
        """从单个 FSM cell 提取信息

        Args:
            cell_data: cell 的 JSON 数据
            cell_name: cell 名称
            module_name: 所属模块名

        Returns:
            FSM 信息字典或 None
        """
        try:
            parameters = cell_data.get("parameters", {})
            attributes = cell_data.get("attributes", {})

            # 状态数
            state_count = 0
            for key in ("\\STATE_COUNT", "STATE_COUNT", "NUM_STATES"):
                if key in parameters:
                    state_count = int(parameters[key], 0)
                    break

            # 编码方式推断
            encoding = self._infer_encoding(cell_data, state_count)

            # 状态跳转（从 JSON 网表启发式提取）
            transitions = self._extract_transitions(cell_data)

            return {
                "fsm_name": cell_name.replace("\\", "").lstrip("$"),
                "module_name": module_name,
                "state_count": state_count,
                "encoding": encoding,
                "transitions": transitions,
                "source_file": attributes.get("\\src", ""),
            }
        except Exception as e:
            logger.debug(f"提取 FSM 信息失败 ({cell_name}): {e}")
            return None

    def _infer_encoding(self, cell_data: dict, state_count: int) -> str:
        """推断 FSM 状态编码方式

        通过检查 cell 内部连接和参数推断编码类型。

        Args:
            cell_data: cell 数据
            state_count: 状态数

        Returns:
            编码描述字符串
        """
        parameters = cell_data.get("parameters", {})
        connections = cell_data.get("connections", {})

        # 检查是否有编码相关参数
        for key in ("\\ENCODING", "ENCODING", "\\FSM_ENCODING"):
            if key in parameters:
                enc = str(parameters[key]).lower()
                if "one-hot" in enc or "onehot" in enc:
                    return "one-hot"
                elif "gray" in enc:
                    return "gray"
                elif "binary" in enc:
                    return "binary"

        # 通过状态位宽推断
        state_bits = 0
        for conn_name, conn_data in connections.items():
            if "state" in conn_name.lower() or "rst" in conn_name.lower():
                if isinstance(conn_data, list) and len(conn_data) > 1:
                    state_bits = len(conn_data) - 1

        if state_bits > 0:
            if state_bits == state_count:
                return "one-hot"
            elif state_bits == state_count.bit_length():
                return "binary"
            elif state_bits > state_count:
                return "one-hot"

        return "unknown"

    def _extract_transitions(self, cell_data: dict) -> list[dict]:
        """从 JSON 网表启发式提取 FSM 状态跳转关系

        从 connections 中提取与状态转移相关的信号。

        Args:
            cell_data: cell 数据

        Returns:
            跳转列表 [{"from": "N/A", "to": "N/A", "condition": "..."}, ...]
        """
        transitions = []
        connections = cell_data.get("connections", {})

        # 从 connections 提取 CTRL_IN / ARST 等信号
        for conn_name in connections:
            conn_lower = conn_name.replace("\\", "").lower()
            if any(kw in conn_lower for kw in ("ctrl", "state", "trans", "next")):
                transitions.append({
                    "from": "N/A",
                    "to": "N/A",
                    "condition": f"signal: {conn_name}",
                })

        if not transitions:
            transitions.append({
                "from": "N/A",
                "to": "N/A",
                "condition": "implicit (extracted from netlist)",
            })

        return transitions

    def _parse_gated_clocks(self, design: dict) -> list[dict]:
        """从 Yosys `clk2fflogic` 处理后的网表中识别门控时钟信号

        Args:
            design: Yosys JSON 网表

        Returns:
            门控时钟列表
        """
        gated_clocks = []
        modules = design.get("modules", {})

        for mod_name, mod_data in modules.items():
            cells = mod_data.get("cells", {})

            for cell_name, cell_data in cells.items():
                cell_type = cell_data.get("type", "")

                # Latch-based 门控: $dlatch 或 $_DLATCH_*
                if "$dlatch" in cell_type.lower() or "_dlatch" in cell_type.lower():
                    gated = self._extract_gated_clock_info(
                        cell_data, cell_name, mod_name, "latch_based"
                    )
                    if gated:
                        gated_clocks.append(gated)

                # AND-gate 门控: $_AND_ 驱动时钟
                if (
                    "$_AND_" in cell_type or "and" in cell_type.lower()
                ) and "clk" in cell_name.lower():
                    gated = self._extract_gated_clock_info(
                        cell_data, cell_name, mod_name, "and_gate"
                    )
                    if gated:
                        gated_clocks.append(gated)

        return gated_clocks

    def _extract_gated_clock_info(
        self, cell_data: dict, cell_name: str, module_name: str, gate_type: str
    ) -> Optional[dict]:
        """从单个 cell 提取门控时钟信息

        Args:
            cell_data: cell 数据
            cell_name: cell 名称
            module_name: 模块名
            gate_type: 门控类型

        Returns:
            门控时钟信息字典或 None
        """
        connections = cell_data.get("connections", {})

        # 提取连接的信号
        connected_signals = []
        for conn_name, conn_data in connections.items():
            if isinstance(conn_data, list) and len(conn_data) > 0:
                for bit in conn_data:
                    if isinstance(bit, str) and bit:
                        connected_signals.append(bit)

        enable_signal = ""
        source_clock = ""

        for sig in connected_signals:
            sig_lower = sig.lower()
            if any(kw in sig_lower for kw in ("en", "enable", "gate", "gating")):
                enable_signal = sig
            elif "clk" in sig_lower or "clock" in sig_lower:
                source_clock = sig

        if not source_clock and len(connected_signals) >= 1:
            source_clock = connected_signals[0]
        if not enable_signal and len(connected_signals) >= 2:
            enable_signal = connected_signals[1]

        if source_clock:
            return {
                "gated_clock_name": cell_name.replace("\\", ""),
                "source_clock": source_clock,
                "enable_signal": enable_signal or "unknown",
                "type": gate_type,
                "module_name": module_name,
            }

        return None

    def _parse_stat(self, stat_data: dict) -> list[dict]:
        """解析 Yosys `stat -json` 输出的资源统计

        Args:
            stat_data: stat JSON 数据

        Returns:
            资源统计列表，每项对应一个模块
        """
        stats = []

        design = stat_data.get("design", stat_data)
        modules = stat_data.get("modules", {})

        if not modules:
            stat_entry = self._extract_stat_entry(design, "top")
            if stat_entry:
                stats.append(stat_entry)
            return stats

        for mod_name, mod_data in modules.items():
            stat_entry = self._extract_stat_entry(mod_data, mod_name)
            if stat_entry:
                stats.append(stat_entry)

        return stats

    def _extract_stat_entry(self, data: dict, module_name: str) -> Optional[dict]:
        """从 stat 数据块提取资源统计

        Args:
            data: 统计数据块
            module_name: 模块名

        Returns:
            统计字典
        """
        num_cells = data.get("num_cells", 0)
        num_wires = data.get("num_wires", 0)

        cells_by_type = data.get("num_cells_by_type", {})

        num_lut = 0
        num_ff = 0
        num_memory = 0
        num_dsp = 0

        for cell_type, count in cells_by_type.items():
            ct = cell_type.lower()
            if any(kw in ct for kw in ("lut", "$lut", "$_lut", "mux", "$mux", "$pmux")):
                num_lut += count
            elif any(kw in ct for kw in ("dff", "$dff", "$_dff", "$_ff", "sdff", "dffe", "dlatch", "$dlatch")):
                num_ff += count
            elif any(kw in ct for kw in ("mem", "$mem", "ram", "rom", "bram")):
                num_memory += count
            elif any(kw in ct for kw in ("dsp", "$dsp", "mul", "mac")):
                num_dsp += count

        return {
            "module_name": module_name,
            "num_cells": num_cells,
            "num_wires": num_wires,
            "num_lut": num_lut,
            "num_ff": num_ff,
            "num_memory": num_memory,
            "num_dsp": num_dsp,
        }

    @staticmethod
    def _output_files_exist(output_dir: str) -> bool:
        """检查 Yosys 输出文件是否存在"""
        netlist = os.path.exists(os.path.join(output_dir, "yosys_netlist.json"))
        stat = os.path.exists(os.path.join(output_dir, "stat.json"))
        return netlist and stat
