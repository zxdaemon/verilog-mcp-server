"""
pyslang 提取器 — 从 elaboration 结果中提取增强数据

从 pyslang elaborated AST 中提取：
- generate 展开后的实例列表（含完整层次路径）
- 参数求值后的信号位宽
- 完整层次树
"""

from __future__ import annotations

import logging
from typing import Optional

from ..database.models import (
    ElaboratedInstanceDef,
    ResolvedSignalDef,
    ElaborationReport,
)

try:
    import pyslang

    PYSLANG_AVAILABLE = True
except ImportError:
    PYSLANG_AVAILABLE = False
    pyslang = None  # type: ignore

logger = logging.getLogger(__name__)


class PyslangExtractor:
    """从 pyslang elaboration 结果提取增强数据"""

    def extract_elaborated_instances(
        self, design_root: "pyslang.ast.RootSymbol"
    ) -> list[ElaboratedInstanceDef]:
        """提取所有 generate 展开后的实例

        Args:
            design_root: pyslang elaborated design root

        Returns:
            ElaboratedInstanceDef 列表
        """
        instances = []

        def _visit_instance(inst: "pyslang.ast.InstanceSymbol", parent_path: str = ""):
            path = inst.hierarchicalPath or f"{parent_path}.{inst.name}".strip(".")

            # 获取原始 generate 条件信息
            gen_condition = ""
            gen_source = ""
            try:
                if hasattr(inst, "syntax") and inst.syntax:
                    # 尝试获取 generate 条件
                    if hasattr(inst.syntax, "condition"):
                        gen_condition = str(inst.syntax.condition)
                    if hasattr(inst.syntax, "source"):
                        gen_source = str(inst.syntax.source)
            except Exception:
                pass

            instances.append(
                ElaboratedInstanceDef(
                    instance_name=inst.name,
                    module_type=inst.definition.name if inst.definition else "",
                    hierarchical_path=path,
                    parent_module=parent_path.split(".")[-1] if parent_path else "",
                    is_generated="genblk" in path or "[" in path,
                    generate_condition=gen_condition,
                    generate_source=gen_source,
                    file_path="",  # pyslang 不提供展开实例的源文件路径
                    line=0,
                )
            )

            # 递归访问子实例
            for child in inst.body:
                if child.kind.name == "Instance":
                    _visit_instance(child, path)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_generate_block_array(child, path)

        def _visit_generate_block_array(
            gen_array: "pyslang.ast.GenerateBlockArraySymbol", parent_path: str
        ):
            for entry in getattr(gen_array, "entries", []):
                for child in entry:
                    if child.kind.name == "Instance":
                        _visit_instance(child, parent_path)
                    elif child.kind.name == "GenerateBlockArray":
                        _visit_generate_block_array(child, parent_path)
                    elif child.kind.name == "GenerateBlock":
                        _visit_generate_block(child, parent_path)

        def _visit_generate_block(
            gen_block: "pyslang.ast.GenerateBlockSymbol", parent_path: str
        ):
            for child in gen_block:
                if child.kind.name == "Instance":
                    _visit_instance(child, parent_path)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_generate_block_array(child, parent_path)
                elif child.kind.name == "GenerateBlock":
                    _visit_generate_block(child, parent_path)

        for top in design_root.topInstances:
            _visit_instance(top)

        return instances

    def extract_resolved_signals(
        self, design_root: "pyslang.ast.RootSymbol"
    ) -> list[ResolvedSignalDef]:
        """提取参数求值后的信号定义（含实际位宽）

        Args:
            design_root: pyslang elaborated design root

        Returns:
            ResolvedSignalDef 列表
        """
        signals = []

        def _visit_scope(scope: "pyslang.ast.InstanceBodySymbol", module_name: str):
            for child in scope:
                kind = child.kind.name
                if kind == "Net":
                    sig = _make_resolved_signal(child, module_name)
                    if sig:
                        signals.append(sig)
                elif kind == "Variable":
                    sig = _make_resolved_signal(child, module_name)
                    if sig:
                        signals.append(sig)
                elif kind == "Port":
                    sig = _make_resolved_signal(child, module_name)
                    if sig:
                        signals.append(sig)

        def _make_resolved_signal(
            symbol: "pyslang.ast.Symbol", module_name: str
        ) -> Optional[ResolvedSignalDef]:
            try:
                name = symbol.name
                dt = getattr(symbol, "declaredType", None)
                if not dt:
                    return None

                resolved_type = str(dt.type) if dt.type else ""
                bit_width = dt.type.bitWidth if dt.type and hasattr(dt.type, "bitWidth") else 0
                is_signed = dt.type.isSigned if dt.type and hasattr(dt.type, "isSigned") else False

                # 原始文本宽度（从 syntax 获取）
                original_width = ""
                try:
                    if hasattr(symbol, "syntax") and symbol.syntax:
                        rng = getattr(symbol.syntax, "dimensions", None)
                        if rng:
                            original_width = str(rng)
                except Exception:
                    pass

                # 分类信号类型
                var_type = "wire"
                if symbol.kind.name == "Variable":
                    var_type = "reg"
                elif symbol.kind.name == "Net":
                    net_type = getattr(symbol, "netType", None)
                    if net_type:
                        var_type = str(net_type).lower()

                return ResolvedSignalDef(
                    name=name,
                    module_name=module_name,
                    var_type=var_type,
                    original_width=original_width,
                    resolved_width=resolved_type,
                    resolved_bit_width=bit_width,
                    is_signed=is_signed,
                )
            except Exception as e:
                logger.debug(f"处理信号 {getattr(symbol, 'name', '?')} 时出错: {e}")
                return None

        def _visit_instance(inst: "pyslang.ast.InstanceSymbol"):
            module_name = inst.definition.name if inst.definition else inst.name
            _visit_scope(inst.body, module_name)

            for child in inst.body:
                if child.kind.name == "Instance":
                    _visit_instance(child)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_gen_array(child)
                elif child.kind.name == "GenerateBlock":
                    _visit_gen_block(child)

        def _visit_gen_array(gen_array: "pyslang.ast.GenerateBlockArraySymbol"):
            for entry in getattr(gen_array, "entries", []):
                _visit_gen_block(entry)

        def _visit_gen_block(gen_block: "pyslang.ast.GenerateBlockSymbol"):
            for child in gen_block:
                if child.kind.name == "Instance":
                    _visit_instance(child)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_gen_array(child)
                elif child.kind.name == "GenerateBlock":
                    _visit_gen_block(child)

        for top in design_root.topInstances:
            _visit_instance(top)

        return signals

    def extract_hierarchy(
        self, design_root: "pyslang.ast.RootSymbol"
    ) -> dict[str, list[str]]:
        """提取完整层次树（模块 -> 子模块类型列表）

        Args:
            design_root: pyslang elaborated design root

        Returns:
            {module_name: [child_module_type, ...]} 字典
        """
        hierarchy: dict[str, list[str]] = {}

        def _visit_instance(inst: "pyslang.ast.InstanceSymbol"):
            module_name = inst.definition.name if inst.definition else inst.name
            if module_name not in hierarchy:
                hierarchy[module_name] = []

            for child in inst.body:
                if child.kind.name == "Instance":
                    child_type = (
                        child.definition.name if child.definition else child.name
                    )
                    if child_type not in hierarchy[module_name]:
                        hierarchy[module_name].append(child_type)
                    _visit_instance(child)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_gen_array(child, module_name)
                elif child.kind.name == "GenerateBlock":
                    _visit_gen_block(child, module_name)

        def _visit_gen_array(
            gen_array: "pyslang.ast.GenerateBlockArraySymbol", parent_module: str
        ):
            for entry in getattr(gen_array, "entries", []):
                _visit_gen_block(entry, parent_module)

        def _visit_gen_block(
            gen_block: "pyslang.ast.GenerateBlockSymbol", parent_module: str
        ):
            for child in gen_block:
                if child.kind.name == "Instance":
                    child_type = (
                        child.definition.name if child.definition else child.name
                    )
                    if child_type not in hierarchy.get(parent_module, []):
                        hierarchy.setdefault(parent_module, []).append(child_type)
                    _visit_instance(child)
                elif child.kind.name == "GenerateBlockArray":
                    _visit_gen_array(child, parent_module)
                elif child.kind.name == "GenerateBlock":
                    _visit_gen_block(child, parent_module)

        for top in design_root.topInstances:
            _visit_instance(top)

        return hierarchy

    def build_report(
        self,
        design_root: "pyslang.ast.RootSymbol",
        tree_sitter_module_count: int,
        diagnostics: list[dict],
    ) -> ElaborationReport:
        """构建 elaboration 报告

        Args:
            design_root: pyslang elaborated design root
            tree_sitter_module_count: tree-sitter 解析的模块数
            diagnostics: 诊断信息列表

        Returns:
            ElaborationReport
        """
        instances = self.extract_elaborated_instances(design_root)
        signals = self.extract_resolved_signals(design_root)
        hierarchy = self.extract_hierarchy(design_root)

        # 统计 generate 相关实例
        gen_instances = [i for i in instances if i.is_generated]
        non_gen_instances = [i for i in instances if not i.is_generated]

        # 统计参数化模块实例
        param_modules: set[str] = set()
        for inst in instances:
            if inst.module_type:
                param_modules.add(inst.module_type)

        # 统计诊断
        error_count = sum(1 for d in diagnostics if d.get("is_error"))
        warning_count = sum(1 for d in diagnostics if not d.get("is_error"))

        # 顶层模块
        top_modules = [t.name for t in design_root.topInstances]

        return ElaborationReport(
            top_modules=top_modules,
            total_instances=len(instances),
            generated_instances=len(gen_instances),
            non_generated_instances=len(non_gen_instances),
            unique_module_types=len(param_modules),
            resolved_signals=len(signals),
            tree_sitter_module_count=tree_sitter_module_count,
            pyslang_module_count=len(param_modules),
            error_count=error_count,
            warning_count=warning_count,
            diagnostics=diagnostics,
            hierarchy=hierarchy,
        )
