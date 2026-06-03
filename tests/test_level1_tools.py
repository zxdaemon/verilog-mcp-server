"""测试 Level 1 工具的业务逻辑函数"""

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import ModuleDef, PortDef, InstanceDef, SignalDef
from verilog_mcp_server.database.errors import ModuleNotFoundError
from verilog_mcp_server.tools.level1_search import (
    _do_search_module, _do_get_module, _do_search_signal,
    _do_get_hierarchy, _fmt_module_summary, _fmt_search_module_results,
    _fmt_signal_results,
)


def make_test_store() -> IndexStore:
    """创建带测试数据的 IndexStore"""
    store = IndexStore()
    mod = ModuleDef(
        name="counter", file_path="counter.v", line_start=1, line_end=20,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="rst_n", direction="input"),
            PortDef(name="count", direction="output", var_type="reg", width_range="[15:0]"),
        ],
        signals=[SignalDef(name="internal_wire", var_type="wire")],
        instances=[
            InstanceDef(module_type="adder", instance_name="u_adder",
                        port_connections={"a": "x", "b": "y"}, file_path="counter.v", line=15),
        ],
    )
    store.add_module(mod)
    return store


class TestDoSearchModule:
    def test_exact_match(self):
        store = make_test_store()
        results = _do_search_module(store, "counter")
        assert len(results) == 1
        assert results[0].name == "counter"

    def test_partial_match(self):
        store = make_test_store()
        results = _do_search_module(store, "count")
        assert len(results) >= 1

    def test_no_match(self):
        store = make_test_store()
        results = _do_search_module(store, "nonexistent")
        assert len(results) == 0

    def test_empty_store(self):
        store = IndexStore()
        results = _do_search_module(store, "anything")
        assert results == []


class TestDoGetModule:
    def test_found(self):
        store = make_test_store()
        mod = _do_get_module(store, "counter")
        assert mod.name == "counter"
        assert mod.file_path == "counter.v"

    def test_not_found_raises(self):
        store = make_test_store()
        try:
            _do_get_module(store, "nonexistent")
            assert False, "should have raised"
        except ModuleNotFoundError as e:
            assert "nonexistent" in str(e)


class TestDoSearchSignal:
    def test_search_by_name(self):
        store = make_test_store()
        results = _do_search_signal(store, "clk")
        assert len(results) >= 1

    def test_search_not_found(self):
        store = make_test_store()
        results = _do_search_signal(store, "nonexistent_signal")
        assert len(results) == 0


class TestFormatModuleSummary:
    def test_contains_name(self):
        store = make_test_store()
        mod = store.get_module("counter")
        result = _fmt_module_summary(mod)
        assert "counter" in result
        assert "counter.v" in result


class TestFormatSearchModuleResults:
    def test_format(self):
        store = make_test_store()
        results = _do_search_module(store, "counter")
        output = _fmt_search_module_results(results)
        assert "counter" in output
        assert "counter.v" in output


class TestFormatSignalResults:
    def test_format(self):
        store = make_test_store()
        results = _do_search_signal(store, "clk")
        output = _fmt_signal_results(results)
        assert "clk" in output


class TestDoGetHierarchy:
    def test_build_tree(self):
        store = make_test_store()
        tree = _do_get_hierarchy(store, "counter")
        assert "counter" in tree
        assert "counter.v" in tree

    def test_not_found(self):
        store = IndexStore()
        try:
            _do_get_hierarchy(store, "nonexistent")
            assert False, "should have raised"
        except ModuleNotFoundError:
            pass
