"""Tests for analysis/expr_walker.py"""
import pytest
from verilog_mcp_server.analysis.expr_walker import extract_signal_refs


class TestExtractSignalRefs:
    def test_simple_binary_expr(self):
        assert extract_signal_refs("a + b") == ["a", "b"]

    def test_with_constants(self):
        result = extract_signal_refs("data[7:0] & 8'hFF")
        assert "data" in result
        assert "8'hFF" not in result

    def test_concatenation(self):
        result = extract_signal_refs("{carry, sum}")
        assert "carry" in result
        assert "sum" in result

    def test_ternary(self):
        result = extract_signal_refs("sel ? a : b")
        assert "sel" in result
        assert "a" in result
        assert "b" in result

    def test_sensitivity_list(self):
        result = extract_signal_refs("posedge clk or negedge rst_n")
        assert "clk" in result
        assert "rst_n" in result
        # posedge/negedge/or are keywords and should be filtered
        assert "posedge" not in result
        assert "negedge" not in result
        assert "or" not in result

    def test_numbers_filtered(self):
        result = extract_signal_refs("counter + 1")
        assert "counter" in result
        assert "1" not in result

    def test_dedup_preserves_order(self):
        result = extract_signal_refs("a + b + a")
        assert result == ["a", "b"]
