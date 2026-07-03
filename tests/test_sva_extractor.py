"""测试 SvaExtractor 断言提取"""

import pytest
from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.sva_extractor import SvaExtractor


def _find_module_node(tree, src):
    root = tree.root_node()
    for i in range(root.child_count()):
        c = root.child(i)
        if c.kind() == "module_declaration":
            return c
    return root


CONCURRENT_ASSERT_SRC = """
module sva_test(input clk, input a, input b);
    assert property (@(posedge clk) a |=> b);
endmodule
"""

IMMEDIATE_ASSERT_SRC = """
module sva_test(input a, input b);
    always @(a or b) begin
        assert (a == b) else $error("mismatch");
    end
endmodule
"""

PROPERTY_SEQUENCE_SRC = """
module sva_test(input clk, input a, input b, input c);
    property my_prop;
        @(posedge clk) a |=> b;
    endproperty
    sequence my_seq;
        a ##1 b ##1 c;
    endsequence
endmodule
"""

ASSUME_COVER_SRC = """
module sva_test(input clk, input a, input b);
    assume property (@(posedge clk) a |-> b);
    cover property (@(posedge clk) a ##1 b);
endmodule
"""


class TestConcurrentAssertion:
    def test_basic_concurrent_assert(self):
        extractor = SvaExtractor()
        tree, src = parse_source(CONCURRENT_ASSERT_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        assert len(assertions) >= 1
        concurrent = [a for a in assertions if a.type == "concurrent"]
        assert len(concurrent) >= 1
        assert concurrent[0].keyword == "assert"

    def test_concurrent_assert_has_clock(self):
        extractor = SvaExtractor()
        tree, src = parse_source(CONCURRENT_ASSERT_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        concurrent = [a for a in assertions if a.type == "concurrent"]
        assert concurrent[0].clock != ""


class TestImmediateAssertion:
    def test_immediate_assert(self):
        extractor = SvaExtractor()
        tree, src = parse_source(IMMEDIATE_ASSERT_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        immediate = [a for a in assertions if a.type == "immediate"]
        assert len(immediate) >= 1
        assert "a" in immediate[0].expression

    def test_immediate_assert_has_action(self):
        extractor = SvaExtractor()
        tree, src = parse_source(IMMEDIATE_ASSERT_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        immediate = [a for a in assertions if a.type == "immediate"]
        assert len(immediate) >= 1
        assert "error" in immediate[0].action.lower()


class TestPropertySequence:
    def test_property_decl(self):
        extractor = SvaExtractor()
        tree, src = parse_source(PROPERTY_SEQUENCE_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        props = [a for a in assertions if a.type == "property"]
        assert len(props) == 1
        assert props[0].name == "my_prop"
        assert props[0].body != ""

    def test_sequence_decl(self):
        extractor = SvaExtractor()
        tree, src = parse_source(PROPERTY_SEQUENCE_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        seqs = [a for a in assertions if a.type == "sequence"]
        assert len(seqs) == 1
        assert seqs[0].name == "my_seq"
        assert seqs[0].body != ""
        assert "##1" in seqs[0].body


class TestAssumeCover:
    def test_assume(self):
        extractor = SvaExtractor()
        tree, src = parse_source(ASSUME_COVER_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        assumes = [a for a in assertions if a.keyword == "assume"]
        assert len(assumes) == 1

    def test_cover(self):
        extractor = SvaExtractor()
        tree, src = parse_source(ASSUME_COVER_SRC)
        mod = _find_module_node(tree, src)
        assertions = extractor.extract_from_module(mod, src)
        covers = [a for a in assertions if a.keyword == "cover"]
        assert len(covers) == 1
