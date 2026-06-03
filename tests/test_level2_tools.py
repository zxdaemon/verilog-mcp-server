"""测试 Level 2 工具的业务逻辑函数"""

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import ModuleDef, PortDef, InstanceDef
from verilog_mcp_server.tools.level2_relation import (
    _do_trace_signal, _do_where_used, _do_instance_connections,
    _do_hierarchy_tree, _do_hierarchy_instances,
)
from verilog_mcp_server.database.errors import AnalysisError


def make_nested_store() -> IndexStore:
    """创建带层次结构的测试 IndexStore"""
    store = IndexStore()

    store.add_module(ModuleDef(
        name="adder", file_path="adder.v", line_start=1, line_end=10,
        ports=[PortDef(name="a", direction="input"), PortDef(name="b", direction="input"),
               PortDef(name="sum", direction="output")],
    ))
    store.add_module(ModuleDef(
        name="counter", file_path="counter.v", line_start=1, line_end=20,
        ports=[PortDef(name="clk", direction="input"), PortDef(name="count", direction="output", var_type="reg")],
    ))
    store.add_module(ModuleDef(
        name="top", file_path="top.v", line_start=1, line_end=50,
        ports=[PortDef(name="clk", direction="input"), PortDef(name="result", direction="output")],
        instances=[
            InstanceDef(module_type="adder", instance_name="u_adder",
                        port_connections={"a": "data_a", "b": "data_b", "sum": "sum_result"},
                        file_path="top.v", line=30),
            InstanceDef(module_type="counter", instance_name="u_counter",
                        port_connections={"clk": "clk", "count": "counter_val"},
                        file_path="top.v", line=35),
        ],
    ))
    return store


class TestDoWhereUsed:
    def test_where_used_module(self):
        store = make_nested_store()
        results = _do_where_used(store, "adder", "module")
        assert len(results) >= 1

    def test_where_used_module_not_found(self):
        store = make_nested_store()
        results = _do_where_used(store, "nonexistent", "module")
        assert len(results) == 0

    def test_invalid_target_type(self):
        store = make_nested_store()
        try:
            _do_where_used(store, "adder", "invalid")
            assert False, "should have raised"
        except AnalysisError:
            pass


class TestDoHierarchyTree:
    def test_build_tree(self):
        store = make_nested_store()
        tree = _do_hierarchy_tree(store, "top", max_depth=3)
        assert "top" in tree
        assert "adder" in tree or "u_adder" in tree

    def test_instance_connections(self):
        store = make_nested_store()
        details = _do_instance_connections(store, "u_adder", "top")
        assert len(details) >= 1

    def test_hierarchy_instances(self):
        store = make_nested_store()
        instances = _do_hierarchy_instances(store, "top", max_depth=3)
        assert len(instances) >= 2
