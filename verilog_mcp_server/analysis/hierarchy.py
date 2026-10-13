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
                node = self._build_from_elab(top_module, elab_instances, max_depth)
                if node is not None:
                    return node
                # 该类型在 elab 数据中无实例（未被例化/接口等）→ 回退 tree-sitter

        # 回退到 tree-sitter 索引
        return self._expand(top_module, "", top_module, set(), 0, max_depth)

    def _build_from_elab(
        self,
        top_module: str,
        elab_instances: list,
        max_depth: int,
    ) -> Optional[HierarchyNode]:
        """从 pyslang elaboration 数据构建层次树（VMS-09 路径前缀树）

        修复两缺陷：
        1. 旧实现把所有 parent_module="" 的顶层实例兜底挂到请求的 root 键下
           （``or top_module``）→ 请求子树时整林泄漏；
        2. children_map 按「父实例名」建键、按「模块类型」查——仅实例名与
           类型同名时侥幸命中，其余子树静默截断。

        新实现按 hierarchical_path 前缀关系建树：实例的父 = 其路径剥尾段后
        最近的存在实例路径（中间剥掉的段为 generate 域）。子树根 = 该类型
        的全部 elab 实例（同名多处例化时各自成根）。

        Returns:
            HierarchyNode 根；该类型在 elab 数据中无实例时返回 None（调用方
            回退 tree-sitter 路径）。
        """
        inst_map: dict[str, object] = {i.hierarchical_path: i for i in elab_instances}

        # 实例父路径解析：剥尾段，直到落在某个实例路径上（generate 域段被跳过）
        def _instance_parent(path: str) -> str:
            cur = path.rsplit(".", 1)[0] if "." in path else ""
            while cur and cur not in inst_map:
                cur = cur.rsplit(".", 1)[0] if "." in cur else ""
            return cur

        children_map: dict[str, list] = {}
        for inst in elab_instances:
            p = _instance_parent(inst.hierarchical_path)
            children_map.setdefault(p, []).append(inst)

        # 子树根：该类型的全部 elab 实例（按路径排序保证输出稳定）
        roots = sorted(
            (i for i in elab_instances if i.module_type == top_module),
            key=lambda i: i.hierarchical_path,
        )
        if not roots:
            return None

        def _make_node(inst) -> HierarchyNode:
            node = HierarchyNode(
                module_name=inst.module_type,
                instance_name=inst.instance_name,
                instance_path=inst.hierarchical_path,
                file_path=inst.file_path,
                line_start=inst.line,
            )
            if inst.is_generated:
                node.is_generated = True
                node.generate_info = inst.generate_condition
            return node

        if len(roots) == 1:
            root = _make_node(roots[0])
            root.instance_name = ""  # 根节点不计入扁平例化列表
            self._expand_elab_path(root, roots[0].hierarchical_path,
                                   children_map, set(), 0, max_depth)
            return root

        # 同名多例化：虚拟根挂多棵子树（子树根实例自身计入扁平列表）
        root = HierarchyNode(
            module_name=top_module,
            instance_name="",
            instance_path=top_module,
            file_path=self._index_store.get_module(top_module).file_path if self._index_store.get_module(top_module) else "",
        )
        for r in roots:
            child = _make_node(r)
            self._expand_elab_path(child, r.hierarchical_path,
                                   children_map, set(), 0, max_depth)
            root.children.append(child)
        return root

    def _expand_elab_path(
        self,
        node: HierarchyNode,
        instance_path: str,
        children_map: dict,
        visited: set[str],
        depth: int,
        max_depth: int,
    ):
        """按实例路径展开子树（children_map 键 = 父实例路径）"""
        if depth >= max_depth:
            return

        new_visited = visited | {node.module_name}
        for inst in children_map.get(instance_path, []):
            if inst.module_type in visited:
                node.children.append(HierarchyNode(
                    module_name=inst.module_type,
                    instance_name=inst.instance_name,
                    instance_path=inst.hierarchical_path,
                    is_cycle_ref=True,
                ))
                continue

            child_node = HierarchyNode(
                module_name=inst.module_type,
                instance_name=inst.instance_name,
                instance_path=inst.hierarchical_path,
                file_path=inst.file_path,
                line_start=inst.line,
            )
            if inst.is_generated:
                child_node.is_generated = True
                child_node.generate_info = inst.generate_condition

            self._expand_elab_path(child_node, inst.hierarchical_path,
                                   children_map, new_visited, depth + 1, max_depth)
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
            # 根节点（depth 0 且无实例名）不计入；数组元素 instance_name 为空串
            # （pyslang 命名唯一可靠源是 hierarchical_path），非根一律入列
            if depth > 0 or node.instance_name:
                result.append({
                    "instance_name": node.instance_name,
                    "module_type": node.module_name,
                    "instance_path": node.instance_path,
                    "depth": depth,
                    "file_path": node.file_path,
                    "is_cycle_ref": node.is_cycle_ref,
                    "is_generated": bool(node.is_generated),
                    "generate_info": node.generate_info or "",
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
