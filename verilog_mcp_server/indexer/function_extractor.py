"""
Function/Method 提取器 — 从 class 和 package 中提取 function/task 方法
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text, get_node_line, find_child
from ..database.models import MethodDef

logger = logging.getLogger(__name__)

_UVM_PHASES = {
    "build_phase", "connect_phase", "end_of_elaboration_phase",
    "start_of_simulation_phase", "run_phase", "main_phase",
    "pre_reset_phase", "reset_phase", "post_reset_phase",
    "pre_configure_phase", "configure_phase", "post_configure_phase",
    "pre_main_phase", "post_main_phase", "shutdown_phase",
    "extract_phase", "check_phase", "report_phase", "final_phase",
}


class FunctionExtractor:
    """从 class 和 package 提取 function/task 方法"""

    def extract_from_class(self, class_node, source_text: str, file_path: str,
                           parent_class: str) -> list[MethodDef]:
        """从 class_declaration AST 节点提取所有方法"""
        methods: list[MethodDef] = []
        for i in range(class_node.child_count()):
            child = class_node.child(i)
            if child.kind() == "class_item":
                self._extract_class_item_methods(child, source_text, file_path,
                                                 parent_class, methods)
        return methods

    def extract_from_package(self, package_node, source_text: str, file_path: str,
                             parent_package: str) -> list[MethodDef]:
        """从 package_declaration AST 节点提取 function/task"""
        methods: list[MethodDef] = []
        for i in range(package_node.child_count()):
            child = package_node.child(i)
            if child.kind() == "package_item":
                for j in range(child.child_count()):
                    item = child.child(j)
                    if item.kind() == "function_declaration":
                        m = self._extract_func(item, source_text, file_path, "function",
                                               parent_package=parent_package)
                        if m:
                            methods.append(m)
                    elif item.kind() == "task_declaration":
                        m = self._extract_func(item, source_text, file_path, "task",
                                               parent_package=parent_package)
                        if m:
                            methods.append(m)
        return methods

    # ── class 内部方法 ──

    def _extract_class_item_methods(self, node, source_text: str, file_path: str,
                                    parent_class: str, methods: list[MethodDef]):
        for i in range(node.child_count()):
            child = node.child(i)
            ckind = child.kind()

            if ckind == "class_method":
                modifiers = self._collect_modifiers(child, source_text)
                for j in range(child.child_count()):
                    inner = child.child(j)
                    ikind = inner.kind()
                    if ikind == "function_declaration":
                        m = self._extract_func(inner, source_text, file_path, "function",
                                               parent_class=parent_class, modifiers=modifiers)
                        if m:
                            methods.append(m)
                    elif ikind == "task_declaration":
                        m = self._extract_func(inner, source_text, file_path, "task",
                                               parent_class=parent_class, modifiers=modifiers)
                        if m:
                            methods.append(m)
                    elif ikind == "function_prototype":
                        m = self._extract_prototype(inner, source_text, file_path, "function",
                                                    parent_class, modifiers)
                        if m:
                            methods.append(m)
                    elif ikind == "task_prototype":
                        m = self._extract_prototype(inner, source_text, file_path, "task",
                                                    parent_class, modifiers)
                        if m:
                            methods.append(m)
                    elif ikind == "class_constructor_declaration":
                        m = self._extract_constructor(inner, source_text, file_path,
                                                      parent_class, modifiers)
                        if m:
                            methods.append(m)
            elif ckind == "class_item":
                self._extract_class_item_methods(child, source_text, file_path,
                                                 parent_class, methods)

    # ── 核心解析 ──

    def _extract_func(self, node, source_text: str, file_path: str,
                      method_type: str, parent_class: str = "", parent_package: str = "",
                      modifiers: list[str] | None = None) -> MethodDef | None:
        name = ""
        return_type = ""
        parameters: list[dict] = []

        for i in range(node.child_count()):
            child = node.child(i)
            ckind = child.kind()

            if ckind in ("function_body_declaration", "task_body_declaration"):
                name, return_type, parameters = self._parse_body_decl(child, source_text)
            elif ckind == "data_type_or_void":
                return_type = get_node_text(child, source_text)
            elif ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                parameters = self._parse_tf_ports(child, source_text)

        if not name:
            return None

        if modifiers is None:
            modifiers = []
        if method_type == "function" and "automatic" not in modifiers:
            # check if 'automatic' keyword is present
            for i in range(node.child_count()):
                child = node.child(i)
                if child.kind() == "automatic":
                    modifiers.append("automatic")
                    break

        body = get_node_text(node, source_text)
        is_phase, phase_name = self._check_uvm_phase(name)

        return MethodDef(
            name=name,
            method_type=method_type,
            return_type=return_type,
            parameters=parameters,
            modifiers=modifiers,
            is_uvm_phase=is_phase,
            uvm_phase_name=phase_name,
            parent_class=parent_class,
            parent_package=parent_package,
            body=body,
            file_path=file_path,
            line=get_node_line(node),
        )

    def _extract_prototype(self, node, source_text: str, file_path: str,
                           method_type: str, parent_class: str,
                           modifiers: list[str]) -> MethodDef | None:
        name = ""
        return_type = ""
        parameters: list[dict] = []

        for i in range(node.child_count()):
            child = node.child(i)
            ckind = child.kind()

            if ckind == "data_type_or_void":
                return_type = get_node_text(child, source_text)
            elif ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                parameters = self._parse_tf_ports(child, source_text)

        if not name:
            return None

        is_phase, phase_name = self._check_uvm_phase(name)

        return MethodDef(
            name=name,
            method_type=method_type,
            return_type=return_type,
            parameters=parameters,
            modifiers=modifiers,
            is_uvm_phase=is_phase,
            uvm_phase_name=phase_name,
            parent_class=parent_class,
            body=get_node_text(node, source_text),
            file_path=file_path,
            line=get_node_line(node),
        )

    def _extract_constructor(self, node, source_text: str, file_path: str,
                             parent_class: str, modifiers: list[str]) -> MethodDef | None:
        parameters: list[dict] = []

        for i in range(node.child_count()):
            child = node.child(i)
            if child.kind() == "class_constructor_arg_list":
                parameters = self._parse_constructor_args(child, source_text)

        return MethodDef(
            name="new",
            method_type="function",
            return_type="",
            parameters=parameters,
            modifiers=modifiers,
            is_uvm_phase=False,
            parent_class=parent_class,
            body=get_node_text(node, source_text),
            file_path=file_path,
            line=get_node_line(node),
        )

    def _parse_body_decl(self, node, source_text: str) -> tuple[str, str, list[dict]]:
        name = ""
        return_type = ""
        parameters: list[dict] = []

        for i in range(node.child_count()):
            child = node.child(i)
            ckind = child.kind()
            if ckind == "simple_identifier":
                name = get_node_text(child, source_text)
            elif ckind == "data_type_or_void":
                return_type = get_node_text(child, source_text)
            elif ckind == "tf_port_list":
                parameters = self._parse_tf_ports(child, source_text)

        return name, return_type, parameters

    def _parse_tf_ports(self, node, source_text: str) -> list[dict]:
        ports = []
        for i in range(node.child_count()):
            child = node.child(i)
            if child.kind() == "tf_port_item":
                p = self._parse_port_item(child, source_text)
                if p:
                    ports.append(p)
        return ports

    def _parse_port_item(self, node, source_text: str) -> dict | None:
        direction = "input"
        dtype = ""
        name = ""

        for i in range(node.child_count()):
            child = node.child(i)
            ckind = child.kind()
            if ckind in ("input", "output", "inout", "ref"):
                direction = ckind
            elif ckind == "data_type_or_implicit":
                dtype = get_node_text(child, source_text).strip()
            elif ckind == "simple_identifier":
                name = get_node_text(child, source_text)

        if not name:
            return None
        return {"name": name, "type": dtype, "direction": direction}

    def _parse_constructor_args(self, node, source_text: str) -> list[dict]:
        args = []
        for i in range(node.child_count()):
            child = node.child(i)
            if child.kind() == "class_constructor_arg":
                pname = ""
                ptype = ""
                for j in range(child.child_count()):
                    gc = child.child(j)
                    if gc.kind() == "tf_port_item":
                        p = self._parse_port_item(gc, source_text)
                        if p:
                            pname = p["name"]
                            ptype = p["type"]
                if pname:
                    args.append({"name": pname, "type": ptype})
        return args

    # ── 修饰符 ──

    def _collect_modifiers(self, class_method_node, source_text: str) -> list[str]:
        modifiers = []
        for i in range(class_method_node.child_count()):
            child = class_method_node.child(i)
            if child.kind() == "method_qualifier":
                text = get_node_text(child, source_text).strip()
                if text:
                    modifiers.append(text)
        return modifiers

    # ── UVM phase 检测 ──

    @staticmethod
    def _check_uvm_phase(name: str) -> tuple[bool, str]:
        if name in _UVM_PHASES:
            return True, name
        return False, ""
