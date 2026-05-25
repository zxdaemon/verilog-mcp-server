"""测试 SignalExtractor"""

from indexer.verilog_parser import parse_source, find_child
from indexer.signal_extractor import SignalExtractor

MODULE_WITH_SIGNALS = """
module test_signals (
    input wire clk,
    input wire rst_n,
    output wire [7:0] result
);
    wire [7:0] internal;
    reg [3:0] counter;
    logic enable;

    assign result = internal;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            counter <= 4'h0;
        else if (enable)
            counter <= counter + 1'b1;
    end
endmodule
"""


def _find_module_node(tree, module_name, src):
    """Helper: find module_declaration node by name"""
    def search(node):
        if node.kind() == "module_declaration":
            header = find_child(node, "module_ansi_header")
            if header:
                for i in range(header.child_count()):
                    child = header.child(i)
                    if child.kind() == "simple_identifier":
                        from indexer.verilog_parser import get_node_text
                        if get_node_text(child, src) == module_name:
                            return node
        for i in range(node.child_count()):
            result = search(node.child(i))
            if result:
                return result
        return None
    return search(tree.root_node())


def test_extract_signals():
    extractor = SignalExtractor()
    tree, src = parse_source(MODULE_WITH_SIGNALS)
    mod_node = _find_module_node(tree, "test_signals", src)
    assert mod_node is not None

    signals = extractor.extract_signals(mod_node, src)
    assert len(signals) >= 2  # internal, counter, enable

    sig_names = {s.name for s in signals}
    assert "internal" in sig_names or "counter" in sig_names


def test_extract_assignments():
    extractor = SignalExtractor()
    tree, src = parse_source(MODULE_WITH_SIGNALS)
    mod_node = _find_module_node(tree, "test_signals", src)
    assert mod_node is not None

    assignments = extractor.extract_assignments(mod_node, src, "test.v")
    assert len(assignments) >= 1
    assert any(a.lhs == "result" for a in assignments)


def test_extract_always_blocks():
    extractor = SignalExtractor()
    tree, src = parse_source(MODULE_WITH_SIGNALS)
    mod_node = _find_module_node(tree, "test_signals", src)
    assert mod_node is not None

    always_blocks = extractor.extract_always_blocks(mod_node, src)
    assert len(always_blocks) >= 1
    assert any("posedge clk" in b.sensitivity_list for b in always_blocks)
