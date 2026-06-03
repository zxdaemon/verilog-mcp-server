"""
时钟域结构图构建引擎 (Clock Tree Builder)

遍历模块层次树，收集各模块的时钟域信息，通过 port_connections
将本地时钟信号名逐级映射为顶层信号名，按根时钟域分组展示。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..database.index_store import IndexStore
from ..database.models import InstanceDef
from ..database.errors import ModuleNotFoundError
from .clock_analyzer import ClockAnalyzer, ResetInfo
from .hierarchy import HierarchyBuilder, HierarchyNode

DEFAULT_GATED_CLOCK_PATTERNS = ["gated_clk_cell", "icg", "CLKGATE", "clock_gate", "clk_gate"]


@dataclass
class ClockModuleInfo:
    """单个模块实例的时钟信息"""
    module_type: str
    instance_name: str
    instance_path: str
    local_clock_signal: str
    edge: str                       # posedge / negedge
    resets: list[ResetInfo] = field(default_factory=list)
    is_gated_cell: bool = False
    depth: int = 0

    def to_dict(self) -> dict:
        return {
            "module_type": self.module_type, "instance_name": self.instance_name,
            "instance_path": self.instance_path, "local_clock_signal": self.local_clock_signal,
            "edge": self.edge, "is_gated_cell": self.is_gated_cell, "depth": self.depth,
            "resets": [r.to_dict() for r in self.resets],
        }


@dataclass
class ClockDomainGroup:
    """一个时钟域的所有模块"""
    root_clock_name: str
    edge: str = "posedge"
    modules: list[ClockModuleInfo] = field(default_factory=list)
    all_resets: list[ResetInfo] = field(default_factory=list)
    is_gated: bool = False
    gated_from: str | None = None
    gating_cell_path: str | None = None

    @property
    def module_count(self) -> int:
        return len(self.modules)


@dataclass
class ClockTreeResult:
    """完整时钟树分析结果"""
    top_module: str
    clock_domains: list[ClockDomainGroup] = field(default_factory=list)
    unclocked_modules: list[str] = field(default_factory=list)


class ClockTreeBuilder:
    """时钟树构建器"""

    def __init__(self, index_store: IndexStore,
                 gated_clock_patterns: list[str] | None = None):
        self._index_store = index_store
        self._clock_analyzer = ClockAnalyzer(index_store)
        self._hierarchy_builder = HierarchyBuilder(index_store)
        self._gated_patterns = gated_clock_patterns or DEFAULT_GATED_CLOCK_PATTERNS[:]

    def build(self, top_module: str, max_depth: int = 10) -> ClockTreeResult:
        """构建时钟域结构图"""
        mod = self._index_store.get_module(top_module)
        if not mod:
            raise ModuleNotFoundError(top_module)

        result = ClockTreeResult(top_module=top_module)

        # Phase 1: 收集所有模块的时钟域
        all_entries: list[ClockModuleInfo] = []
        self._collect_clock_info(top_module, top_module, set(), 0, max_depth,
                                all_entries, result)

        if not all_entries:
            return result

        # Phase 2: 将本地时钟名映射到根时钟名
        root_clock_map: dict[str, str] = {}  # instance_path+clock → root_clock
        for entry in all_entries:
            key = f"{entry.instance_path}|{entry.local_clock_signal}"
            root_clock_map[key] = self._trace_clock_to_root(
                entry.instance_path, entry.local_clock_signal, top_module)

        # Phase 3: 按时钟名分组
        group_map: dict[str, ClockDomainGroup] = {}
        for entry in all_entries:
            key = f"{entry.instance_path}|{entry.local_clock_signal}"
            root_clock = root_clock_map[key]
            if root_clock not in group_map:
                group_map[root_clock] = ClockDomainGroup(
                    root_clock_name=root_clock, edge=entry.edge)
            group = group_map[root_clock]
            group.modules.append(entry)
            for rst in entry.resets:
                if rst.signal not in {r.signal for r in group.all_resets}:
                    group.all_resets.append(rst)

        # Phase 4: 检测门控时钟
        for group in list(group_map.values()):
            for entry in group.modules:
                if entry.is_gated_cell:
                    group.is_gated = True
                    group.gating_cell_path = entry.instance_path

        # 按模块数降序排列
        result.clock_domains = sorted(group_map.values(),
                                      key=lambda g: -g.module_count)
        return result

    def _collect_clock_info(self, module_name: str, instance_path: str,
                            visited: set, depth: int, max_depth: int,
                            entries: list, result: ClockTreeResult):
        """递归收集时钟域信息"""
        if depth > max_depth or module_name in visited:
            return
        visited.add(module_name)

        mod = self._index_store.get_module(module_name)
        if not mod:
            return

        try:
            analysis = self._clock_analyzer.analyze(module_name)
        except Exception:
            analysis = None

        if analysis and analysis.clock_domains:
            for cd in analysis.clock_domains:
                entries.append(ClockModuleInfo(
                    module_type=module_name,
                    instance_name=instance_path.split(".")[-1] if "." in instance_path else module_name,
                    instance_path=instance_path,
                    local_clock_signal=cd.clock_name,
                    edge=cd.edge,
                    resets=cd.resets[:],
                    is_gated_cell=self._is_gated_clock_cell(module_name),
                    depth=depth,
                ))
        else:
            result.unclocked_modules.append(instance_path)

        # 遍历子模块
        for inst in mod.instances:
            child_name = inst.module_type
            child_path = f"{instance_path}.{inst.instance_name}"
            self._collect_clock_info(child_name, child_path, set(visited),
                                    depth + 1, max_depth, entries, result)

    def _trace_clock_to_root(self, instance_path: str, local_clock: str,
                             top_module: str) -> str:
        """沿 instance_path 向上追踪，将本地时钟名映射为顶层信号名

        通过 IndexStore 直接查找每层父模块的例化 port_connections。
        instance_path 如 "soc.u_cpu.u_alu"，逐级向上:
          1. 查 cpu 中 u_alu 的 port_connections，将 clk 映射为 cpu 侧信号名
          2. 查 soc 中 u_cpu 的 port_connections，继续映射
        """
        if "." not in instance_path:
            return local_clock

        parts = instance_path.split(".")
        clock_name = local_clock

        # parts = ["soc", "u_cpu", "u_alu"]
        # i=2: parent_path="soc.u_cpu", inst_name="u_alu"
        #   → 找 cpu 模块, 查 u_alu 例化的 port_connections
        # i=1: parent_path="soc", inst_name="u_cpu"
        #   → 找 soc 模块, 查 u_cpu 例化的 port_connections
        for i in range(len(parts) - 1, 0, -1):
            inst_name = parts[i]          # "u_alu", then "u_cpu"
            parent_mod_name = parts[i - 1]  # "cpu", then "soc"
            # 对于非直接子模块（i>1），父模块类型名需要从上层例化链获取
            if i > 1:
                # 查上层模块的 inst.module_type
                grandparent = parts[i - 2] if i >= 2 else None
                gp_mod = self._index_store.get_module(grandparent) if grandparent else None
                if gp_mod:
                    for inst in gp_mod.instances:
                        if inst.instance_name == parent_mod_name:
                            parent_mod_name = inst.module_type
                            break

            parent_mod = self._index_store.get_module(parent_mod_name)
            if parent_mod:
                for inst in parent_mod.instances:
                    if inst.instance_name == inst_name:
                        clock_name = inst.port_connections.get(clock_name, clock_name)
                        break

        return clock_name

    def _is_gated_clock_cell(self, module_type: str) -> bool:
        """检查模块类型是否匹配门控时钟模式"""
        mt_lower = module_type.lower()
        return any(pattern.lower() in mt_lower for pattern in self._gated_patterns)

    # ── 格式化 ──

    def format_text_tree(self, result: ClockTreeResult) -> str:
        """格式化时钟树为 ASCII 文本"""
        lines: list[str] = [
            f"⏰ 时钟域结构: {result.top_module}",
            "═" * 50, "",
        ]

        for i, group in enumerate(result.clock_domains):
            gated_label = ""
            if group.is_gated and group.gating_cell_path:
                gated_label = f" [门控, 通过 {group.gating_cell_path}]"
            lines.append(f"🔹 {group.root_clock_name} ({group.edge})  [{group.module_count} 个模块]{gated_label}")
            lines.append("")

            self._format_domain_tree(group.modules, lines)
            lines.append("")

            if group.all_resets:
                rst_strs = [f"{r.signal} ({r.type}, {r.polarity})" for r in group.all_resets]
                lines.append(f"   复位: {', '.join(rst_strs)}")
                lines.append("")

        # 无时钟模块
        if result.unclocked_modules:
            lines.append(f"⚪ 无时钟模块 ({len(result.unclocked_modules)}):")
            for path in result.unclocked_modules[:10]:
                lines.append(f"   {path}")
            if len(result.unclocked_modules) > 10:
                lines.append(f"   ... 还有 {len(result.unclocked_modules) - 10} 个")

        # 汇总
        gated_count = sum(1 for g in result.clock_domains if g.is_gated)
        clocked_count = sum(g.module_count for g in result.clock_domains)
        lines.append("")
        lines.append("─" * 50)
        lines.append(f"时钟域: {len(result.clock_domains)} | 门控: {gated_count} | "
                     f"时钟模块: {clocked_count} | 无时钟: {len(result.unclocked_modules)}")

        return "\n".join(lines)

    def _format_domain_tree(self, modules: list[ClockModuleInfo],
                            lines: list[str]):
        """将时钟域内模块按层次树格式输出"""
        # 按深度排序，构建父子关系
        sorted_mods = sorted(modules, key=lambda m: (m.depth, m.instance_path))
        entry_map: dict[str, ClockModuleInfo] = {}
        for m in sorted_mods:
            entry_map[m.instance_path] = m

        roots: list[ClockModuleInfo] = []
        children_map: dict[str, list[ClockModuleInfo]] = {}
        for m in sorted_mods:
            if "." in m.instance_path:
                parent_path = m.instance_path.rsplit(".", 1)[0]
                children_map.setdefault(parent_path, []).append(m)
            else:
                roots.append(m)

        def _format_subtree(node: ClockModuleInfo, prefix: str, is_last: bool,
                            show_limit: int = 3):
            connector = "└── " if is_last else "├── "
            gated = " ⚙" if node.is_gated_cell else ""
            lines.append(f"  {prefix}{connector}{node.instance_name} → {node.module_type}"
                        f" [{node.local_clock_signal}]{gated}")

            child_prefix = prefix + ("   " if is_last else "│  ")
            children = children_map.get(node.instance_path, [])
            for j, child in enumerate(children):
                if j >= show_limit:
                    lines.append(f"  {child_prefix}└─ ... 还有 {len(children) - show_limit} 个")
                    break
                _format_subtree(child, child_prefix, j == len(children) - 1)

        for k, root in enumerate(roots):
            _format_subtree(root, "", k == len(roots) - 1)

    def format_mermaid(self, result: ClockTreeResult) -> str:
        """格式化时钟树为 Mermaid flowchart"""
        lines = ["flowchart TD"]

        node_idx = 0

        for gi, group in enumerate(result.clock_domains):
            gated_info = ""
            if group.is_gated:
                gated_info = f" [gated]"
            domain_id = f"CD_{gi}"
            lines.append(f"  subgraph {domain_id}[\"🔹 {group.root_clock_name} "
                        f"({group.edge}){gated_info}\"]")

            # 为域中每个模块创建节点
            sorted_mods = sorted(group.modules, key=lambda m: m.depth)
            path_to_node: dict[str, str] = {}

            for m in sorted_mods:
                nid = f"n{node_idx}"
                node_idx += 1
                gated = " ⚙" if m.is_gated_cell else ""
                lines.append(f"    {nid}[\"{m.instance_name}: {m.module_type} [{m.local_clock_signal}]{gated}\"]")
                path_to_node[m.instance_path] = nid

                # 连接到父节点
                if "." in m.instance_path:
                    parent_path = m.instance_path.rsplit(".", 1)[0]
                    if parent_path in path_to_node:
                        lines.append(f"    {path_to_node[parent_path]} --> {nid}")

            lines.append(f"  end")

        return "\n".join(lines)
