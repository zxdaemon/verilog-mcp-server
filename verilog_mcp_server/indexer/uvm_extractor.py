"""
UVM 模式提取辅助 — 解析 type_id::create(), uvm_config_db::set/get, TLM port 等
"""

from __future__ import annotations
import logging

from .verilog_parser import get_node_text, find_child, recursive_find

logger = logging.getLogger(__name__)

_TLM_PORT_TYPES = {
    "uvm_analysis_port", "uvm_analysis_export", "uvm_analysis_imp",
    "uvm_blocking_put_port", "uvm_blocking_put_export", "uvm_blocking_put_imp",
    "uvm_nonblocking_put_port", "uvm_nonblocking_put_export",
    "uvm_blocking_get_port", "uvm_blocking_get_export",
    "uvm_nonblocking_get_port", "uvm_nonblocking_get_export",
    "uvm_blocking_peek_port", "uvm_blocking_peek_export",
    "uvm_nonblocking_peek_port", "uvm_nonblocking_peek_export",
    "uvm_blocking_master_port", "uvm_blocking_master_export",
    "uvm_nonblocking_master_port", "uvm_nonblocking_master_export",
    "uvm_blocking_slave_port", "uvm_blocking_slave_export",
    "uvm_nonblocking_slave_port", "uvm_nonblocking_slave_export",
    "uvm_blocking_transport_port", "uvm_blocking_transport_export",
    "uvm_nonblocking_transport_port", "uvm_nonblocking_transport_export",
    "uvm_seq_item_pull_port", "uvm_seq_item_pull_export", "uvm_seq_item_pull_imp",
    "uvm_tlm_analysis_fifo",
}


class UvmExtractor:
    """UVM 模式提取器 — 解析 UVM 惯用语法"""

    # ── type_id::create() ──

    def find_create_calls(self, root_node, source_text: str) -> list[dict]:
        """在 AST 中查找所有 type_id::create("name", parent) 调用

        Returns:
            list[dict]: [{instance_name, component_type, parent_handle, line}]
        """
        results = []
        method_calls = recursive_find(root_node, "method_call")

        for mc in method_calls:
            call_body = find_child(mc, "method_call_body")
            if not call_body:
                continue
            call_name = self._get_first_identifier(call_body, source_text)
            if call_name != "create":
                continue

            # 确认是 type_id::create 模式
            if not self._is_type_id_create(mc, source_text):
                continue

            instance_name, component_type, parent_handle = self._parse_create_args(
                mc, source_text)
            if instance_name:
                results.append({
                    "instance_name": instance_name,
                    "component_type": component_type,
                    "parent_handle": parent_handle,
                    "line": mc.start_position().row + 1,
                })

        return results

    def _is_type_id_create(self, method_call_node, source_text: str) -> bool:
        """检查 method_call 是否为 type_id::create 模式"""
        # 在父节点的 children 中查找 ...::type_id 模式
        # method_call 结构: primary(包含 type_id 的 chain) + method_call_body("create")
        primary = find_child(method_call_node, "primary")
        if primary:
            for i in range(primary.child_count()):
                child = primary.child(i)
                if child.kind() == "function_subroutine_call":
                    inner_call = find_child(child, "subroutine_call")
                    if inner_call:
                        inner_method = find_child(inner_call, "method_call")
                        if inner_method:
                            inner_body = find_child(inner_method, "method_call_body")
                            if inner_body:
                                inner_name = self._get_first_identifier(inner_body, source_text)
                                if inner_name == "type_id":
                                    return True
        return False

    def _parse_create_args(self, method_call_node, source_text: str) -> tuple[str, str, str]:
        """解析 create("name", parent) 的参数"""
        instance_name = ""
        component_type = ""
        parent_handle = ""

        # 提取 component_type from ...::type_id 链
        component_type = self._get_type_id_component(method_call_node, source_text)

        # 提取调用参数
        call_body = find_child(method_call_node, "method_call_body")
        if call_body:
            args = find_child(call_body, "list_of_arguments")
            if args:
                arg_list = self._collect_arguments(args, source_text)
                if len(arg_list) >= 1:
                    instance_name = arg_list[0].strip('"')
                if len(arg_list) >= 2:
                    parent_handle = arg_list[1]

        return instance_name, component_type, parent_handle

    def _get_type_id_component(self, method_call_node, source_text: str) -> str:
        """从 method_call 的 primary 链中提取组件类名"""
        primary = find_child(method_call_node, "primary")
        if primary:
            # 遍历 primary 的子节点找到最外层的 hierarchical_identifier
            for i in range(primary.child_count()):
                child = primary.child(i)
                if child.kind() == "function_subroutine_call":
                    inner_call = find_child(child, "subroutine_call")
                    if inner_call:
                        inner_method = find_child(inner_call, "method_call")
                        if inner_method:
                            inner_primary = find_child(inner_method, "primary")
                            if inner_primary:
                                hi = find_child(inner_primary, "hierarchical_identifier")
                                if hi:
                                    return get_node_text(hi, source_text)
        return ""

    # ── uvm_config_db::set/get ──

    def find_config_db_calls(self, root_node, source_text: str) -> list[dict]:
        """查找所有 uvm_config_db#(type)::set/get 调用

        Returns:
            list[dict]: [{type_param, operation, scope, field_name, value_hint, line}]
        """
        results = []
        method_calls = recursive_find(root_node, "method_call")

        for mc in method_calls:
            class_type = find_child(mc, "class_type")
            if not class_type:
                continue

            ct_text = get_node_text(class_type, source_text)
            if not ct_text.startswith("uvm_config_db"):
                continue

            # 提取类型参数
            type_param = ""
            pva = find_child(class_type, "parameter_value_assignment")
            if pva:
                type_param = get_node_text(pva, source_text).strip("()# ")

            # 提取操作名 (set / get)
            call_body = find_child(mc, "method_call_body")
            if not call_body:
                continue
            operation = self._get_first_identifier(call_body, source_text)
            if operation not in ("set", "get"):
                continue

            # 提取参数
            args = find_child(call_body, "list_of_arguments")
            arg_list = self._collect_arguments(args, source_text) if args else []

            scope = ""
            field_name = ""
            value_hint = ""

            if operation == "set":
                if len(arg_list) >= 2:
                    scope = arg_list[1]
                if len(arg_list) >= 3:
                    field_name = arg_list[2].strip('"')
                if len(arg_list) >= 4:
                    value_hint = arg_list[3]
            elif operation == "get":
                if len(arg_list) >= 2:
                    scope = arg_list[1]
                if len(arg_list) >= 3:
                    field_name = arg_list[2].strip('"')
                if len(arg_list) >= 4:
                    value_hint = arg_list[3]

            results.append({
                "type_param": type_param,
                "operation": operation,
                "scope": scope,
                "field_name": field_name,
                "value_hint": value_hint,
                "line": mc.start_position().row + 1,
            })

        return results

    # ── TLM port 声明 ──

    def find_tlm_port_declarations(self, class_node, source_text: str) -> list[dict]:
        """在 class_declaration 中查找 TLM port 声明

        Returns:
            list[dict]: [{port_name, port_type, type_param, line}]
        """
        ports = []
        data_decls = recursive_find(class_node, "data_declaration")

        for dd in data_decls:
            class_type = find_child(dd, "class_type")
            if not class_type:
                # 检查 data_type_or_implicit → data_type → class_type
                dti = find_child(dd, "data_type_or_implicit")
                if dti:
                    dt = find_child(dti, "data_type")
                    if dt:
                        class_type = find_child(dt, "class_type")

            if not class_type:
                continue

            port_type = ""
            for i in range(class_type.child_count()):
                child = class_type.child(i)
                if child.kind() == "simple_identifier":
                    port_type = get_node_text(child, source_text)
                    break

            if port_type not in _TLM_PORT_TYPES:
                continue

            # 提取参数
            type_param = ""
            pva = find_child(class_type, "parameter_value_assignment")
            if pva:
                type_param = get_node_text(pva, source_text).strip("()# ")

            # 提取端口名
            port_name = ""
            lvd = find_child(dd, "list_of_variable_decl_assignments")
            if lvd:
                vda = find_child(lvd, "variable_decl_assignment")
                if vda:
                    ident = find_child(vda, "simple_identifier")
                    if ident:
                        port_name = get_node_text(ident, source_text)

            if port_name:
                ports.append({
                    "port_name": port_name,
                    "port_type": port_type,
                    "type_param": type_param,
                    "line": dd.start_position().row + 1,
                })

        return ports

    # ── TLM connect() 调用 ──

    def find_tlm_connections(self, root_node, source_text: str) -> list[dict]:
        """查找所有 .connect(target) 调用

        Returns:
            list[dict]: [{source_port, target_port, line}]
        """
        results = []
        tf_calls = recursive_find(root_node, "tf_call")

        for tc in tf_calls:
            hi = find_child(tc, "hierarchical_identifier")
            if not hi:
                continue

            full_text = get_node_text(hi, source_text)
            if not full_text.endswith(".connect"):
                continue

            source_port = full_text  # e.g., "agt.mon_ap.connect"
            target_port = ""

            args = find_child(tc, "list_of_arguments")
            if args:
                arg_list = self._collect_arguments(args, source_text)
                if arg_list:
                    target_port = arg_list[0]

            results.append({
                "source_port": source_port,
                "target_port": target_port,
                "line": tc.start_position().row + 1,
            })

        return results

    # ── new() 构造调用 ──

    def find_new_calls(self, root_node, source_text: str) -> list[dict]:
        """查找所有 new("name", parent) 构造调用

        Returns:
            list[dict]: [{instance_name, component_type, parent_handle, line}]
        """
        results = []
        class_news = recursive_find(root_node, "class_new")

        for cn in class_news:
            args = find_child(cn, "list_of_arguments")
            arg_list = self._collect_arguments(args, source_text) if args else []

            instance_name = ""
            parent_handle = ""
            if len(arg_list) >= 1:
                instance_name = arg_list[0].strip('"')
            if len(arg_list) >= 2:
                parent_handle = arg_list[1]

            results.append({
                "instance_name": instance_name,
                "component_type": "",
                "parent_handle": parent_handle,
                "line": cn.start_position().row + 1,
            })

        return results

    # ── 辅助方法 ──

    @staticmethod
    def _get_first_identifier(node, source_text: str) -> str:
        for i in range(node.child_count()):
            child = node.child(i)
            if child.kind() == "simple_identifier":
                return get_node_text(child, source_text)
        return ""

    @staticmethod
    def _collect_arguments(args_node, source_text: str) -> list[str]:
        values = []
        if not args_node:
            return values
        for i in range(args_node.child_count()):
            child = args_node.child(i)
            if child.kind() == "expression":
                values.append(get_node_text(child, source_text))
        return values
