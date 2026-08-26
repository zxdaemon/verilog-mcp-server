"""
Class 定义提取器 — 提取 class/extends/members/methods，支持 UVM 组件检测
"""

from __future__ import annotations
import logging
from typing import Optional

from .verilog_parser import get_node_text, get_node_line, find_child
from ..database.models import ClassDef

logger = logging.getLogger(__name__)

_UVM_BASE_CLASSES = {
    "uvm_component", "uvm_env", "uvm_agent", "uvm_driver",
    "uvm_monitor", "uvm_sequencer", "uvm_scoreboard",
    "uvm_test", "uvm_subscriber",
    "uvm_object", "uvm_sequence_item", "uvm_sequence",
    "uvm_reg_block", "uvm_reg_adapter", "uvm_reg_predictor",
}

_UVM_UTILS_MACROS = {
    "uvm_component_utils", "uvm_object_utils",
    "uvm_component_param_utils", "uvm_object_param_utils",
}


class ClassExtractor:
    """从 tree-sitter AST 提取 class 定义"""

    def extract_from_source_file(self, tree, source_text: str, file_path: str) -> list[ClassDef]:
        """从 source_file 顶层提取所有 class 定义，并解析 UVM 继承链"""
        classes = []
        root = tree.root_node

        for i in range(root.child_count):
            child = root.child(i)
            if child.type == "class_declaration":
                cls = self._extract_class(child, source_text, file_path)
                if cls:
                    classes.append(cls)

        self._resolve_uvm_components(classes)
        return classes

    # ── 单 class 提取 ──

    def _extract_class(self, node, source_text: str, file_path: str) -> Optional[ClassDef]:
        name = ""
        extends = ""
        type_params: list[str] = []
        member_vars: list[dict] = []
        methods: list[dict] = []
        has_uvm_macro = False

        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type

            if ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "class_type":
                extends = self._parse_class_type(child, source_text, type_params)
            elif ckind == "class_item":
                self._process_class_item(child, source_text, member_vars, methods)
                if self._has_uvm_utils_macro(child):
                    has_uvm_macro = True

        if not name:
            return None

        body_text = get_node_text(node, source_text)

        return ClassDef(
            name=name,
            extends=extends,
            type_params=type_params,
            member_vars=member_vars,
            methods=methods,
            is_uvm_component=(extends in _UVM_BASE_CLASSES) or has_uvm_macro,
            uvm_base_class=extends if extends in _UVM_BASE_CLASSES else "",
            body_text=body_text,
            file_path=file_path,
            line=get_node_line(node),
        )

    # ── class_type 解析 ──

    def _parse_class_type(self, node, source_text: str, type_params: list) -> str:
        """解析 class_type，返回基类名，同时填充 type_params"""
        base_name = ""

        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type

            if ckind == "simple_identifier":
                base_name = get_node_text(child, source_text)
            elif ckind == "parameter_value_assignment":
                self._collect_type_params(child, source_text, type_params)

        return base_name

    def _collect_type_params(self, node, source_text: str, type_params: list):
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "list_of_parameter_value_assignments":
                for j in range(child.child_count):
                    pa = child.child(j)
                    if pa.type == "named_parameter_assignment":
                        ident = find_child(pa, "simple_identifier")
                        if ident:
                            type_params.append(get_node_text(ident, source_text))

    # ── class_item 处理 ──

    def _process_class_item(self, node, source_text: str, member_vars: list, methods: list):
        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type

            if ckind == "class_property":
                self._extract_property(child, source_text, member_vars)
            elif ckind == "class_method":
                self._extract_method(child, source_text, methods)
            elif ckind == "class_item":
                self._process_class_item(child, source_text, member_vars, methods)

    def _has_uvm_utils_macro(self, node) -> bool:
        """检测 class_item 中是否包含 uvm_*_utils 宏"""
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "text_macro_usage":
                macro_name = self._get_macro_name(child)
                if macro_name in _UVM_UTILS_MACROS:
                    return True
        return False

    def _get_macro_name(self, node) -> str:
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "simple_identifier":
                return get_node_text(child, "")
        return ""

    # ── 成员变量 ──

    def _extract_property(self, node, source_text: str, member_vars: list):
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "data_declaration":
                var_info = self._parse_data_declaration(child, source_text)
                if var_info:
                    member_vars.append(var_info)

    def _parse_data_declaration(self, node, source_text: str) -> dict | None:
        dtype = ""
        var_names: list[str] = []

        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "data_type_or_implicit":
                dtype = get_node_text(child, source_text).strip()
            elif child.type == "list_of_variable_decl_assignments":
                for j in range(child.child_count):
                    va = child.child(j)
                    if va.type == "variable_decl_assignment":
                        ident = find_child(va, "simple_identifier")
                        if ident:
                            var_names.append(get_node_text(ident, source_text))

        if var_names:
            return {"name": var_names[0], "type": dtype, "all_names": var_names}
        return None

    # ── 方法提取 ──

    def _extract_method(self, node, source_text: str, methods: list):
        method_info = {
            "name": "",
            "method_type": "function",
            "return_type": "",
            "modifiers": [],
            "parameters": [],
        }

        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type

            if ckind == "method_qualifier":
                method_info["modifiers"].append(get_node_text(child, source_text))
            elif ckind == "function_prototype":
                method_info["method_type"] = "function"
                self._parse_prototype(child, source_text, method_info)
            elif ckind == "task_prototype":
                method_info["method_type"] = "task"
                method_info["return_type"] = ""
                self._parse_prototype(child, source_text, method_info)
            elif ckind == "function_declaration":
                method_info["method_type"] = "function"
                self._parse_func_decl(child, source_text, method_info)
            elif ckind == "task_declaration":
                method_info["method_type"] = "task"
                method_info["return_type"] = ""
                self._parse_func_decl(child, source_text, method_info)
            elif ckind == "class_constructor_declaration":
                method_info["method_type"] = "function"
                method_info["name"] = "new"
                self._parse_constructor(child, source_text, method_info)
            elif ckind == "extern_declaration":
                pass

        if method_info["name"]:
            methods.append(method_info)

    def _parse_prototype(self, node, source_text: str, method_info: dict):
        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type
            if ckind == "data_type_or_void":
                method_info["return_type"] = get_node_text(child, source_text)
            elif ckind == "simple_identifier":
                if not method_info["name"]:
                    method_info["name"] = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                method_info["parameters"] = self._parse_tf_ports(child, source_text)

    def _parse_func_decl(self, node, source_text: str, method_info: dict):
        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type
            if ckind in ("function_body_declaration", "task_body_declaration"):
                self._parse_body_decl(child, source_text, method_info)
            elif ckind == "data_type_or_void":
                method_info["return_type"] = get_node_text(child, source_text)
            elif ckind == "simple_identifier":
                if not method_info["name"]:
                    method_info["name"] = get_node_text(child, source_text)

    def _parse_body_decl(self, node, source_text: str, method_info: dict):
        for i in range(node.child_count):
            child = node.child(i)
            ckind = child.type
            if ckind == "simple_identifier":
                if not method_info["name"]:
                    method_info["name"] = get_node_text(child, source_text)
            elif ckind == "data_type_or_void":
                if not method_info["return_type"]:
                    method_info["return_type"] = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                method_info["parameters"] = self._parse_tf_ports(child, source_text)

    def _parse_constructor(self, node, source_text: str, method_info: dict):
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "class_constructor_arg_list":
                method_info["parameters"] = self._parse_constructor_args(child, source_text)

    def _parse_constructor_args(self, node, source_text: str) -> list[dict]:
        params = []
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "class_constructor_arg":
                pname = ""
                ptype = ""
                for j in range(child.child_count):
                    gc = child.child(j)
                    if gc.type == "tf_port_item":
                        pname, ptype = self._parse_tf_port_item(gc, source_text)
                if pname:
                    params.append({"name": pname, "type": ptype})
        return params

    def _parse_tf_ports(self, node, source_text: str) -> list[dict]:
        params = []
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "tf_port_item":
                pname, ptype = self._parse_tf_port_item(child, source_text)
                if pname:
                    params.append({"name": pname, "type": ptype})
        return params

    def _parse_tf_port_item(self, node, source_text: str) -> tuple[str, str]:
        name = ""
        dtype = ""
        for i in range(node.child_count):
            child = node.child(i)
            if child.type == "data_type_or_implicit":
                dtype = get_node_text(child, source_text).strip()
            elif child.type == "simple_identifier":
                name = get_node_text(child, source_text)
        return name, dtype

    # ── UVM 继承链解析 ──

    def _resolve_uvm_components(self, classes: list[ClassDef]):
        """两遍处理：通过 extends 链解析 UVM 组件"""
        name_map = {c.name: c for c in classes}

        for cls in classes:
            uvm_base = self._find_uvm_base(cls, name_map)
            if uvm_base:
                cls.is_uvm_component = True
                cls.uvm_base_class = uvm_base

    def _find_uvm_base(self, cls: ClassDef, name_map: dict, visited: set | None = None) -> str:
        if visited is None:
            visited = set()
        if cls.name in visited or len(visited) > 20:
            return ""
        visited.add(cls.name)

        if not cls.extends:
            return ""
        if cls.extends in _UVM_BASE_CLASSES:
            return cls.extends
        parent = name_map.get(cls.extends)
        if parent:
            return self._find_uvm_base(parent, name_map, visited)
        return ""
