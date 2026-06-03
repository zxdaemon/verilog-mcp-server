"""Tests for analysis/signal_classifier.py"""
import pytest
from verilog_mcp_server.database.models import ModuleDef, AlwaysBlockInfo, PortDef
from verilog_mcp_server.analysis.signal_classifier import SignalClassifier


def make_module(name="test_mod", signals=None, ports=None, always_blocks=None):
    return ModuleDef(
        name=name,
        file_path="test.sv",
        ports=ports or [],
        signals=signals or [],
        always_blocks=always_blocks or [],
        instances=[],
        parameters=[],
        assignments=[],
    )


class TestIsClock:
    def test_named_clock_pattern(self):
        sc = SignalClassifier()
        mod = make_module()
        assert sc.is_clock("sys_clk", mod) is True
        assert sc.is_clock("clk", mod) is True
        assert sc.is_clock("hclk", mod) is True

    def test_input_port_clock(self):
        sc = SignalClassifier()
        mod = make_module(ports=[PortDef(name="core_clk", direction="input", var_type="wire")])
        assert sc.is_clock("core_clk", mod) is True

    def test_input_port_not_clock_if_reset(self):
        sc = SignalClassifier()
        mod = make_module(ports=[PortDef(name="rst_n", direction="input", var_type="wire")])
        assert sc.is_clock("rst_n", mod) is False

    def test_multi_always_sensitivity(self):
        sc = SignalClassifier()
        mod = make_module(always_blocks=[
            AlwaysBlockInfo(sensitivity_list="@(posedge osc_clk)", block_type="sequential", statements=[]),
            AlwaysBlockInfo(sensitivity_list="@(posedge osc_clk)", block_type="sequential", statements=[]),
        ])
        assert sc.is_clock("osc_clk", mod) is True

    def test_not_clock(self):
        sc = SignalClassifier()
        mod = make_module()
        assert sc.is_clock("data_out", mod) is False
        assert sc.is_clock("enable", mod) is False


class TestIsReset:
    def test_named_reset(self):
        sc = SignalClassifier()
        assert sc.is_reset("rst_n") is True
        assert sc.is_reset("rst") is True
        assert sc.is_reset("reset_n") is True
        assert sc.is_reset("nrst") is True

    def test_not_reset(self):
        sc = SignalClassifier()
        assert sc.is_reset("data_out") is False
        assert sc.is_reset("clk") is False


class TestInferResetPolarity:
    def test_active_low_by_name(self):
        sc = SignalClassifier()
        assert sc.infer_reset_polarity("rst_n", "posedge") == "low"
        assert sc.infer_reset_polarity("reset_b", "posedge") == "low"

    def test_active_low_by_negedge(self):
        sc = SignalClassifier()
        assert sc.infer_reset_polarity("rst", "negedge") == "low"

    def test_active_high(self):
        sc = SignalClassifier()
        assert sc.infer_reset_polarity("rst", "posedge") == "high"
