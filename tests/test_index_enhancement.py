"""
Tests for index-layer-enhancement extractors:
non-ansi ports, package/import, SVA, macros, filelist, testbench detection
"""

import pytest
import tempfile
import os
from pathlib import Path

from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.port_extractor import PortExtractor
from verilog_mcp_server.indexer.package_extractor import PackageExtractor
from verilog_mcp_server.indexer.sva_extractor import SvaExtractor
from verilog_mcp_server.indexer.macro_extractor import MacroExtractor
from verilog_mcp_server.indexer.filelist_parser import FilelistParser
from verilog_mcp_server.indexer.signal_extractor import SignalExtractor
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, PackageImportDef, SvaDef, MacroDef, ConditionalBranch
)


def _find_node(node, kind, depth=10):
    if depth < 0:
        return None
    if node.kind() == kind:
        return node
    for i in range(node.child_count()):
        r = _find_node(node.child(i), kind, depth - 1)
        if r:
            return r
    return None


# ── 8.1 Non-ANSI Port Extraction ──

class TestNonAnsiPorts:
    def test_basic_non_ansi_ports(self):
        code = """
module foo(a, b, c, d);
  output [7:0] a;
  wire [7:0] a;
  input b;
  input [3:0] c;
  output reg [31:0] d;
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        ports = PortExtractor().extract_from_module(mod, code)

        assert len(ports) == 4
        a = ports[0]
        assert a.direction == "output" and a.width_range == "[7:0]" and a.var_type == "wire"
        b = ports[1]
        assert b.direction == "input" and b.width_range is None
        d = ports[3]
        assert d.direction == "output" and d.width_range == "[31:0]" and d.var_type == "reg"

    def test_non_ansi_signed_port(self):
        code = """
module bar(clk, result);
  input clk;
  output signed [15:0] result;
  wire signed [15:0] result;
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        ports = PortExtractor().extract_from_module(mod, code)
        result = ports[1]
        assert result.signed == True
        assert result.width_range == "[15:0]"

    def test_ansi_non_ansi_parity(self):
        """ANSI and non-ANSI ports should have same field completeness"""
        ansi_code = "module ansi_m(input clk, output reg [7:0] out); endmodule"
        nonansi_code = """
module nonansi_m(clk, out);
  input clk;
  output reg [7:0] out;
endmodule
"""
        ext = PortExtractor()

        tree1, _ = parse_source(ansi_code)
        mod1 = _find_node(tree1.root_node(), "module_declaration")
        ports1 = ext.extract_from_module(mod1, ansi_code)

        tree2, _ = parse_source(nonansi_code)
        mod2 = _find_node(tree2.root_node(), "module_declaration")
        ports2 = ext.extract_from_module(mod2, nonansi_code)

        for p1, p2 in zip(ports1, ports2):
            assert p1.direction == p2.direction
            assert p1.var_type == p2.var_type
            assert p1.width_range == p2.width_range


# ── 8.2 Package/Import Extraction ──

class TestPackageExtractor:
    def test_wildcard_import(self):
        code = "module m; import my_pkg::*; endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        imports = PackageExtractor().extract_imports_from_module(mod, code)
        assert len(imports) == 1
        assert imports[0].package == "my_pkg"
        assert imports[0].wildcard == True
        assert imports[0].symbol == "*"

    def test_specific_symbol_import(self):
        code = "module m; import my_pkg::my_type; endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        imports = PackageExtractor().extract_imports_from_module(mod, code)
        assert len(imports) == 1
        assert imports[0].package == "my_pkg"
        assert imports[0].symbol == "my_type"
        assert imports[0].wildcard == False

    def test_multiple_imports(self):
        code = "module m; import pkg_a::*; import pkg_b::helper; endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        imports = PackageExtractor().extract_imports_from_module(mod, code)
        assert len(imports) == 2
        assert imports[0].wildcard == True
        assert imports[1].wildcard == False

    def test_package_with_parameter(self):
        code = "package config_pkg; parameter WIDTH = 32; endpackage"
        tree, _ = parse_source(code)
        pkgs = PackageExtractor().extract_package_defs(tree, code, "test.v")
        assert len(pkgs) == 1
        assert pkgs[0].name == "config_pkg"
        assert len(pkgs[0].parameters) == 1
        assert pkgs[0].parameters[0].name == "WIDTH"
        assert pkgs[0].parameters[0].default_value == "32"

    def test_import_roundtrip(self):
        imp = PackageImportDef(package="pkg", symbol="*", wildcard=True)
        d = imp.to_dict()
        imp2 = PackageImportDef.from_dict(d)
        assert imp2.package == "pkg"
        assert imp2.wildcard == True


# ── 8.3 SVA Assertion Extraction ──

class TestSvaExtractor:
    def test_concurrent_assert_property(self):
        code = """
module m(input clk, req, ack);
  assert property (@(posedge clk) req |=> ack);
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        assertions = SvaExtractor().extract_from_module(mod, code)
        conc = [a for a in assertions if a.type == "concurrent"]
        assert len(conc) == 1
        assert conc[0].keyword == "assert"
        assert "req |=> ack" in conc[0].property
        assert "posedge clk" in conc[0].clock

    def test_immediate_assert(self):
        code = """
module m(input req, ack);
  always @(*) begin
    assert (req && ack) else $error("protocol violation");
  end
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        assertions = SvaExtractor().extract_from_module(mod, code)
        imm = [a for a in assertions if a.type == "immediate"]
        assert len(imm) == 1
        assert imm[0].keyword == "assert"
        assert imm[0].expression == "req && ack"

    def test_sequence_declaration(self):
        code = """
module m;
  sequence handshake;
    req ##1 ack;
  endsequence
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        assertions = SvaExtractor().extract_from_module(mod, code)
        seq = [a for a in assertions if a.type == "sequence"]
        assert len(seq) == 1
        assert seq[0].name == "handshake"
        assert "req ##1 ack" in seq[0].body

    def test_immediate_assume(self):
        code = """
module m(input valid);
  always @(*) begin
    assume (valid);
  end
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        assertions = SvaExtractor().extract_from_module(mod, code)
        imm = [a for a in assertions if a.type == "immediate"]
        assert len(imm) == 1
        assert imm[0].keyword == "assume"

    def test_sva_roundtrip(self):
        sva = SvaDef(type="concurrent", keyword="assert",
                     property="req |=> ack", clock="@(posedge clk)")
        d = sva.to_dict()
        sva2 = SvaDef.from_dict(d)
        assert sva2.type == "concurrent"
        assert sva2.keyword == "assert"
        assert sva2.property == "req |=> ack"


# ── 8.4 Macro Extraction ──

class TestMacroExtractor:
    def test_simple_value_macro(self):
        code = "`define WIDTH 32"
        tree, _ = parse_source(code)
        defines = MacroExtractor().extract_defines(tree, code, "test.v")
        assert len(defines) == 1
        assert defines[0].name == "WIDTH"
        assert defines[0].params == []
        assert defines[0].value == "32"

    def test_parameterized_macro(self):
        code = "`define MAX(a,b) ((a) > (b) ? (a) : (b))"
        tree, _ = parse_source(code)
        defines = MacroExtractor().extract_defines(tree, code, "test.v")
        assert defines[0].name == "MAX"
        assert defines[0].params == ["a", "b"]

    def test_ifdef_else_endif(self):
        code = """
`ifdef SIMULATION
  initial $display("sim");
`else
  wire clk;
`endif
"""
        tree, _ = parse_source(code)
        branches = MacroExtractor().extract_conditionals(tree, code)
        assert len(branches) == 1
        assert branches[0].branch_type == "ifdef"
        assert branches[0].condition == "SIMULATION"
        assert len(branches[0].children) >= 1
        assert any(c.branch_type == "else" for c in branches[0].children)

    def test_macro_usage_in_module(self):
        code = """
`define WIDTH 32
module m;
  wire [`WIDTH-1:0] data;
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        usages = MacroExtractor().extract_macro_usages(mod, code)
        assert any(u["name"] == "WIDTH" for u in usages)

    def test_macro_roundtrip(self):
        md = MacroDef(name="WIDTH", params=[], value="32")
        d = md.to_dict()
        md2 = MacroDef.from_dict(d)
        assert md2.name == "WIDTH"
        assert md2.value == "32"


# ── 8.5 Filelist Parsing ──

class TestFilelistParser:
    def test_simple_filelist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(f"{tmpdir}/rtl", exist_ok=True)
            f_path = f"{tmpdir}/project.f"
            with open(f_path, "w") as f:
                f.write("""
// comment
+incdir+/path/to/include
-v /path/to/lib.v
-y /path/to/libdir
rtl/module_a.v
rtl/module_b.v
""")
            result = FilelistParser().parse(f_path)
            assert result["incdirs"] == ["/path/to/include"]
            assert result["lib_files"] == ["/path/to/lib.v"]
            assert result["lib_dirs"] == [os.path.normpath("/path/to/libdir")]
            assert len(result["files"]) == 2

    def test_recursive_f_include(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(f"{tmpdir}/rtl", exist_ok=True)
            sub_path = f"{tmpdir}/sub.f"
            with open(sub_path, "w") as f:
                f.write("rtl/module_c.v\n")
            main_path = f"{tmpdir}/main.f"
            with open(main_path, "w") as f:
                f.write(f"rtl/module_a.v\n-f {sub_path}\n")
            result = FilelistParser().parse(main_path)
            assert len(result["files"]) == 2
            assert any("module_c.v" in f for f in result["files"])

    def test_relative_path_resolution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f_path = f"{tmpdir}/project.f"
            with open(f_path, "w") as f:
                f.write("rtl/module_a.v\n")
            result = FilelistParser().parse(f_path)
            expected = os.path.normpath(f"{tmpdir}/rtl/module_a.v")
            assert result["files"] == [expected]


# ── 8.6 Testbench Detection ──

class TestTestbenchDetection:
    def test_rtl_module(self):
        code = "module m(input clk); wire a; assign a = clk; endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        is_tb, has_ns = SignalExtractor().detect_testbench(mod, code)
        assert not is_tb
        assert not has_ns

    def test_initial_block_is_testbench(self):
        code = "module tb; initial $display(\"hello\"); endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        is_tb, has_ns = SignalExtractor().detect_testbench(mod, code)
        assert is_tb

    def test_system_task_non_synth(self):
        code = "module m; always @(*) $display(\"x=%d\", x); endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        is_tb, has_ns = SignalExtractor().detect_testbench(mod, code)
        assert not is_tb
        assert has_ns

    def test_delay_control_non_synth(self):
        code = "module m; always #5 clk = ~clk; endmodule"
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        is_tb, has_ns = SignalExtractor().detect_testbench(mod, code)
        assert not is_tb
        assert has_ns

    def test_force_release_non_synth(self):
        code = """
module m;
  wire sig;
  always @(*) begin
    force sig = 1'b1;
    release sig;
  end
endmodule
"""
        tree, _ = parse_source(code)
        mod = _find_node(tree.root_node(), "module_declaration")
        is_tb, has_ns = SignalExtractor().detect_testbench(mod, code)
        assert not is_tb
        assert has_ns


# ── 8.7 ModuleDef extended fields ──

class TestModuleDefExtended:
    def test_new_fields_default(self):
        mod = ModuleDef(name="test", file_path="test.v")
        assert mod.package_imports == []
        assert mod.assertions == []
        assert mod.is_testbench == False
        assert mod.has_non_synth_constructs == False

    def test_new_fields_roundtrip(self):
        mod = ModuleDef(
            name="test", file_path="test.v",
            package_imports=[PackageImportDef(package="pkg")],
            assertions=[SvaDef(type="immediate", keyword="assert", expression="a && b")],
            is_testbench=True,
            has_non_synth_constructs=False,
        )
        row = mod.to_row()
        mod2 = ModuleDef.from_row(row)
        assert mod2.is_testbench == True
        assert len(mod2.package_imports) == 1
        assert len(mod2.assertions) == 1
