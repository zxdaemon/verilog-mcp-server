"""测试 SignalExtractor"""

from verilog_mcp_server.indexer.verilog_parser import parse_source, find_child
from verilog_mcp_server.indexer.signal_extractor import SignalExtractor

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
        if node.type == "module_declaration":
            header = find_child(node, "module_ansi_header")
            if header:
                for i in range(header.child_count):
                    child = header.child(i)
                    if child.type == "simple_identifier":
                        from verilog_mcp_server.indexer.verilog_parser import get_node_text
                        if get_node_text(child, src) == module_name:
                            return node
        for i in range(node.child_count):
            result = search(node.child(i))
            if result:
                return result
        return None
    return search(tree.root_node)


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


def test_extract_drivers_and_loads():
    """VMS-17 回归：always 型 drivers/loads 提取

    根因：过程赋值左值在本 grammar（tree-sitter-language-pack systemverilog）
    为 variable_lvalue，旧实现只认 net_lvalue → LHS 恒空 → always 型
    drivers/loads 全库零产出（assign 型不受影响）。
    """
    se = SignalExtractor()
    tree, _lang = parse_source(MODULE_WITH_SIGNALS)
    mod = _find_module_node(tree, "test_signals", MODULE_WITH_SIGNALS)
    drivers, loads = se.extract_drivers_and_loads(mod, MODULE_WITH_SIGNALS, "t.v")

    # reg counter 被 always 块 nonblocking 赋值驱动（修复前 0 条）
    counter_drvs = [d for d in drivers.get("counter", []) if d.type == "always_block"]
    assert len(counter_drvs) >= 1

    # wire result 由 assign 驱动、internal 为其 RHS load（既有行为不回归）
    assert any(d.type == "assign" for d in drivers.get("result", []))
    assert any(l.type == "assign" for l in loads.get("internal", []))

    # 条件信号拿到 if 条件 load（conditional_statement，修复前 if_statement 不命中）
    assert any(l.type == "always_block" and "if" in l.target
               for l in loads.get("rst_n", []))
    assert any(l.type == "always_block" for l in loads.get("enable", []))
