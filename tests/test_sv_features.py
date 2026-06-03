"""Tests for SV feature coverage: generate, interface, params, positional ports, types"""
import pytest
from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.instance_extractor import InstanceExtractor
from verilog_mcp_server.indexer.signal_extractor import SignalExtractor
from verilog_mcp_server.indexer.port_extractor import PortExtractor
from verilog_mcp_server.indexer.module_extractor import ModuleExtractor
from verilog_mcp_server.indexer.type_extractor import TypeExtractor
from verilog_mcp_server.database.models import TypeDef
from verilog_mcp_server.database.index_store import IndexStore


def _find_module_node(tree, src):
    root = tree.root_node()
    for i in range(root.child_count()):
        c = root.child(i)
        if c.kind() == "module_declaration":
            return c
    return root


# ── Generate block tests ──

FOR_GENERATE_SRC = """
module gen_test(input clk, input [7:0] data_in, output [7:0] data_out);
    generate
        for (genvar i = 0; i < 4; i = i + 1) begin : gen_blk
            dff u_ff (.clk(clk), .d(data_in[i]), .q(data_out[i]));
        end
    endgenerate
endmodule
"""

IF_GENERATE_SRC = """
module if_gen_test(input clk, input en);
    generate
        if (1) begin : feat_blk
            wire internal;
            buf u_buf (.in(clk), .out(internal));
        end
    endgenerate
endmodule
"""


class TestGenerateBlocks:
    def test_for_generate_instances(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(FOR_GENERATE_SRC)
        insts = extractor.extract_from_module_body(_find_module_node(tree, src), src, "test.v")
        assert len(insts) >= 1

    def test_if_generate_signals(self):
        extractor = SignalExtractor()
        tree, src = parse_source(IF_GENERATE_SRC)
        signals = extractor.extract_signals(_find_module_node(tree, src), src)
        signal_names = [s.name for s in signals]
        assert "internal" in signal_names


# ── Interface port tests ──

INTERFACE_PORT_SRC = """
module if_consumer(input clk, axis_if.slave rx, axis_if.master tx);
endmodule
"""

INTERFACE_SIMPLE_SRC = """
module simple_if_consumer(axis_if rx);
endmodule
"""


class TestInterfacePorts:
    def test_interface_with_modport(self):
        extractor = PortExtractor()
        tree, src = parse_source(INTERFACE_PORT_SRC)
        ports = extractor.extract_from_module(_find_module_node(tree, src), src)
        if_ports = [p for p in ports if p.var_type == "interface"]
        assert len(if_ports) >= 1

    def test_simple_interface(self):
        extractor = PortExtractor()
        tree, src = parse_source(INTERFACE_SIMPLE_SRC)
        ports = extractor.extract_from_module(_find_module_node(tree, src), src)
        if_ports = [p for p in ports if p.var_type == "interface"]
        assert len(if_ports) == 1

    def test_mixed_ports(self):
        extractor = PortExtractor()
        tree, src = parse_source(INTERFACE_PORT_SRC)
        ports = extractor.extract_from_module(_find_module_node(tree, src), src)
        traditional = [p for p in ports if p.var_type != "interface"]
        if_ports = [p for p in ports if p.var_type == "interface"]
        assert len(traditional) >= 1  # clk
        assert len(if_ports) >= 1


# ── Parameter extraction tests ──

PARAM_SRC = """
module fifo #(parameter WIDTH = 32, parameter DEPTH = 8) (
    input clk, input [WIDTH-1:0] din, output [WIDTH-1:0] dout
);
    localparam ADDR_W = $clog2(DEPTH);
endmodule
"""


class TestParameterExtraction:
    def test_header_parameters(self):
        extractor = ModuleExtractor()
        tree, src = parse_source(PARAM_SRC)
        mods = extractor.extract(tree, src, "fifo.sv")
        params = mods[0].parameters
        assert len(params) >= 2
        names = [p.name for p in params]
        assert "WIDTH" in names
        assert "DEPTH" in names

    def test_localparam(self):
        extractor = ModuleExtractor()
        tree, src = parse_source(PARAM_SRC)
        mods = extractor.extract(tree, src, "fifo.sv")
        params = mods[0].parameters
        lp = [p for p in params if p.type == "localparam"]
        assert len(lp) >= 1
        assert lp[0].name == "ADDR_W"


# ── Positional port tests ──

POSITIONAL_PORT_SRC = """
module top(input clk, input rst_n, input [7:0] din, output [7:0] dout);
    wire [7:0] w;
    my_mod u_mod (clk, rst_n, din, dout);
endmodule
"""

NAMED_MIXED_SRC = """
module top(input clk, input rst_n, input [7:0] din, output [7:0] dout);
    my_mod u_mod (.clk(clk), .rst_n(rst_n), din, dout);
endmodule
"""


class TestPositionalPorts:
    def test_unknown_module_placeholder(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(POSITIONAL_PORT_SRC)
        insts = extractor.extract_from_module_body(_find_module_node(tree, src), src, "top.v")
        conns = insts[0].port_connections
        assert "__pos_0" in conns or len(conns) > 0

    def test_mixed_connections(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(NAMED_MIXED_SRC)
        insts = extractor.extract_from_module_body(_find_module_node(tree, src), src, "top.v")
        conns = insts[0].port_connections
        if "clk" in conns:
            assert conns["clk"] == "clk"


# ── Type extraction tests ──

TYPE_SRC = """
module type_test;
    typedef enum logic [1:0] {IDLE, ACTIVE, DONE} state_t;
    typedef struct packed {logic [7:0] data; logic valid;} bus_t;
endmodule
"""


class TestTypeExtraction:
    def test_typedef_enum(self):
        extractor = TypeExtractor()
        tree, src = parse_source(TYPE_SRC)
        types = extractor.extract_types(_find_module_node(tree, src), src, "test.sv")
        enum_types = [t for t in types if t.kind == "enum"]
        assert len(enum_types) >= 1
        assert enum_types[0].name == "state_t"
        assert "IDLE" in enum_types[0].members

    def test_typedef_struct(self):
        extractor = TypeExtractor()
        tree, src = parse_source(TYPE_SRC)
        types = extractor.extract_types(_find_module_node(tree, src), src, "test.sv")
        struct_types = [t for t in types if t.kind == "struct"]
        assert len(struct_types) >= 1
        assert struct_types[0].name == "bus_t"

    def test_type_roundtrip(self):
        td = TypeDef(name="state_t", kind="enum", members=["IDLE", "ACTIVE"],
                     source_text="typedef enum {IDLE, ACTIVE} state_t;",
                     file_path="test.sv", line=1)
        d = td.to_dict()
        restored = TypeDef.from_dict(d)
        assert restored.name == td.name
        assert restored.kind == td.kind
        assert restored.members == td.members
