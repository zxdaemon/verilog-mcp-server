"""
Tests for cross-hierarchy port dataflow tracing
"""
import pytest

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, SignalDef, InstanceDef, DriverInfo, LoadInfo,
)
from verilog_mcp_server.analysis.fan_out import DataflowTracer


@pytest.fixture
def index_store_with_hierarchy():
    """Create an IndexStore with a 3-level module hierarchy"""
    store = IndexStore()

    # Leaf module: adder
    adder = ModuleDef(
        name="adder",
        file_path="adder.sv",
        line_start=1,
        line_end=10,
        ports=[
            PortDef(name="a", direction="input", var_type="wire"),
            PortDef(name="b", direction="input", var_type="wire"),
            PortDef(name="sum", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(name="sum", var_type="wire", drivers=[
                DriverInfo(type="assign", source="a + b", file_path="adder.sv", line=5),
            ]),
        ],
        assignments=[],
    )
    store.add_module(adder)

    # Middle module: alu (instantiates adder)
    alu = ModuleDef(
        name="alu",
        file_path="alu.sv",
        line_start=1,
        line_end=20,
        ports=[
            PortDef(name="op_a", direction="input", var_type="wire"),
            PortDef(name="op_b", direction="input", var_type="wire"),
            PortDef(name="result", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(name="sum_result", var_type="wire"),
        ],
        instances=[
            InstanceDef(
                module_type="adder",
                instance_name="u_adder",
                port_connections={"a": "op_a", "b": "op_b", "sum": "sum_result"},
                file_path="alu.sv",
                line=10,
            ),
        ],
    )
    store.add_module(alu)

    # Top module: cpu (instantiates alu)
    cpu = ModuleDef(
        name="cpu",
        file_path="cpu.sv",
        line_start=1,
        line_end=30,
        ports=[
            PortDef(name="data_in1", direction="input", var_type="wire"),
            PortDef(name="data_in2", direction="input", var_type="wire"),
            PortDef(name="alu_out", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(name="internal_a", var_type="wire"),
            SignalDef(name="internal_b", var_type="wire"),
            SignalDef(name="internal_result", var_type="wire"),
        ],
        instances=[
            InstanceDef(
                module_type="alu",
                instance_name="u_alu",
                port_connections={
                    "op_a": "internal_a",
                    "op_b": "internal_b",
                    "result": "internal_result",
                },
                file_path="cpu.sv",
                line=15,
            ),
        ],
    )
    store.add_module(cpu)

    return store


class TestTracePortDataflowInput:
    def test_input_port_fan_in(self, index_store_with_hierarchy):
        """Trace input port upward through hierarchy"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("adder", "a", direction="fan_in", max_depth=5)

        assert result.nodes_count >= 1
        assert result.root.signal_name == "a"
        assert result.root.role == "port"

    def test_input_port_crosses_hierarchy(self, index_store_with_hierarchy):
        """input port 'a' in adder is connected to 'op_a' in alu"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("adder", "a", direction="fan_in", max_depth=5)

        # Should find the parent connection
        paths = _collect_paths(result.root)
        # There should be a path going up to alu.op_a
        assert any("alu" in p and "op_a" in p for p in paths)


class TestTracePortDataflowOutput:
    def test_output_port_fan_out(self, index_store_with_hierarchy):
        """Trace output port upward through hierarchy"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("adder", "sum", direction="fan_out", max_depth=5)

        assert result.nodes_count >= 1
        assert result.root.signal_name == "sum"

    def test_output_port_crosses_hierarchy(self, index_store_with_hierarchy):
        """output port 'sum' in adder is connected to 'sum_result' in alu"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("adder", "sum", direction="fan_out", max_depth=5)

        paths = _collect_paths(result.root)
        assert any("alu" in p and "sum_result" in p for p in paths)


class TestTracePortDataflowBoth:
    def test_both_directions(self, index_store_with_hierarchy):
        """Bidirectional tracing"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("alu", "op_a", direction="both", max_depth=5)

        assert result.root.signal_name == "op_a"
        # Should have children from both fan_in and fan_out
        assert len(result.root.children) > 0


class TestTracePortDataflowTopLevel:
    def test_top_level_input(self, index_store_with_hierarchy):
        """Top-level input has no parent"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("cpu", "data_in1", direction="fan_in", max_depth=5)

        # Should mark as top-level
        paths = _collect_paths(result.root)
        assert any("top_level" in p.lower() for p in paths)

    def test_top_level_output(self, index_store_with_hierarchy):
        """Top-level output has no parent"""
        tracer = DataflowTracer(index_store_with_hierarchy)
        result = tracer.trace_port_dataflow("cpu", "alu_out", direction="fan_out", max_depth=5)

        paths = _collect_paths(result.root)
        assert any("top_level" in p.lower() for p in paths)


def _collect_paths(node, current="", depth=0):
    """Collect all path descriptions from trace result"""
    if depth > 20:
        return []
    paths = []
    new_path = f"{current} -> {node.signal_name}@{node.module_name}[{node.role}]"
    paths.append(new_path)
    for child in node.children:
        paths.extend(_collect_paths(child, new_path, depth + 1))
    return paths
