"""
Tests for pyslang extractor
"""
import os
import tempfile

import pytest

from verilog_mcp_server.indexer.pyslang_parser import PyslangParser
from verilog_mcp_server.indexer.pyslang_extractor import PyslangExtractor


MODULE_WITH_GENERATE = """
module child #(parameter WIDTH = 8);
  wire [WIDTH-1:0] data;
endmodule

module top;
  parameter N = 2;
  wire [15:0] bus;
  reg [3:0] cnt;
  genvar i;
  generate
    for (i = 0; i < N; i = i + 1) begin : genblk
      child #(16) u_child();
    end
  endgenerate
endmodule
"""


@pytest.fixture
def design_root():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False) as f:
        f.write(MODULE_WITH_GENERATE)
        path = f.name
    try:
        parser = PyslangParser()
        compilation = parser.parse_files([path])
        root = parser.elaborate(compilation)
        yield root
    finally:
        os.unlink(path)


class TestExtractElaboratedInstances:
    def test_extracts_top_instance(self, design_root):
        extractor = PyslangExtractor()
        instances = extractor.extract_elaborated_instances(design_root)
        assert len(instances) >= 1
        top = [i for i in instances if i.instance_name == "top"]
        assert len(top) == 1
        assert top[0].hierarchical_path == "top"
        assert not top[0].is_generated

    def test_extracts_generated_instances(self, design_root):
        extractor = PyslangExtractor()
        instances = extractor.extract_elaborated_instances(design_root)
        gen = [i for i in instances if i.is_generated]
        assert len(gen) >= 2
        # Check hierarchical paths contain genblk
        for g in gen:
            assert "genblk" in g.hierarchical_path

    def test_instance_has_module_type(self, design_root):
        extractor = PyslangExtractor()
        instances = extractor.extract_elaborated_instances(design_root)
        child_instances = [i for i in instances if i.module_type == "child"]
        assert len(child_instances) >= 2


class TestExtractResolvedSignals:
    def test_extracts_signals(self, design_root):
        extractor = PyslangExtractor()
        signals = extractor.extract_resolved_signals(design_root)
        assert len(signals) >= 3  # bus, cnt, and 2 data signals

    def test_bus_width_resolved(self, design_root):
        extractor = PyslangExtractor()
        signals = extractor.extract_resolved_signals(design_root)
        bus_signals = [s for s in signals if s.name == "bus"]
        assert len(bus_signals) == 1
        assert bus_signals[0].resolved_bit_width == 16

    def test_data_width_resolved(self, design_root):
        extractor = PyslangExtractor()
        signals = extractor.extract_resolved_signals(design_root)
        data_signals = [s for s in signals if s.name == "data"]
        assert len(data_signals) >= 1
        for ds in data_signals:
            assert ds.resolved_bit_width == 16  # overridden by #(16)


class TestExtractHierarchy:
    def test_hierarchy_contains_top(self, design_root):
        extractor = PyslangExtractor()
        hierarchy = extractor.extract_hierarchy(design_root)
        assert "top" in hierarchy

    def test_hierarchy_has_child(self, design_root):
        extractor = PyslangExtractor()
        hierarchy = extractor.extract_hierarchy(design_root)
        assert "child" in hierarchy.get("top", [])


class TestBuildReport:
    def test_report_counts(self, design_root):
        extractor = PyslangExtractor()
        report = extractor.build_report(design_root, 2, [])
        assert report.total_instances >= 3
        assert report.generated_instances >= 2
        assert report.resolved_signals >= 3
        assert report.top_modules == ["top"]

    def test_report_module_counts(self, design_root):
        extractor = PyslangExtractor()
        report = extractor.build_report(design_root, 2, [])
        assert report.tree_sitter_module_count == 2
        assert report.pyslang_module_count >= 2

    def test_report_diagnostics(self, design_root):
        extractor = PyslangExtractor()
        diagnostics = [{"severity": "error", "message": "test", "is_error": True}]
        report = extractor.build_report(design_root, 2, diagnostics)
        assert report.error_count == 1
        assert report.warning_count == 0
