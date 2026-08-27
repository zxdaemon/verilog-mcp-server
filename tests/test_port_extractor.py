"""测试 PortExtractor"""

from verilog_mcp_server.indexer.verilog_parser import parse_source, find_child
from verilog_mcp_server.indexer.port_extractor import PortExtractor


ANSI_PORTS = """
module mymod (
    input wire clk,
    input wire rst_n,
    input wire [31:0] data_in,
    output reg [31:0] data_out,
    output wire valid
);
    always @(posedge clk) data_out <= data_in;
    assign valid = 1'b1;
endmodule
"""


def test_extract_ansi_ports():
    extractor = PortExtractor()
    tree, src = parse_source(ANSI_PORTS)
    # Find the module_declaration node
    module_node = _find_module_node(tree, "mymod", src)
    assert module_node is not None

    ports = extractor.extract_from_module(module_node, src)
    assert len(ports) == 5

    port_map = {p.name: p for p in ports}
    assert port_map["clk"].direction == "input"
    assert port_map["rst_n"].direction == "input"
    assert port_map["data_in"].width_range == "[31:0]"
    assert port_map["data_out"].direction == "output"
    assert port_map["data_out"].var_type == "reg"
    assert port_map["valid"].direction == "output"
    assert port_map["valid"].var_type == "wire"


def test_no_ports_module():
    extractor = PortExtractor()
    tree, src = parse_source("module empty(); endmodule")
    module_node = _find_module_node(tree, "empty", src)
    ports = extractor.extract_from_module(module_node, src)
    assert len(ports) == 0


def _find_module_node(tree, module_name, src):
    """Helper: find module_declaration node by name"""
    from verilog_mcp_server.indexer.verilog_parser import get_node_text

    def search(node):
        if node.type == "module_declaration":
            # Try ANSI header first
            header = find_child(node, "module_ansi_header")
            if header:
                for i in range(header.child_count):
                    child = header.child(i)
                    if child.type == "simple_identifier":
                        if get_node_text(child, src) == module_name:
                            return node
            # Try non-ANSI header
            header = find_child(node, "module_nonansi_header")
            if header:
                for i in range(header.child_count):
                    child = header.child(i)
                    if child.type == "simple_identifier":
                        if get_node_text(child, src) == module_name:
                            return node
            # Fallback: recursive search for simple_identifier anywhere under module_declaration
            for i in range(node.child_count):
                child = node.child(i)
                if child.type == "simple_identifier":
                    if get_node_text(child, src) == module_name:
                        return node
        for i in range(node.child_count):
            result = search(node.child(i))
            if result:
                return result
        return None
    return search(tree.root_node)
