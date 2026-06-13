"""
Phase 2 — 模块层次树构建引擎 (Hierarchy Tree Builder)

构建模块例化层次结构，支持：
- 递归展开模块例化树
- 循环例化检测
- 例化路径追踪 (e.g. "top.u_cpu.u_alu")
- 获取设计中所有例化实例的扁平列表
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..database.index_store import IndexStore
from ..database.models import ModuleDef, InstanceDef, PortDef


@dataclass
class HierarchyNode:
    """层次树节点"""
    module_name: str                  # 模块名 (如 "alu")
    instance_name: str                # 例化名 (如 "u_alu")，根节点为空字符串
    instance_path: str                # 完整例化路径 (如 "top.u_cpu.u_alu")
    children: list[HierarchyNode] = field(default_factory=list)
    instances: list[InstanceDef] = field(default_factory=list)  # 本模块中的例化声明
    ports: list[PortDef] = field(default_factory=list)          # 本模块的端口
    file_path: str = ""               # 定义文件
    line_start: int = 0
    line_end: int = 0
    is_cycle_ref: bool = False        # 是否为循环引用标记节点
    is_generated: bool = False        # 是否为 generate 展开实例
    generate_info: str = ""           # generate 条件信息

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "instance_name": self.instance_name,
            "instance_path": self.instance_path,
            "is_cycle_ref": self.is_cycle_ref,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "children": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return f"HierarchyNode({self.instance_path}, {len(self.children)} children)"


class HierarchyBuilder:
    """模块层次树构建器"""

    def __init__(self, index_store: IndexStore):
        self._index_store = index_store

    def build_tree(self, top_module: str, max_depth: int = 10,
                   include_elab: bool = True) -> HierarchyNode:
        """
        构建以 top_module 为根的层次树

        优先使用 pyslang elaboration 数据（含 generate 展开），
        无 elaboration 数据时回退到 tree-sitter 索引。

        Args:
            top_module: 顶层模块名
            max_depth: 最大递归深度
            include_elab: 是否优先使用 pyslang elaboration 数据

        Returns:
            HierarchyNode 根节点

        Raises:
            ValueError: 如果顶层模块不存在
        """
        mod = self._index_store.get_module(top_module)
        if not mod:
            raise ValueError(f"模块 '{top_module}' 不存在于索引中")

        # 优先使用 pyslang elaboration 数据
        if include_elab:
            elab_instances = self._index_store.get_elab_instances()
            if elab_instances:
                return self._build_from_elab(top_module, elab_instances, max_depth)

        # 回退到 tree-sitter 索引
        return self._expand(top_module, "", top_module, set(), 0, max_depth)

    def _build_from_elab(
        self,
        top_module: str,
        elab_instances: list,
        max_depth: int,
    ) -> HierarchyNode:
        """从 pyslang elaboration 数据构建层次树"""
        # 构建 parent → children 映射
        children_map: dict[str, list] = {}
        inst_map: dict[str, object] = {}

        for inst in elab_instances:
            parent = inst.parent_module or top_module
            children_map.setdefault(parent, []).append(inst)
            inst_map[inst.hierarchical_path] = inst

        root = HierarchyNode(
            module_name=top_module,
            instance_name="",
            instance_path=top_module,
            file_path=self._index_store.get_module(top_module).file_path if self._index_store.get_module(top_module) else "",
        )

        self._expand_elab(root, top_module, children_map, set(), 0, max_depth)
        return root

    def _expand_elab(
        self,
        node: HierarchyNode,
        module_name: str,
        children_map: dict,
        visited: set[str],
        depth: int,
        max_depth: int,
    ):
        """递归展开 pyslang elaboration 层次"""
        if depth >= max_depth:
            return

        new_visited = visited | {module_name}
        children = children_map.get(module_name, [])

        for inst in children:
            child_path = inst.hierarchical_path
            child_mod_name = inst.module_type

            if child_mod_name in visited:
                node.children.append(HierarchyNode(
                    module_name=child_mod_name,
                    instance_name=inst.instance_name,
                    instance_path=child_path,
                    is_cycle_ref=True,
                ))
                continue

            child_node = HierarchyNode(
                module_name=child_mod_name,
                instance_name=inst.instance_name,
                instance_path=child_path,
                file_path=inst.file_path,
                line_start=inst.line,
            )

            # 标记 generate 展开实例
            if inst.is_generated:
                child_node.is_generated = True
                child_node.generate_info = inst.generate_condition

            self._expand_elab(child_node, child_mod_name, children_map, new_visited, depth + 1, max_depth)
            node.children.append(child_node)

    def _expand(
        self,
        module_name: str,
        instance_name: str,
        instance_path: str,
        visited: set[str],
        depth: int,
        max_depth: int,
    ) -> HierarchyNode:
        """递归展开模块层次"""
        mod = self._index_store.get_module(module_name)

        node = HierarchyNode(
            module_name=module_name,
            instance_name=instance_name,
            instance_path=instance_path,
            instances=list(mod.instances) if mod else [],
            ports=list(mod.ports) if mod else [],
            file_path=mod.file_path if mod else "",
            line_start=mod.line_start if mod else 0,
            line_end=mod.line_end if mod else 0,
        )

        if depth >= max_depth:
            return node

        if not mod:
            return node

        # 标记当前模块为已访问（用于循环检测）
        new_visited = visited | {module_name}

        for inst in mod.instances:
            child_instance_path = f"{instance_path}.{inst.instance_name}" if instance_path else inst.instance_name

            if inst.module_type in visited:
                # 循环引用：创建一个标记节点但不继续展开
                cycle_node = HierarchyNode(
                    module_name=inst.module_type,
                    instance_name=inst.instance_name,
                    instance_path=child_instance_path,
                    is_cycle_ref=True,
                )
                node.children.append(cycle_node)
                continue

            child_mod = self._index_store.get_module(inst.module_type)
            if child_mod:
                child_node = self._expand(
                    module_name=inst.module_type,
                    instance_name=inst.instance_name,
                    instance_path=child_instance_path,
                    visited=new_visited,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
                node.children.append(child_node)
            else:
                # 模块不存在（可能是外部 IP 或未扫描到）
                node.children.append(HierarchyNode(
                    module_name=inst.module_type,
                    instance_name=inst.instance_name,
                    instance_path=child_instance_path,
                    file_path="",
                    is_cycle_ref=False,
                ))

        return node

    def get_all_instances(
        self,
        top_module: str,
        max_depth: int = 10,
    ) -> list[dict]:
        """
        获取指定顶层模块下所有例化的扁平列表（含路径）

        Returns:
            list[dict]: 每个例化的信息，如:
                {"instance_name": "u_alu", "module_type": "alu",
                 "instance_path": "top.u_cpu.u_alu", "depth": 2}
        """
        root = self.build_tree(top_module, max_depth)
        result: list[dict] = []

        def _walk(node: HierarchyNode, depth: int):
            if node.instance_name:  # 跳过根节点
                result.append({
                    "instance_name": node.instance_name,
                    "module_type": node.module_name,
                    "instance_path": node.instance_path,
                    "depth": depth,
                    "file_path": node.file_path,
                    "is_cycle_ref": node.is_cycle_ref,
                    "ports": [p.name for p in node.ports],
                })
            for child in node.children:
                _walk(child, depth + 1)

        _walk(root, 0)
        return result

    def find_instance_path(
        self,
        instance_name: str,
        top_module: str,
    ) -> Optional[str]:
        """
        在层次树中查找指定例化名的完整路径

        注意：如果存在同名例化（在不同层次），只返回第一个匹配
        """
        root = self.build_tree(top_module)

        def _search(node: HierarchyNode) -> Optional[str]:
            if node.instance_name == instance_name:
                return node.instance_path
            for child in node.children:
                result = _search(child)
                if result:
                    return result
            return None

        return _search(root)

    def format_tree_text(
        self,
        top_module: str,
        max_depth: int = 10,
        show_ports: bool = False,
    ) -> str:
        """构建可读的文本层次树"""
        root = self.build_tree(top_module, max_depth)

        lines: list[str] = []
        lines.append(f"📐 模块层次树: {top_module}")
        lines.append("")

        def _format(
            node: HierarchyNode,
            prefix: str = "",
            is_last: bool = True,
            depth: int = 0,
        ):
            if depth == 0:
                # 根节点
                port_info = ""
                if show_ports and node.ports:
                    port_names = ", ".join(f"{p.direction} {p.name}" for p in node.ports)
                    port_info = f"  ports: {port_names}"
                lines.append(f"  {node.module_name}  [{node.file_path}]{port_info}")
                for i, child in enumerate(node.children):
                    _format(child, "", i == len(node.children) - 1, 1)
                return

            connector = "└── " if is_last else "├── "
            extension = "   " if is_last else "│  "

            if node.is_cycle_ref:
                lines.append(f"{prefix}{connector}{node.instance_name} → {node.module_name} ⚠️ (循环引用)")
                return

            gen_tag = ""
            if node.is_generated:
                gen_tag = f" [generate: {node.generate_info}]" if node.generate_info else " [generate]"

            port_info = ""
            if show_ports and node.ports:
                port_names = ", ".join(f"{p.direction} {p.name}" for p in node.ports[:5])
                if len(node.ports) > 5:
                    port_names += f", ... (+{len(node.ports) - 5})"
                port_info = f"  ports: {port_names}"

            lines.append(f"{prefix}{connector}{node.instance_name} → {node.module_name}{gen_tag}{port_info}")

            if node.children:
                for i, child in enumerate(node.children):
                    _format(child, prefix + extension, i == len(node.children) - 1, depth + 1)

        _format(root)
        return "\n".join(lines)
