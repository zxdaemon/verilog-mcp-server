"""Test UvmConfigDbTracer — config_db set/get tracing."""

import pytest
from tree_sitter_language_pack import get_parser

from verilog_mcp_server.analysis.uvm_config_db import UvmConfigDbTracer
from verilog_mcp_server.database.models import UvmConfigEntry


@pytest.fixture
def parser():
    return get_parser("systemverilog")


@pytest.fixture
def tracer():
    return UvmConfigDbTracer()


class TestConfigDbTracer:
    def test_tracer_initialization(self):
        tracer = UvmConfigDbTracer()
        assert tracer is not None

    def test_analyze_file_finds_set_calls(self, parser, tracer):
        src = """
function void build_phase(uvm_phase phase);
  uvm_config_db#(int)::set(this, "agt.*", "count", 42);
endfunction
"""
        tree = parser.parse(src)
        entries = tracer.analyze_file(tree, src, "test.sv")
        assert len(entries) >= 1
        assert entries[0].operation == "set"
        assert entries[0].field_name == "count"

    def test_analyze_file_finds_get_calls(self, parser, tracer):
        src = """
function void build_phase(uvm_phase phase);
  uvm_config_db#(int)::get(this, "", "count", count);
endfunction
"""
        tree = parser.parse(src)
        entries = tracer.analyze_file(tree, src, "test.sv")
        assert len(entries) >= 1
        assert entries[0].operation == "get"
        assert entries[0].field_name == "count"

    def test_analyze_file_multiple_calls(self, parser, tracer):
        src = """
function void build_phase(uvm_phase phase);
  uvm_config_db#(int)::set(this, "agt.*", "count", 42);
  uvm_config_db#(string)::set(this, "env.*", "name", "test");
  uvm_config_db#(int)::get(this, "", "count", count);
endfunction
"""
        tree = parser.parse(src)
        entries = tracer.analyze_file(tree, src, "test.sv")
        assert len(entries) == 3

    def test_no_config_db_calls(self, parser, tracer):
        src = """
function void build_phase(uvm_phase phase);
  int x = 1;
endfunction
"""
        tree = parser.parse(src)
        entries = tracer.analyze_file(tree, src, "test.sv")
        assert entries == []


class TestMatchPairs:
    def test_match_set_get_pairs(self, tracer):
        entries = [
            UvmConfigEntry(field_name="count", type_param="int", operation="set",
                           scope="agt.*", value_hint="42"),
            UvmConfigEntry(field_name="count", type_param="int", operation="get",
                           scope="", value_hint="count"),
        ]
        result = tracer.match_pairs(entries)
        assert len(result["matched"]) == 1
        assert result["unmatched_sets"] == []
        assert result["unmatched_gets"] == []

    def test_unmatched_set(self, tracer):
        entries = [
            UvmConfigEntry(field_name="orphan", type_param="int", operation="set",
                           scope="*", value_hint="1"),
        ]
        result = tracer.match_pairs(entries)
        assert len(result["matched"]) == 0
        assert len(result["unmatched_sets"]) == 1

    def test_unmatched_get(self, tracer):
        entries = [
            UvmConfigEntry(field_name="orphan", type_param="int", operation="get",
                           scope="*", value_hint="x"),
        ]
        result = tracer.match_pairs(entries)
        assert len(result["matched"]) == 0
        assert len(result["unmatched_gets"]) == 1

    def test_different_type_params_not_matched(self, tracer):
        entries = [
            UvmConfigEntry(field_name="count", type_param="int", operation="set",
                           scope="*", value_hint="42"),
            UvmConfigEntry(field_name="count", type_param="string", operation="get",
                           scope="*", value_hint="s"),
        ]
        result = tracer.match_pairs(entries)
        assert len(result["matched"]) == 0
        assert len(result["unmatched_sets"]) == 1
        assert len(result["unmatched_gets"]) == 1


class TestFormatReport:
    def test_format_report_with_pairs(self, tracer):
        entries = [
            UvmConfigEntry(field_name="count", type_param="int", operation="set",
                           scope="*", value_hint="42"),
            UvmConfigEntry(field_name="count", type_param="int", operation="get",
                           scope="*", value_hint="count"),
        ]
        report = tracer.format_report(entries)
        assert "Matched Pairs" in report
        assert "count" in report

    def test_format_report_empty(self, tracer):
        report = tracer.format_report([])
        assert "No uvm_config_db calls found" in report

    def test_format_report_unmatched(self, tracer):
        entries = [
            UvmConfigEntry(field_name="orphan", type_param="int", operation="set",
                           scope="*", value_hint="1"),
        ]
        report = tracer.format_report(entries)
        assert "Unmatched Sets" in report
