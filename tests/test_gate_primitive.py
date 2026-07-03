"""测试门级原语识别"""

import pytest
from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.instance_extractor import InstanceExtractor


def _find_module_node(tree, src):
    root = tree.root_node()
    for i in range(root.child_count()):
        c = root.child(i)
        if c.kind() == "module_declaration":
            return c
    return root


GATE_AND_SRC = """
module gate_test(input a, input b, output y);
    and u_and (y, a, b);
endmodule
"""

GATE_BUF_SRC = """
module gate_test(input a, output y);
    buf u_buf (y, a);
endmodule
"""

MULTI_GATE_SRC = """
module gate_test(input a, input b, input c, output y1, output y2);
    nand u_nand (y1, a, b);
    nor  u_nor  (y2, b, c);
endmodule
"""


class TestGatePrimitive:
    def test_and_gate(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(GATE_AND_SRC)
        mod = _find_module_node(tree, src)
        insts = extractor.extract_from_module_body(mod, src, "test.v")
        assert len(insts) >= 1
        gate = insts[0]
        assert gate.is_primitive is True
        assert gate.module_type == "and"

    def test_buf_gate(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(GATE_BUF_SRC)
        mod = _find_module_node(tree, src)
        insts = extractor.extract_from_module_body(mod, src, "test.v")
        assert len(insts) >= 1
        gate = insts[0]
        assert gate.is_primitive is True
        assert gate.module_type == "buf"

    def test_multiple_gates(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(MULTI_GATE_SRC)
        mod = _find_module_node(tree, src)
        insts = extractor.extract_from_module_body(mod, src, "test.v")
        gates = [i for i in insts if i.is_primitive]
        assert len(gates) >= 2

    def test_gate_has_instance_name(self):
        extractor = InstanceExtractor()
        tree, src = parse_source(GATE_AND_SRC)
        mod = _find_module_node(tree, src)
        insts = extractor.extract_from_module_body(mod, src, "test.v")
        gate = insts[0]
        assert gate.instance_name != ""
