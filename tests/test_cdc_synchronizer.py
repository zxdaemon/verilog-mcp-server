"""
Tests for CDC synchronizer detection
"""
import pytest

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, SignalDef, AlwaysBlockInfo,
)
from verilog_mcp_server.analysis.clock_analyzer import ClockAnalyzer


@pytest.fixture
def two_flop_sync_module():
    """Module with two-flop synchronizer"""
    store = IndexStore()

    mod = ModuleDef(
        name="cdc_sync",
        file_path="cdc.sv",
        line_start=1,
        line_end=20,
        ports=[
            PortDef(name="clk_a", direction="input", var_type="wire"),
            PortDef(name="clk_b", direction="input", var_type="wire"),
            PortDef(name="async_sig", direction="input", var_type="wire"),
            PortDef(name="synced_sig", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(name="sync_ff1", var_type="reg"),
            SignalDef(name="sync_ff2", var_type="reg"),
        ],
        always_blocks=[
            # First flop: sample async_sig in clk_b domain
            AlwaysBlockInfo(
                sensitivity_list="posedge clk_b",
                block_type="sequential",
                statements=[
                    "sync_ff1 <= async_sig;",
                ],
            ),
            # Second flop: sample sync_ff1 in clk_b domain
            AlwaysBlockInfo(
                sensitivity_list="posedge clk_b",
                block_type="sequential",
                statements=[
                    "sync_ff2 <= sync_ff1;",
                ],
            ),
            # Output assignment
            AlwaysBlockInfo(
                sensitivity_list="posedge clk_b",
                block_type="sequential",
                statements=[
                    "synced_sig <= sync_ff2;",
                ],
            ),
        ],
    )
    store.add_module(mod)
    return store


@pytest.fixture
def handshake_sync_module():
    """Module with handshake synchronizer"""
    store = IndexStore()

    mod = ModuleDef(
        name="handshake_sync",
        file_path="handshake.sv",
        line_start=1,
        line_end=30,
        ports=[
            PortDef(name="clk_a", direction="input", var_type="wire"),
            PortDef(name="clk_b", direction="input", var_type="wire"),
            PortDef(name="req", direction="input", var_type="wire"),
            PortDef(name="ack", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(name="req_sync", var_type="reg"),
            SignalDef(name="ack_sync", var_type="reg"),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk_b",
                block_type="sequential",
                statements=[
                    "req_sync <= req;",
                ],
            ),
            AlwaysBlockInfo(
                sensitivity_list="posedge clk_a",
                block_type="sequential",
                statements=[
                    "ack_sync <= ack;",
                ],
            ),
        ],
    )
    store.add_module(mod)
    return store


class TestTwoFlopSynchronizer:
    def test_detects_two_flop(self, two_flop_sync_module):
        analyzer = ClockAnalyzer(two_flop_sync_module)
        syncs = analyzer._detect_synchronizers(
            two_flop_sync_module.get_module("cdc_sync"),
            ["async_sig"]
        )
        assert "async_sig" in syncs
        assert syncs["async_sig"] == "two_flop"


class TestHandshakeSynchronizer:
    def test_detects_handshake(self, handshake_sync_module):
        analyzer = ClockAnalyzer(handshake_sync_module)
        syncs = analyzer._detect_synchronizers(
            handshake_sync_module.get_module("handshake_sync"),
            ["req", "ack"]
        )
        assert "req" in syncs or "ack" in syncs


class TestCDCToolOutput:
    def test_cross_domain_with_sync_info(self, two_flop_sync_module):
        from verilog_mcp_server.tools.level3_analysis import register_tools
        from mcp.server.fastmcp import FastMCP

        store = two_flop_sync_module
        mcp = FastMCP("test")
        register_tools(mcp, store)

        tool_fn = None
        for tool_info in mcp._tool_manager._tools.values():
            if tool_info.name == "rtl_cross_domain_signals":
                tool_fn = tool_info.fn
                break

        result = tool_fn(module_name="cdc_sync")
        assert "cdc_sync" in result
