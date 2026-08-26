"""
UVM 组件层次构建器 — 从类定义和 create/new 调用构建组件树
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from ..database.models import ClassDef, UvmComponentDef
from ..indexer.uvm_extractor import UvmExtractor

logger = logging.getLogger(__name__)


class UvmHierarchyBuilder:
    """构建 UVM 验证环境组件层次树"""

    def __init__(self, index_store):
        self._index_store = index_store
        self._uvm_extractor = UvmExtractor()

    def build_hierarchy(self, tree, source_text: str, file_path: str,
                        classes: list[ClassDef]) -> list[UvmComponentDef]:
        """构建 UVM 组件层次

        Args:
            tree: tree-sitter AST
            source_text: 源码
            file_path: 文件路径
            classes: 该文件中的所有 ClassDef

        Returns:
            该文件中顶级 UVM 组件的层次定义
        """
        if not classes:
            return []

        # 收集所有 create/new 调用
        create_calls = self._uvm_extractor.find_create_calls(tree.root_node, source_text)
        new_calls = self._uvm_extractor.find_new_calls(tree.root_node, source_text)

        # 建立类名 → ClassDef 映射
        uvm_classes = {c.name: c for c in classes if c.is_uvm_component}

        # 为每个 UVM 组件类构建 UvmComponentDef
        component_map: dict[str, UvmComponentDef] = {}
        for name, cls in uvm_classes.items():
            is_test = (cls.extends == "uvm_test" or cls.uvm_base_class == "uvm_test")
            comp = UvmComponentDef(
                component_type=name,
                instance_name=name,
                is_test=is_test,
                file_path=file_path,
                line=cls.line,
            )
            component_map[name] = comp

        # 解析 create 调用，建立父子关系
        for call in create_calls:
            ctype = call["component_type"]
            iname = call["instance_name"]
            parent = call["parent_handle"]

            if ctype in component_map:
                comp = component_map[ctype]
                comp.instance_name = iname

                if parent and parent != "this":
                    for pcomp in component_map.values():
                        if pcomp.instance_name == parent:
                            pcomp.children.append({
                                "type": ctype,
                                "instance_name": iname,
                            })
                            comp.parent_type = pcomp.component_type
                            comp.parent_instance = parent
                            break
                elif parent == "this":
                    pass  # parent is the enclosing class itself

        # 处理 new 调用作为补充
        for call in new_calls:
            ctype = call["component_type"]
            iname = call["instance_name"]
            parent = call["parent_handle"]

            if ctype in component_map:
                comp = component_map[ctype]
                if not comp.instance_name or comp.instance_name == ctype:
                    comp.instance_name = iname

                if parent and parent != "this":
                    for pcomp in component_map.values():
                        if pcomp.instance_name == parent:
                            already = any(
                                c.get("type") == ctype and c.get("instance_name") == iname
                                for c in pcomp.children
                            )
                            if not already:
                                pcomp.children.append({
                                    "type": ctype,
                                    "instance_name": iname,
                                })
                            break

        return list(component_map.values())

    def get_test_components(self) -> list[UvmComponentDef]:
        """从 index_store 获取所有 UVM test 组件"""
        uvm_classes = self._index_store.get_uvm_component_classes()
        tests = [c for c in uvm_classes if c.extends == "uvm_test"]
        return [
            UvmComponentDef(
                component_type=c.name,
                instance_name=c.name,
                is_test=True,
                file_path=c.file_path,
                line=c.line,
            )
            for c in tests
        ]

    def build_full_tree(self, tree, source_text: str, file_path: str,
                        classes: list[ClassDef]) -> dict | None:
        """构建完整的 UVM 层次树（嵌套 dict 格式）

        Returns:
            {component_type: {instance_name, children: [...]}}
            或 None（如果该文件没有 UVM test 顶层）
        """
        components = self.build_hierarchy(tree, source_text, file_path, classes)
        if not components:
            return None

        # 找到 test 根节点
        roots = [c for c in components if c.is_test]
        if not roots:
            return None

        root = roots[0]

        def _build_node(comp: UvmComponentDef) -> dict:
            return {
                "component_type": comp.component_type,
                "instance_name": comp.instance_name,
                "children": [
                    _build_node(c)
                    for child_item in comp.children
                    for c in components
                    if c.component_type == child_item.get("type")
                    and c.instance_name == child_item.get("instance_name")
                ],
            }

        return _build_node(root)

    def format_hierarchy_text(self, hierarchy: dict, indent: int = 0) -> str:
        """将层次树格式化为文本"""
        lines = []
        prefix = "  " * indent
        ctype = hierarchy.get("component_type", "?")
        iname = hierarchy.get("instance_name", "?")
        lines.append(f"{prefix}{ctype} ({iname})")
        for child in hierarchy.get("children", []):
            lines.append(self.format_hierarchy_text(child, indent + 1))
        return "\n".join(lines)
