"""测试 ModuleExtractor"""

from indexer.verilog_parser import parse_source
from indexer.module_extractor import ModuleExtractor


SIMPLE_MODULE = """
module adder (
    input wire [31:0] a,
    input wire [31:0] b,
    output wire [31:0] sum
);
    assign sum = a + b;
endmodule
"""

MULTI_MODULE = """
module simple(input clk, output reg out);
    always @(posedge clk) out <= ~out;
endmodule

module wrapper(input clk, input rst_n, output [7:0] data);
    wire [7:0] internal;
    assign data = internal;
endmodule
"""


def test_extract_single_module():
    extractor = ModuleExtractor()
    tree, src = parse_source(SIMPLE_MODULE)
    modules = extractor.extract(tree, src, "test.v")
    assert len(modules) == 1
    assert modules[0].name == "adder"
    assert modules[0].file_path == "test.v"


def test_extract_multiple_modules():
    extractor = ModuleExtractor()
    tree, src = parse_source(MULTI_MODULE)
    modules = extractor.extract(tree, src, "test.v")
    assert len(modules) == 2
    names = {m.name for m in modules}
    assert names == {"simple", "wrapper"}


def test_extract_empty_file():
    extractor = ModuleExtractor()
    tree, src = parse_source("// just a comment\n")
    modules = extractor.extract(tree, src, "empty.v")
    assert len(modules) == 0
