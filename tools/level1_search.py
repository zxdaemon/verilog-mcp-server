"""
Level 1 — 搜索型 MCP Tools

提供基础的符号搜索和模块信息检索能力
"""

from __future__ import annotations
from typing import Optional

from database.index_store import IndexStore
from database.errors import ModuleNotFoundError, SignalNotFoundError, DomainError


def _fmt_module_summary(mod) -> str:
    """格式化模块摘要"""
    lines = [f"## {mod.name}"]
    lines.append(f"- 路径: `{mod.file_path}`")
    lines.append(f"- 行号: {mod.line_start}-{mod.line_end}")

    if mod.ports:
        lines.append(f"- 端口 ({len(mod.ports)}):")
        for p in mod.ports:
            width = f" {p.width_range}" if p.width_range else ""
            signed = " signed" if p.signed else ""
            lines.append(f"  - {p.direction} {p.var_type}{signed}{width} {p.name}")

    if mod.parameters:
        lines.append(f"- 参数 ({len(mod.parameters)}):")
        for p in mod.parameters:
            dv = f" = {p.default_value}" if p.default_value else ""
            lines.append(f"  - {p.type} {p.name}{dv}")

    if mod.signals:
        lines.append(f"- 信号 ({len(mod.signals)}):")
        for s in mod.signals[:20]:
            width = f" {s.width_range}" if s.width_range else ""
            signed = " signed" if s.signed else ""
            lines.append(f"  - {s.var_type}{signed}{width} {s.name}")
        if len(mod.signals) > 20:
            lines.append(f"  - ... 还有 {len(mod.signals) - 20} 个信号")

    if mod.instances:
        lines.append(f"- 子模块例化 ({len(mod.instances)}):")
        for i in mod.instances:
            lines.append(f"  - {i.instance_name} → {i.module_type}")

    if mod.always_blocks:
        lines.append(f"- always 块 ({len(mod.always_blocks)}):")
        for a in mod.always_blocks:
            lines.append(f"  - [{a.block_type}] @({a.sensitivity_list})")

    if mod.assignments:
        lines.append(f"- 连续赋值 ({len(mod.assignments)}):")
        for a in mod.assignments[:10]:
            lines.append(f"  - assign {a.lhs} = {a.rhs}")
        if len(mod.assignments) > 10:
            lines.append(f"  - ... 还有 {len(mod.assignments) - 10} 个")

    return "\n".join(lines)


def _fmt_search_module_results(results: list) -> str:
    """格式化模块搜索结果"""
    lines = [f"找到 {len(results)} 个匹配模块:\n"]
    for mod in results:
        port_count = len(mod.ports)
        inst_count = len(mod.instances)
        lines.append(f"### {mod.name}")
        lines.append(f"- 文件: `{mod.file_path}` 行 {mod.line_start}")
        lines.append(f"- 端口: {port_count}, 子模块: {inst_count}")
        lines.append("")
    return "\n".join(lines)


def _do_search_module(index_store: IndexStore, pattern: str) -> list:
    """模糊搜索模块名，返回匹配的 ModuleDef 列表"""
    if index_store.module_count == 0:
        return []
    return index_store.search_modules(pattern)


def _do_get_module(index_store: IndexStore, module_name: str):
    """获取模块定义，找不到时抛出 ModuleNotFoundError"""
    mod = index_store.get_module(module_name)
    if not mod:
        results = index_store.search_modules(module_name)
        if results:
            mod = results[0]
            raise ModuleNotFoundError(module_name)
        raise ModuleNotFoundError(module_name)
    return mod


def _do_search_signal(index_store: IndexStore, signal_name: str,
                      module_name: str | None = None) -> list:
    """搜索信号定义，返回 [(ModuleDef, signal_name), ...]"""
    if index_store.module_count == 0:
        return []
    return index_store.search_signals(signal_name, module_name)


def _fmt_signal_results(results: list) -> str:
    """格式化信号搜索结果"""
    lines = [f"找到 {len(results)} 个匹配信号:\n"]
    for mod, sig_name in results:
        sig = None
        for s in mod.signals:
            if s.name == sig_name:
                sig = s
                break
        port = None
        for p in mod.ports:
            if p.name == sig_name:
                port = p
                break

        if sig:
            width = f" {sig.width_range}" if sig.width_range else ""
            signed = " signed" if sig.signed else ""
            lines.append(f"  {sig_name:<20} ({sig.var_type}{signed}{width})")
            lines.append(f"    {'模块:':<8} {mod.name}")
            lines.append(f"    {'文件:':<8} `{mod.file_path}`")
        elif port:
            width = f" {port.width_range}" if port.width_range else ""
            signed = " signed" if port.signed else ""
            lines.append(f"  {sig_name:<20} ({port.direction} {port.var_type}{signed}{width})")
            lines.append(f"    {'模块:':<8} {mod.name} [端口]")
            lines.append(f"    {'文件:':<8} `{mod.file_path}`")
        else:
            lines.append(f"  {sig_name:<20} (模块 {mod.name})")
            lines.append(f"    {'文件:':<8} `{mod.file_path}`")
        lines.append("")

    return "\n".join(lines)


def _do_get_hierarchy(index_store: IndexStore, module_name: str, max_depth: int = 5) -> str:
    """构建模块层次树"""
    visited = set()

    def _build_tree(mod_name: str, depth: int = 0, indent: str = "") -> list[str]:
        if depth > max_depth:
            return [f"{indent}└─ ... (已达最大深度 {max_depth})"]
        if mod_name in visited:
            return [f"{indent}└─ {mod_name} (循环引用)"]

        mod = index_store.get_module(mod_name)
        if not mod:
            return [f"{indent}└─ {mod_name} (未找到)"]

        visited.add(mod_name)
        lines = []
        if depth == 0:
            lines.append(f"{mod.name}  [{mod.file_path}]")
        else:
            lines.append(f"{indent}└─ {mod.name}")

        children_indent = indent + ("   " if depth == 0 else "│  ")
        for i, inst in enumerate(mod.instances):
            is_last = (i == len(mod.instances) - 1)
            conn_prefix = children_indent + ("└─ " if is_last else "├─ ")

            target_mod = index_store.get_module(inst.module_type)
            if target_mod:
                lines.append(f"{conn_prefix}{inst.instance_name} → {inst.module_type}")
                next_indent = children_indent + ("   " if is_last else "│  ")
                sub_lines = _build_tree(inst.module_type, depth + 1, next_indent)
                if sub_lines:
                    sub_lines[0] = f"{next_indent}├─ {target_mod.name} ({len(target_mod.ports)} ports)"
                    lines.extend(sub_lines[1:])
            else:
                lines.append(f"{conn_prefix}{inst.instance_name} → {inst.module_type} [?]")

        visited.remove(mod_name)
        return lines

    root_mod = index_store.get_module(module_name)
    if not root_mod:
        results = index_store.search_modules(module_name)
        if results:
            module_name = results[0].name
        else:
            raise ModuleNotFoundError(module_name)

    tree_lines = _build_tree(module_name)
    return "\n".join(tree_lines)


def register_tools(mcp, index_store: IndexStore):
    """注册所有 Level 1 搜索型 tools"""

    @mcp.tool()
    def rtl_search_module(pattern: str) -> str:
        """
        模糊搜索模块定义

        Args:
            pattern: 模块名搜索模式（大小写不敏感，支持部分匹配）

        Returns:
            匹配的模块列表（名称、文件路径、端口数）
        """
        results = _do_search_module(index_store, pattern)
        if not results:
            return f"未找到匹配 '{pattern}' 的模块"
        return _fmt_search_module_results(results)

    @mcp.tool()
    def rtl_get_module(module_name: str) -> str:
        """
        获取模块的详细信息

        Args:
            module_name: 模块名（精确匹配）

        Returns:
            模块的完整信息（端口、参数、例化、信号、always、assign）
        """
        try:
            mod = _do_get_module(index_store, module_name)
            return _fmt_module_summary(mod)
        except ModuleNotFoundError:
            results = _do_search_module(index_store, module_name)
            if results:
                mod = results[0]
                return f"未找到精确匹配 '{module_name}'，显示最接近的 '{mod.name}':\n\n" + _fmt_module_summary(mod)
            return f"未找到模块 '{module_name}'"

    @mcp.tool()
    def rtl_module_ports(module_name: str) -> str:
        """
        获取模块端口列表

        Args:
            module_name: 模块名

        Returns:
            端口列表（方向、类型、宽度、名称）
        """
        try:
            mod = _do_get_module(index_store, module_name)
        except ModuleNotFoundError:
            results = _do_search_module(index_store, module_name)
            if results:
                mod = results[0]
            else:
                return f"未找到模块 '{module_name}'"

        if not mod.ports:
            return f"模块 '{mod.name}' 没有端口"

        lines = [f"模块 '{mod.name}' 的端口 ({len(mod.ports)}):\n"]
        for p in mod.ports:
            width = f" [{p.width_range}]" if p.width_range else ""
            signed = " signed" if p.signed else ""
            lines.append(f"  {p.direction:<8} {p.var_type}{signed}{width:<15} {p.name}")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_list_instances(module_name: str) -> str:
        """
        列出模块中所有子模块例化

        Args:
            module_name: 模块名

        Returns:
            例化列表（实例名 → 模块类型，含端口连接数）
        """
        try:
            mod = _do_get_module(index_store, module_name)
        except ModuleNotFoundError:
            results = _do_search_module(index_store, module_name)
            if results:
                mod = results[0]
            else:
                return f"未找到模块 '{module_name}'"

        if not mod.instances:
            return f"模块 '{mod.name}' 没有子模块例化"

        lines = [f"模块 '{mod.name}' 的例化 ({len(mod.instances)}):\n"]
        for i in mod.instances:
            conn_count = len(i.port_connections)
            param_count = len(i.param_overrides)
            lines.append(f"  {i.instance_name:<25} → {i.module_type:<20} ({conn_count} 连接, {param_count} 参数)")
            if i.port_connections:
                lines.append(f"    {'端口连接:':<12} {', '.join(f'{f}={a}' for f, a in list(i.port_connections.items())[:5])}")
                if len(i.port_connections) > 5:
                    lines.append(f"    {'':<12} ... 还有 {len(i.port_connections) - 5} 个连接")
            lines.append(f"    {'文件:':<12} `{i.file_path}` 行 {i.line}")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_search_signal(signal_name: str, module_name: Optional[str] = None) -> str:
        """
        搜索信号定义

        Args:
            signal_name: 信号名（支持部分匹配）
            module_name: 可选，限定搜索范围到指定模块

        Returns:
            信号定义位置及类型信息
        """
        results = _do_search_signal(index_store, signal_name, module_name)
        if not results:
            scope = f" 模块 '{module_name}'" if module_name else ""
            return f"未找到信号 '{signal_name}'{scope}"
        return _fmt_signal_results(results)

    @mcp.tool()
    def rtl_hierarchy(module_name: str, max_depth: int = 5) -> str:
        """
        显示模块例化层次树

        递归展开模块的子模块例化，构建模块层次结构

        Args:
            module_name: 顶层模块名
            max_depth: 最大展开深度（默认 5）

        Returns:
            树状层次结构
        """
        try:
            return _do_get_hierarchy(index_store, module_name, max_depth)
        except ModuleNotFoundError:
            return f"未找到模块 '{module_name}'"
