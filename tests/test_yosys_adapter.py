"""
Tests for YosysAdapter.

Uses mock Yosys output data (no real Yosys needed).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from verilog_mcp_server.eda.yosys_adapter import YosysAdapter


# ── Mock Yosys JSON output fixtures ──

MOCK_YOSYS_NETLIST = {
    "modules": {
        "uart_ctrl": {
            "cells": {
                "$fsm$uart_fsm_0": {
                    "type": "$fsm",
                    "parameters": {
                        "\\STATE_COUNT": "4",
                        "\\ENCODING": "one-hot",
                    },
                    "connections": {
                        "\\state_bits": [0, 0, 0, 1, 0],
                        "\\CTRL_IN": ["start", "done"],
                    },
                    "attributes": {
                        "\\src": "uart_ctrl.sv:42",
                    },
                },
                "$dlatch$clk_gate": {
                    "type": "$dlatch",
                    "parameters": {},
                    "connections": {
                        "\\D": ["sys_clk"],
                        "\\G": ["spi_en"],
                        "\\Q": ["gated_spi_clk"],
                    },
                    "attributes": {"\\src": "uart_ctrl.sv:88"},
                },
            },
        },
    },
}

MOCK_STAT_JSON = {
    "design": {
        "num_cells": 256,
        "num_wires": 512,
        "num_cells_by_type": {
            "$lut": 120,
            "$dff": 80,
            "$mux": 30,
            "$mem": 2,
            "$dsp": 4,
            "$_AND_": 20,
        },
    },
    "modules": {
        "uart_ctrl": {
            "num_cells": 256,
            "num_wires": 512,
            "num_cells_by_type": {
                "$lut": 120,
                "$dff": 80,
                "$mux": 30,
                "$mem": 2,
                "$dsp": 4,
            },
        }
    },
}

MOCK_CHECK_OUTPUT = """
Found logic loop in module ring_osc:
  wire a
  wire b
  cell $_NOT_ $abc

Found logic loop in module bad_latch:
  wire q
  wire d
  cell $_BUF_ $def
"""


class TestYosysAdapter:
    """Tests for YosysAdapter."""

    def test_check_available_not_installed(self):
        """Returns False when yosys is not in PATH."""
        adapter = YosysAdapter({"yosys_path": "/nonexistent/yosys"})
        assert adapter.check_available() is False

    def test_check_available_not_found(self):
        """Returns False when command not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            adapter = YosysAdapter()
            assert adapter.check_available() is False

    def test_run_empty_files(self):
        """run() returns False when no files provided."""
        adapter = YosysAdapter()
        # Patch is_available to avoid real check
        with patch.object(adapter, "is_available", return_value=True):
            result = adapter.run([], "top", "/tmp/out")
            assert result is False

    def test_run_not_available(self):
        """run() returns False when yosys is unavailable."""
        adapter = YosysAdapter()
        with patch.object(adapter, "is_available", return_value=False):
            result = adapter.run(["test.v"], "top", "/tmp/out")
            assert result is False

    def test_output_files_exist(self):
        """_output_files_exist checks for correct files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Files don't exist yet
            assert YosysAdapter._output_files_exist(tmpdir) is False
            # Create files
            Path(tmpdir, "yosys_netlist.json").touch()
            Path(tmpdir, "stat.json").touch()
            assert YosysAdapter._output_files_exist(tmpdir) is True

    def test_parse_fsm_from_netlist(self):
        """_parse_fsm extracts FSM from Yosys JSON netlist."""
        adapter = YosysAdapter()
        fsms = adapter._parse_fsm(MOCK_YOSYS_NETLIST)
        assert len(fsms) == 1
        fsm = fsms[0]
        assert fsm["module_name"] == "uart_ctrl"
        assert fsm["state_count"] == 4
        assert fsm["encoding"] == "one-hot"
        assert "fsm_name" in fsm

    def test_parse_fsm_empty_design(self):
        """_parse_fsm returns empty list for design without FSM."""
        adapter = YosysAdapter()
        fsms = adapter._parse_fsm({"modules": {"empty": {"cells": {}}}})
        assert fsms == []

    def test_infer_encoding_one_hot(self):
        """Encoding inference detects one-hot when state_count matches bits."""
        adapter = YosysAdapter()
        result = adapter._infer_encoding(
            {"parameters": {"\\ENCODING": "one-hot"}}, 4
        )
        assert result == "one-hot"

    def test_infer_encoding_binary(self):
        """Encoding inference detects binary."""
        adapter = YosysAdapter()
        result = adapter._infer_encoding(
            {"parameters": {"ENCODING": "binary"}}, 4
        )
        assert result == "binary"

    def test_infer_encoding_unknown(self):
        """Encoding inference returns unknown when no data."""
        adapter = YosysAdapter()
        result = adapter._infer_encoding({"parameters": {}}, 4)
        assert result == "unknown"

    def test_parse_comb_loops_empty(self):
        """_parse_comb_loops returns empty for clean output."""
        adapter = YosysAdapter()
        loops = adapter._parse_comb_loops("No loops found.")
        assert loops == []

    def test_parse_comb_loops(self):
        """_parse_comb_loops extracts loops from check output."""
        adapter = YosysAdapter()
        loops = adapter._parse_comb_loops(MOCK_CHECK_OUTPUT)
        assert len(loops) == 2
        # First loop should have signals from the ring_osc module
        assert "a" in loops[0]["loop_signals"]
        assert "b" in loops[0]["loop_signals"]
        assert all(loop["severity"] == "warn" for loop in loops)

    def test_parse_gated_clocks(self):
        """_parse_gated_clocks detects latch-based gated clocks."""
        adapter = YosysAdapter()
        clocks = adapter._parse_gated_clocks(MOCK_YOSYS_NETLIST)
        assert len(clocks) == 1
        clock = clocks[0]
        assert clock["type"] == "latch_based"
        assert "module_name" in clock

    def test_parse_gated_clocks_empty(self):
        """_parse_gated_clocks returns empty for no gated clocks."""
        adapter = YosysAdapter()
        clocks = adapter._parse_gated_clocks({"modules": {"top": {"cells": {}}}})
        assert clocks == []

    def test_parse_stat(self):
        """_parse_stat extracts resource statistics."""
        adapter = YosysAdapter()
        stats = adapter._parse_stat(MOCK_STAT_JSON)
        assert len(stats) == 1
        stat = stats[0]
        assert stat["module_name"] == "uart_ctrl"
        assert stat["num_cells"] == 256
        assert stat["num_wires"] == 512
        assert stat["num_lut"] == 150  # $lut(120) + $mux(30)
        assert stat["num_ff"] == 80   # $dff(80)
        assert stat["num_memory"] == 2
        assert stat["num_dsp"] == 4

    def test_parse_stat_from_design_level(self):
        """_parse_stat works with design-level (no modules) stat output."""
        adapter = YosysAdapter()
        stat_data = {
            "design": {
                "num_cells": 10,
                "num_wires": 20,
                "num_cells_by_type": {},
            }
        }
        stats = adapter._parse_stat(stat_data)
        assert len(stats) == 1
        assert stats[0]["module_name"] == "top"
        assert stats[0]["num_cells"] == 10

    def test_parse_output_full(self):
        """parse_output() integrates all parsers."""
        adapter = YosysAdapter()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write mock Yosys output files
            netlist_path = os.path.join(tmpdir, "yosys_netlist.json")
            stat_path = os.path.join(tmpdir, "stat.json")

            with open(netlist_path, "w") as f:
                json.dump(MOCK_YOSYS_NETLIST, f)
            with open(stat_path, "w") as f:
                json.dump(MOCK_STAT_JSON, f)

            results = adapter.parse_output(tmpdir)

            assert "fsms" in results
            assert "comb_loops" in results
            assert "gated_clocks" in results
            assert "stats" in results
            assert len(results["fsms"]) == 1
            assert len(results["gated_clocks"]) == 1
            assert len(results["stats"]) == 1

    def test_parse_output_missing_files(self):
        """parse_output() handles missing output files gracefully."""
        adapter = YosysAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            results = adapter.parse_output(tmpdir)
            assert results["fsms"] == []
            assert results["stats"] == []

    def test_tcl_template_contains_required_passes(self):
        """Yosys Tcl template includes proc, fsm_detect, check, clk2fflogic, stat, write_json."""
        from verilog_mcp_server.eda.yosys_adapter import _YOSYS_TCL_TEMPLATE

        template_str = _YOSYS_TCL_TEMPLATE.template
        required = ["read_verilog", "hierarchy", "proc", "fsm_detect",
                    "check", "clk2fflogic", "stat", "write_json"]
        for r in required:
            assert r in template_str, f"Missing pass: {r}"

    def test_bundled_yosys_path_preferred(self, monkeypatch):
        """When YOSYS_BUNDLED_PATH is set, it takes priority over config."""
        monkeypatch.setenv("YOSYS_BUNDLED_PATH", "/bundle/yosys")
        adapter = YosysAdapter({"yosys_path": "/usr/bin/yosys"})
        assert adapter._yosys_cmd == "/bundle/yosys"

    def test_config_yosys_path_fallback(self):
        """When no env var, config path is used."""
        adapter = YosysAdapter({"yosys_path": "/custom/yosys"})
        assert adapter._yosys_cmd == "/custom/yosys"

    def test_default_yosys_path(self):
        """When nothing configured, defaults to 'yosys' (PATH lookup)."""
        adapter = YosysAdapter({})
        assert adapter._yosys_cmd == "yosys"
