"""
Elaboration 相关 MCP Tools

提供 pyslang elaboration 结果的查询和报告功能
"""

from __future__ import annotations

from ..database.index_store import IndexStore
from ..database.errors import DomainError


def register_tools(mcp, index_store: IndexStore):
    """注册 elaboration 相关 tools"""

    @mcp.tool()
    def rtl_elab_report() -> str:
        """
        获取 pyslang elaboration 报告

        显示 elaboration 摘要：顶层模块、generate 展开实例数、
        参数求值后的信号数、tree-sitter 与 pyslang 模块数量差异、
        诊断信息（错误/警告）等。

        Returns:
            elaboration 摘要报告
        """
        report = index_store.get_elab_report()
        if not report:
            return "暂无 pyslang elaboration 数据。请先运行 rtl_build_index 或 rtl_update_index 构建索引。"

        lines = ["📊 **pyslang Elaboration 报告**\n"]

        # 引用判据（VMS-11 顶层身份 + 缺席报告共用）：tree-sitter 实例条目中出现过的类型
        ts_modules = index_store.get_all_modules()
        referenced_types: set[str] = set()
        for m in ts_modules:
            for inst in m.instances:
                if inst.module_type:
                    referenced_types.add(inst.module_type.lower())

        # 顶层模块身份标注（VMS-11）：配置未设 top_module = 全林展开模式，
        # 顶层实例按「源码是否引用」分两桶——有引用即孤儿根（if/case-generate
        # 死分支、调试结构等被静态源码引用但参数求值后独立展开），无引用即
        # 库单元/死代码根
        if report.top_modules:
            ref_tops = [t for t in report.top_modules if t.lower() in referenced_types]
            unref_tops = [t for t in report.top_modules if t.lower() not in referenced_types]
            lines.append(f"**顶层模块身份**（共 {len(report.top_modules)}）：")
            lines.append(
                f"  ├─ 孤儿根·源码有引用（条件分支死区/调试结构，参数求值后独立展开）: {len(ref_tops)}"
            )
            for t in ref_tops[:15]:
                lines.append(f"  │    {t}")
            if len(ref_tops) > 15:
                lines.append(f"  │    ... 还有 {len(ref_tops) - 15} 个")
            lines.append(f"  └─ 未引用根（库单元/死代码）: {len(unref_tops)}")
            for t in unref_tops[:15]:
                lines.append(f"       {t}")
            if len(unref_tops) > 15:
                lines.append(f"       ... 还有 {len(unref_tops) - 15} 个")

        # 实例统计
        lines.append(f"\n**实例统计**:")
        lines.append(f"  总实例数: {report.total_instances}")
        lines.append(f"  ├─ generate 展开: {report.generated_instances}")
        lines.append(f"  └─ 非 generate: {report.non_generated_instances}")
        lines.append(f"  唯一模块类型: {report.unique_module_types}")

        # 信号统计
        lines.append(f"\n**信号统计**:")
        lines.append(f"  Resolved 信号: {report.resolved_signals}")

        # 模块数量对比
        lines.append(f"\n**模块数量对比**:")
        lines.append(f"  tree-sitter 解析: {report.tree_sitter_module_count}")
        lines.append(f"  pyslang elaboration: {report.pyslang_module_count}")
        diff = report.pyslang_module_count - report.tree_sitter_module_count
        if diff > 0:
            lines.append(f"  差异: +{diff} (generate 展开导致)")
        elif diff < 0:
            lines.append(f"  差异: {diff}")
        else:
            lines.append(f"  差异: 0 (一致)")

        # 诊断信息
        lines.append(f"\n**诊断信息**:")
        lines.append(f"  错误: {report.error_count}")
        lines.append(f"  警告: {report.warning_count}")

        if report.diagnostics:
            lines.append(f"\n**详细诊断**:")
            for d in report.diagnostics[:20]:
                severity = d.get("severity", "unknown")
                loc = d.get("location", "")
                msg = d.get("message", "")
                icon = "🔴" if d.get("is_error") else "⚠️"
                lines.append(f"  {icon} [{severity}] {loc} {msg}")
            if len(report.diagnostics) > 20:
                lines.append(f"  ... 还有 {len(report.diagnostics) - 20} 条诊断")

        # ── 缺席模块报告：声明集 − elab 类型集（VMS-02）──
        elab_types = set(index_store.get_elab_module_types())
        missing = sorted({m.name for m in ts_modules} - elab_types)
        if not elab_types:
            lines.append("\n**缺席模块报告**: elab 无实例数据，不可用")
        elif missing:
            high_risk = [n for n in missing if n.lower() in referenced_types]
            orphans = [n for n in missing if n.lower() not in referenced_types]

            # 每文件首个 error 诊断（首错定位）
            # 诊断 location 的文件部分可能是绝对/相对（pyslang proximate path）形态，
            # 匹配按 路径尾 → 文件名 两级宽松归一
            file_first_error: dict[str, tuple[str, str]] = {}
            for d in (report.diagnostics or []):
                if not d.get("is_error"):
                    continue
                loc = d.get("location", "") or ""
                fpath = loc.rsplit(":", 2)[0] if loc.count(":") >= 2 else loc
                if fpath and fpath not in file_first_error:
                    file_first_error[fpath] = (loc, d.get("message", ""))

            import os as _os

            def _match_first_error(decl_fp: str):
                """按声明文件匹配首个 error：精确尾匹配 → 同名文件兜底"""
                if not decl_fp or not file_first_error:
                    return None
                for f, err in file_first_error.items():
                    if f == decl_fp or f.endswith(decl_fp) or decl_fp.endswith(f):
                        return err
                base = _os.path.basename(decl_fp)
                for f, err in file_first_error.items():
                    if _os.path.basename(f) == base:
                        return err
                return None

            declared_file = {m.name: (m.file_path or "") for m in ts_modules}
            lines.append(
                f"\n**缺席模块报告**（声明 {len(ts_modules)} − elab 类型 {len(elab_types)}"
                f" = 缺席 {len(missing)}；已例化无踪(高危) {len(high_risk)} / 未被引用 {len(orphans)}）"
            )
            lines.append(
                "  口径注: 引用判据取自 tree-sitter 实例条目（generate-case 块内例化"
                "自 2026-10-13 修复起已收集）；残余高危多为参数条件例化未命中"
                "（generate case 分支参数求值未走中——静态上界 vs 求值真值的合法口径差）"
            )
            if high_risk:
                lines.append("  ⚠ 高危（已例化但 elab 无踪——elab 层结论对其静默缺失）:")
                for name in high_risk[:30]:
                    fp = declared_file.get(name, "")
                    err = _match_first_error(fp)
                    if err:
                        loc, msg = err
                        msg_short = (msg[:80] + "...") if len(msg) > 80 else msg
                        lines.append(f"    - {name}  [{fp}]  首错: {loc} {msg_short}")
                    else:
                        lines.append(f"    - {name}  [{fp}]  首错: 无定位")
                if len(high_risk) > 30:
                    lines.append(f"    ... 还有 {len(high_risk) - 30} 个")
            if orphans:
                sample = ", ".join(orphans[:10])
                tail = f" ... 等 {len(orphans)} 个" if len(orphans) > 10 else ""
                lines.append(f"  未被引用例举（孤儿/死代码，正常态）: {sample}{tail}")
        else:
            lines.append("\n✅ 缺席模块检查: 声明模块全部 elab 在踪")

        # 层次概览
        if report.hierarchy:
            lines.append(f"\n**层次概览**:")
            for mod, children in list(report.hierarchy.items())[:10]:
                lines.append(f"  {mod} → {', '.join(children[:5])}")
                if len(children) > 5:
                    lines.append(f"    ... 还有 {len(children) - 5} 个子模块")
            if len(report.hierarchy) > 10:
                lines.append(f"  ... 还有 {len(report.hierarchy) - 10} 个模块")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_elab_instances(module_name: str | None = None, group_by_type: bool = False,
                           limit: int = 0, offset: int = 0) -> str:
        """
        获取 pyslang elaboration 后的实例列表

        Args:
            module_name: 可选，限定模块类型。为 None 时返回所有实例。
            group_by_type: 为 True 时输出模块类型→实例计数聚合表（大输出免落盘）
            limit: 分页大小，0 = 不限
            offset: 分页起点

        Returns:
            elaborated 实例列表（含层次路径和 generate 信息），或聚合计数表
        """
        instances = index_store.get_elab_instances(module_name)
        if not instances:
            scope = f"模块 '{module_name}'" if module_name else "全部"
            return f"未找到 {scope} 的 elaborated 实例数据"

        total = len(instances)

        # 聚合模式：类型 → 计数（VMS-10）
        if group_by_type:
            counts: dict[str, int] = {}
            for inst in instances:
                counts[inst.module_type] = counts.get(inst.module_type, 0) + 1
            lines = [f"elaborated 实例聚合（共 {total} 个 / {len(counts)} 类型）:\n"]
            for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                lines.append(f"  {t}: {c}")
            return "\n".join(lines)

        # 分页模式
        if offset or limit:
            page = instances[offset:offset + limit] if limit else instances[offset:]
            tail = f"\n\n[显示 {len(page)}/{total}（offset={offset}, limit={limit or '∞'}）]"
        else:
            page, tail = instances, ""

        lines = [f"找到 {total} 个 elaborated 实例:\n"]
        for inst in page:
            gen_marker = " [generate]" if inst.is_generated else ""
            lines.append(f"### {inst.hierarchical_path}{gen_marker}")
            lines.append(f"  实例名: {inst.instance_name}")
            lines.append(f"  模块类型: {inst.module_type}")
            if inst.parent_module:
                lines.append(f"  父模块: {inst.parent_module}")
            if inst.generate_condition:
                lines.append(f"  generate 条件: {inst.generate_condition}")
            lines.append("")

        return "\n".join(lines) + tail

    @mcp.tool()
    def rtl_resolved_signals(module_name: str) -> str:
        """
        获取模块的参数求值后信号列表

        Args:
            module_name: 模块名

        Returns:
            信号列表（含原始位宽和 resolved 位宽对比）
        """
        signals = index_store.get_resolved_signals(module_name)
        if not signals:
            return f"未找到模块 '{module_name}' 的 resolved 信号数据"

        lines = [f"模块 '{module_name}' 的 resolved 信号 ({len(signals)}):\n"]
        for sig in signals:
            orig = sig.original_width or "(未指定)"
            resolved = sig.resolved_width or "(未知)"
            signed = " signed" if sig.is_signed else ""
            lines.append(
                f"  {sig.name:<20} {sig.var_type}{signed:<8} "
                f"原始: {orig:<12} → resolved: {resolved} ({sig.resolved_bit_width} bit)"
            )

        return "\n".join(lines)
