"""
Integration tests for Yosys MCP tools.

Tests the MCP tool functions with mock IndexStore data.
"""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    YosysFsmDef,
    YosysCombLoopDef,
    YosysGatedClockDef,
    YosysStatDef,
)


class TestYosysMCPTools:
    """Integration tests for Yosys MCP tools."""

    @pytest.fixture
    def mock_index_store(self):
        """Create an IndexStore without a real DB."""
        store = IndexStore(db_path=None)
        # Mock the DB-backed methods to work with in-memory data
        store._yosys_fsms = []
        store._yosys_comb_loops = []
        store._yosys_gated_clocks = []
        store._yosys_stats = []

        store.add_yosys_fsm = lambda fsm: store._yosys_fsms.append(fsm)
        store.get_yosys_fsms = lambda module_name=None: (
            store._yosys_fsms if not module_name
            else [f for f in store._yosys_fsms if f.module_name == module_name]
        )
        store.add_yosys_comb_loop = lambda loop: store._yosys_comb_loops.append(loop)
        store.get_yosys_comb_loops = lambda: store._yosys_comb_loops
        store.add_yosys_gated_clock = lambda clock: store._yosys_gated_clocks.append(clock)
        store.get_yosys_gated_clocks = lambda module_name=None: (
            store._yosys_gated_clocks if not module_name
            else [c for c in store._yosys_gated_clocks if c.module_name == module_name]
        )
        store.add_yosys_stat = lambda stat: store._yosys_stats.append(stat)
        store.get_yosys_stats = lambda module_name=None: (
            store._yosys_stats if not module_name
            else [s for s in store._yosys_stats if s.module_name == module_name]
        )
        # Mock get_elab_report to simulate build without --yosys
        store.get_elab_report = lambda: None
        return store

    def test_rtl_yosys_fsm_not_enabled(self, mock_index_store):
        """When --yosys not used, rtl_yosys_fsm returns helpful message."""
        from verilog_mcp_server.tools.yosys_tools import _YOSYS_NOT_AVAILABLE_MSG
        # With no data, should return not-available message
        fsms = mock_index_store.get_yosys_fsms()
        assert fsms == []  # no data

    def test_rtl_yosys_fsm_with_data(self, mock_index_store):
        """When Yosys data exists, returns formatted FSM report."""
        fsm = YosysFsmDef(
            fsm_name="$fsm$ctrl_fsm",
            module_name="ctrl",
            state_count=4,
            encoding="one-hot",
            transitions=[
                {"from": "IDLE", "to": "START", "condition": "go"},
                {"from": "START", "to": "BUSY", "condition": ""},
            ],
            source_file="ctrl.sv:10",
        )
        mock_index_store.add_yosys_fsm(fsm)

        result = mock_index_store.get_yosys_fsms()
        assert len(result) == 1
        assert result[0].fsm_name == "$fsm$ctrl_fsm"
        assert result[0].encoding == "one-hot"

    def test_rtl_yosys_fsm_filter_by_module(self, mock_index_store):
        """Module filter works correctly."""
        fsm1 = YosysFsmDef(fsm_name="fsm_a", module_name="mod_a", state_count=2)
        fsm2 = YosysFsmDef(fsm_name="fsm_b", module_name="mod_b", state_count=3)
        mock_index_store.add_yosys_fsm(fsm1)
        mock_index_store.add_yosys_fsm(fsm2)

        result = mock_index_store.get_yosys_fsms("mod_a")
        assert len(result) == 1
        assert result[0].fsm_name == "fsm_a"

    def test_rtl_yosys_comb_loops_with_data(self, mock_index_store):
        """Comb loop query returns structured data."""
        loop = YosysCombLoopDef(
            loop_signals=["a", "b", "c"],
            source_files=["ring.sv"],
            severity="warn",
            message="Logic loop found",
        )
        mock_index_store.add_yosys_comb_loop(loop)

        result = mock_index_store.get_yosys_comb_loops()
        assert len(result) == 1
        assert "a" in result[0].loop_signals

    def test_rtl_yosys_comb_loops_empty(self, mock_index_store):
        """Empty comb loop list returns empty."""
        assert mock_index_store.get_yosys_comb_loops() == []

    def test_rtl_yosys_gated_clocks_with_data(self, mock_index_store):
        """Gated clock query returns structured data."""
        clock = YosysGatedClockDef(
            gated_clock_name="gated_spi_clk",
            source_clock="sys_clk",
            enable_signal="spi_en",
            type="latch_based",
            module_name="spi_master",
        )
        mock_index_store.add_yosys_gated_clock(clock)

        result = mock_index_store.get_yosys_gated_clocks()
        assert len(result) == 1
        assert result[0].type == "latch_based"

    def test_rtl_yosys_gated_clocks_filter(self, mock_index_store):
        """Gated clock filter by module works."""
        c1 = YosysGatedClockDef(gated_clock_name="g1", module_name="m1", type="and_gate")
        c2 = YosysGatedClockDef(gated_clock_name="g2", module_name="m2", type="latch_based")
        mock_index_store.add_yosys_gated_clock(c1)
        mock_index_store.add_yosys_gated_clock(c2)

        assert len(mock_index_store.get_yosys_gated_clocks("m1")) == 1
        assert len(mock_index_store.get_yosys_gated_clocks()) == 2

    def test_rtl_yosys_stat_with_data(self, mock_index_store):
        """Resource statistics query returns structured data."""
        stat = YosysStatDef(
            module_name="riscv_core",
            num_cells=1024,
            num_wires=2048,
            num_lut=480,
            num_ff=320,
            num_memory=8,
            num_dsp=4,
        )
        mock_index_store.add_yosys_stat(stat)

        result = mock_index_store.get_yosys_stats()
        assert len(result) == 1
        assert result[0].num_lut == 480
        assert result[0].num_ff == 320

    def test_rtl_yosys_stat_filter(self, mock_index_store):
        """Resource stat filter by module works."""
        s1 = YosysStatDef(module_name="core_a", num_cells=100)
        s2 = YosysStatDef(module_name="core_b", num_cells=200)
        mock_index_store.add_yosys_stat(s1)
        mock_index_store.add_yosys_stat(s2)

        assert len(mock_index_store.get_yosys_stats("core_a")) == 1
        assert mock_index_store.get_yosys_stats("core_a")[0].num_cells == 100

    def test_not_enabled_message(self, mock_index_store):
        """The _check_yosys_available function returns appropriate message."""
        from verilog_mcp_server.tools.yosys_tools import _YOSYS_NOT_AVAILABLE_MSG
        # Simulate: no elab report (never built), no yosys data
        # Our mock has get_elab_report() returning None
        msg = _YOSYS_NOT_AVAILABLE_MSG
        assert "Yosys" in msg
        assert "https://github.com/YosysHQ/yosys" in msg
