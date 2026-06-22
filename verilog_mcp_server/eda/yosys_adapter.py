"""
Yosys 适配器 — 通过 CLI 调用 Yosys 综合工具

Yosys 流水线（无需工艺库）：
  read_verilog -sv <files> → hierarchy -top <top> → proc →
  fsm_detect → fsm_export → check → clk2fflogic → stat -json → write_json

通过 CLI 调用，零 Python 依赖。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from string import Template
from typing import Optional

from .base_adapter import BaseEdaAdapter

logger = logging.getLogger(__name__)

# ── Yosys Tcl 脚本模板 ──

_YOSYS_TCL_TEMPLATE = Template("""\
# Yosys 分析脚本 (auto-generated)
read_verilog -sv ${files}
hierarchy -top ${top}
proc
fsm_detect
fsm_export -o ${output_dir}/fsm.kiss2
check -noinit
clk2fflogic
stat -json ${output_dir}/stat.json
write_json ${output_dir}/yosys_netlist.json
""")

# ── 默认 Yosys 可执行文件名 ──
DEFAULT_YOSYS_CMD = "yosys"


class YosysAdapter(BaseEdaAdapter):
    """Yosys 综合工具适配器

    通过生成 Tcl 脚本 + CLI 调用的方式运行 Yosys，
    解析输出 JSON 提取 FSM、组合环、门控时钟、资源统计。
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        # 优先级：环境变量（PyInstaller bundled） > config 指定 > PATH 查找
        bundled = os.environ.get("YOSYS_BUNDLED_PATH", "")
        configured = self.config.get("yosys_path", "")
        self._yosys_cmd = bundled or configured or DEFAULT_YOSYS_CMD
        self._extra_args = self.config.get("extra_args", [])

    def check_available(self) -> bool:
        """检测 yosys 命令是否在 PATH 中可用"""
        try:
            result = subprocess.run(
                [self._yosys_cmd, "-V"],
                capture_output=True,
                text=True,
                timeout=10,
                env=os.environ.copy(),
            )
            if result.returncode == 0 and "Yosys" in (result.stdout + result.stderr):
                logger.debug(f"Yosys 可用: {self._yosys_cmd}")
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as e:
            logger.debug(f"Yosys 不可用: {e}")
            return False

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
            logger.warning("Yosys 不可用，跳过")
            return False

        if not file_paths:
            logger.warning("无 RTL 文件，跳过 Yosys")
            return False

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 生成 Tcl 脚本
        files_str = " ".join(shlex.quote(f) for f in file_paths)
        tcl_script = _YOSYS_TCL_TEMPLATE.substitute(
            files=files_str,
            top=shlex.quote(top_module),
            output_dir=shlex.quote(os.path.abspath(output_dir)),
        )

        # 写入临时 Tcl 脚本
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tcl", delete=False, encoding="utf-8"
        ) as f:
            f.write(tcl_script)
            tcl_path = f.name

        try:
            cmd = [self._yosys_cmd, "-s", tcl_path] + self._extra_args
            logger.info(f"运行 Yosys: {' '.join(cmd)}")
            logger.debug(f"Tcl 脚本: {tcl_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
                env=os.environ.copy(),
                cwd=output_dir,
            )

            if result.returncode != 0:
                # Yosys 会返回非零，但可能仍有部分输出可用
                stderr_tail = result.stderr[-500:] if result.stderr else ""
                logger.warning(
                    f"Yosys 返回非零退出码 {result.returncode}: {stderr_tail}"
                )
                # 检查是否有部分输出文件
                if not self._output_files_exist(output_dir):
                    return False

            # 检查输出文件
            if not self._output_files_exist(output_dir):
                logger.warning("Yosys 运行完成但未产生预期输出文件")
                return False

            logger.info(f"Yosys 运行成功，输出: {output_dir}")
            return True

        except subprocess.TimeoutExpired:
            logger.warning("Yosys 运行超时（600s）")
            return False
        except Exception as e:
            logger.warning(f"Yosys 运行异常: {e}")
            return False
        finally:
            # 清理临时 Tcl 脚本
            try:
                os.unlink(tcl_path)
            except OSError:
                pass

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

        # 解析 check 输出（从 stdout/stderr 日志，如果有的话）
        # check 输出通过 subprocess 的 stderr 传递，这里从文件解析
        # 实际上 Yosys check 结果在 stdout/stderr 中，需要从 run() 阶段捕获
        # 这里作为备用：检查是否有 check 日志文件

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
                    state_count = int(parameters[key], 0)  # int with base 0 supports hex/bin/dec
                    break

            # 编码方式推断
            encoding = self._infer_encoding(cell_data, state_count)

            # 状态跳转
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
                    state_bits = len(conn_data) - 1  # approximate

        if state_bits > 0:
            if state_bits == state_count:
                return "one-hot"
            elif state_bits == state_count.bit_length():
                return "binary"
            elif state_bits > state_count:
                return "one-hot"

        # 默认
        return "unknown"

    def _extract_transitions(self, cell_data: dict) -> list[dict]:
        """提取 FSM 状态跳转关系

        Args:
            cell_data: cell 数据

        Returns:
            跳转列表 [{"from": "IDLE", "to": "START", "condition": "..."}, ...]
        """
        transitions = []
        # Yosys FSM cell 的 connections 包含状态和跳转
        # 具体的键名取决于 Yosys 版本，进行启发式提取
        connections = cell_data.get("connections", {})
        parameters = cell_data.get("parameters", {})

        # 尝试从 STATE_TABLE 参数提取
        for key in ("\\STATE_TABLE", "STATE_TABLE"):
            table = parameters.get(key, "")
            if table:
                # state_table 格式复杂，做简单标记
                transitions.append({
                    "from": "N/A",
                    "to": "N/A",
                    "condition": f"state_table: {str(table)[:100]}",
                })
                break

        if not transitions:
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

    def _parse_comb_loops(self, check_output: str) -> list[dict]:
        """解析 Yosys `check` pass 的输出，提取组合逻辑环告警

        Args:
            check_output: check pass 的 stderr/stdout 文本

        Returns:
            组合环列表
        """
        loops = []
        if not check_output or "logic loop" not in check_output.lower():
            return loops

        # Yosys check 输出格式类似:
        # Found logic loop in module <name>:
        #   cell $abc ...
        #   wire ...
        lines = check_output.splitlines()
        current_loop: Optional[dict] = None

        for line in lines:
            if "logic loop" in line.lower():
                if current_loop and current_loop.get("loop_signals"):
                    loops.append(current_loop)
                current_loop = {
                    "loop_signals": [],
                    "source_files": [],
                    "severity": "warn",
                    "message": line.strip(),
                }
            elif current_loop is not None:
                # 提取信号名
                match = re.search(r"(?:wire|cell)\s+(\S+)", line)
                if match:
                    current_loop["loop_signals"].append(match.group(1))

        if current_loop and current_loop.get("loop_signals"):
            loops.append(current_loop)

        return loops

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
        attributes = cell_data.get("attributes", {})

        # 提取连接的信号
        connected_signals = []
        for conn_name, conn_data in connections.items():
            if isinstance(conn_data, list) and len(conn_data) > 0:
                # 连接指向的 wire
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

        # 如果连接数 >= 2，第一个可能是时钟，第二个可能是使能
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

        # stat -json 的顶层结构
        design = stat_data.get("design", stat_data)
        modules = stat_data.get("modules", {})

        # 如果 modules 为空，解析全局统计
        if not modules:
            stat_entry = self._extract_stat_entry(design, "top")
            if stat_entry:
                stats.append(stat_entry)
            return stats

        # 逐个模块统计
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

        # 单元类型计数
        cells_by_type = data.get("num_cells_by_type", {})

        # 估算 LUT/FF/Memory/DSP
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

        # 如果没有分类计数，返回基础统计
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
