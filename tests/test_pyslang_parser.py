"""
Tests for pyslang parser wrapper
"""
import os
import tempfile

import pytest

from verilog_mcp_server.indexer.pyslang_parser import (
    PyslangParser,
    is_pyslang_available,
    get_pyslang_version,
)


SIMPLE_MODULE = """
module top;
  wire a;
endmodule
"""

MODULE_WITH_GENERATE = """
module child #(parameter WIDTH = 8);
  wire [WIDTH-1:0] data;
endmodule

module top;
  parameter N = 2;
  genvar i;
  generate
    for (i = 0; i < N; i = i + 1) begin : genblk
      child #(16) u_child();
    end
  endgenerate
endmodule
"""

MODULE_WITH_ERROR = """
module top;
  wire [3:0] a;
  wire [7:0] b;
  assign a = b;  // width mismatch warning
endmodule
"""


@pytest.fixture
def rtl_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False) as f:
        f.write(SIMPLE_MODULE)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def generate_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False) as f:
        f.write(MODULE_WITH_GENERATE)
        path = f.name
    yield path
    os.unlink(path)


class TestPyslangAvailability:
    def test_is_available(self):
        assert is_pyslang_available() is True

    def test_version(self):
        version = get_pyslang_version()
        assert version.startswith("11.")


class TestPyslangParserParseFiles:
    def test_parse_single_file(self, rtl_file):
        parser = PyslangParser()
        compilation = parser.parse_files([rtl_file])
        assert compilation is not None

    def test_parse_empty_list(self):
        parser = PyslangParser()
        compilation = parser.parse_files([])
        assert compilation is None

    def test_parse_nonexistent_file(self):
        parser = PyslangParser()
        compilation = parser.parse_files(["/nonexistent/file.sv"])
        assert compilation is None


class TestPyslangParserElaborate:
    def test_elaborate_simple(self, rtl_file):
        parser = PyslangParser()
        compilation = parser.parse_files([rtl_file])
        root = parser.elaborate(compilation)
        assert root is not None
        assert len(root.topInstances) == 1
        assert root.topInstances[0].name == "top"

    def test_elaborate_generate(self, generate_file):
        parser = PyslangParser()
        compilation = parser.parse_files([generate_file])
        root = parser.elaborate(compilation)
        assert root is not None
        assert len(root.topInstances) == 1

    def test_elaborate_none(self):
        parser = PyslangParser()
        root = parser.elaborate(None)
        assert root is None


class TestPyslangParserDiagnostics:
    def test_no_diagnostics_for_clean_file(self, rtl_file):
        parser = PyslangParser()
        compilation = parser.parse_files([rtl_file])
        diags = parser.get_diagnostics(compilation)
        assert isinstance(diags, list)

    def test_width_mismatch_warning(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False) as f:
            f.write(MODULE_WITH_ERROR)
            path = f.name
        try:
            parser = PyslangParser()
            compilation = parser.parse_files([path])
            diags = parser.get_diagnostics(compilation)
            assert len(diags) >= 1
            assert any(d["severity"] == "warning" for d in diags)
        finally:
            os.unlink(path)

    def test_diagnostics_for_none(self):
        parser = PyslangParser()
        diags = parser.get_diagnostics(None)
        assert diags == []


class TestPyslangParserWithOptions:
    def test_with_include_dirs(self, rtl_file):
        parser = PyslangParser(include_dirs=["/tmp", "/usr/include"])
        compilation = parser.parse_files([rtl_file])
        assert compilation is not None

    def test_with_defines(self, rtl_file):
        parser = PyslangParser(defines={"DEBUG": "1", "WIDTH": "32"})
        compilation = parser.parse_files([rtl_file])
        assert compilation is not None

    def test_with_top_module(self, generate_file):
        parser = PyslangParser(top_module="top")
        compilation = parser.parse_files([generate_file])
        root = parser.elaborate(compilation)
        assert root is not None
        assert len(root.topInstances) == 1
        assert root.topInstances[0].name == "top"
