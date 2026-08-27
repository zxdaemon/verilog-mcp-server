"""Tests for SystemVerilog always_comb/always_ff/always_latch extraction"""
import pytest
from verilog_mcp_server.indexer.signal_extractor import SignalExtractor
from verilog_mcp_server.indexer.verilog_parser import parse_source


def _find_module_node(tree, src):
    """Find the module_declaration node"""
    root = tree.root_node
    for i in range(root.child_count):
        c = root.child(i)
        if c.type == "module_declaration":
            return c
    return root


ALWAYS_COMB_SRC = """
module test_comb(input [7:0] a, input [7:0] b, output reg [7:0] result);
    always_comb begin
        result = a + b;
    end
endmodule
"""

ALWAYS_FF_SRC = """
module test_ff(input clk, input rst_n, input [7:0] din, output reg [7:0] dout);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            dout <= 0;
        else
            dout <= din;
    end
endmodule
"""

ALWAYS_LATCH_SRC = """
module test_latch(input en, input [7:0] d, output reg [7:0] q);
    always_latch begin
        if (en) q <= d;
    end
endmodule
"""


class TestAlwaysComb:
    def test_extract_always_comb(self):
        extractor = SignalExtractor()
        tree, src = parse_source(ALWAYS_COMB_SRC)
        mod_node = _find_module_node(tree, src)
        blocks = extractor.extract_always_blocks(mod_node, src)
        assert len(blocks) == 1
        assert blocks[0].block_type == "combinational"
        assert blocks[0].sensitivity_list == "@*"
        assert len(blocks[0].statements) > 0


class TestAlwaysFF:
    def test_extract_always_ff(self):
        extractor = SignalExtractor()
        tree, src = parse_source(ALWAYS_FF_SRC)
        mod_node = _find_module_node(tree, src)
        blocks = extractor.extract_always_blocks(mod_node, src)
        assert len(blocks) == 1
        assert blocks[0].block_type == "sequential"
        assert "posedge" in blocks[0].sensitivity_list
        assert "rst_n" in blocks[0].sensitivity_list


class TestAlwaysLatch:
    def test_extract_always_latch(self):
        extractor = SignalExtractor()
        tree, src = parse_source(ALWAYS_LATCH_SRC)
        mod_node = _find_module_node(tree, src)
        blocks = extractor.extract_always_blocks(mod_node, src)
        assert len(blocks) == 1
        assert blocks[0].block_type == "latch"
