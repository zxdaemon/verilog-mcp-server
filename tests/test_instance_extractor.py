"""测试 InstanceExtractor"""

from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.instance_extractor import InstanceExtractor

MODULE_WITH_INSTANCES = """
module top(input clk, input rst_n, input [31:0] a, input [31:0] b, output [31:0] result);
    wire [31:0] sum;

    adder u_adder (
        .a(a),
        .b(b),
        .sum(sum)
    );

    counter #(.WIDTH(16)) u_counter (
        .clk(clk),
        .rst_n(rst_n),
        .count()
    );
endmodule
"""


def test_extract_instances():
    extractor = InstanceExtractor()
    tree, src = parse_source(MODULE_WITH_INSTANCES)

    instances = extractor.extract_from_module_body(tree.root_node(), src, "top.v")
    assert len(instances) >= 1

    inst_map = {i.instance_name: i for i in instances}
    assert "u_adder" in inst_map
    assert inst_map["u_adder"].module_type == "adder"


def test_port_connections():
    extractor = InstanceExtractor()
    tree, src = parse_source(MODULE_WITH_INSTANCES)

    instances = extractor.extract_from_module_body(tree.root_node(), src, "top.v")
    inst_map = {i.instance_name: i for i in instances}

    if "u_adder" in inst_map:
        conns = inst_map["u_adder"].port_connections
        assert "a" in conns
        assert "b" in conns
        assert "sum" in conns


def test_param_overrides():
    extractor = InstanceExtractor()
    tree, src = parse_source(MODULE_WITH_INSTANCES)

    instances = extractor.extract_from_module_body(tree.root_node(), src, "top.v")
    inst_map = {i.instance_name: i for i in instances}

    if "u_counter" in inst_map:
        params = inst_map["u_counter"].param_overrides
        assert params.get("WIDTH") == "16"


def test_no_instances():
    extractor = InstanceExtractor()
    tree, src = parse_source("module empty(); endmodule")
    instances = extractor.extract_from_module_body(tree.root_node(), src, "empty.v")
    assert len(instances) == 0
