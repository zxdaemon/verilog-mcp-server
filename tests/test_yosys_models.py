"""
Tests for Yosys data models — serialization / deserialization.
"""

from __future__ import annotations

import json

import pytest

from verilog_mcp_server.database.models import (
    YosysFsmDef,
    YosysCombLoopDef,
    YosysGatedClockDef,
    YosysStatDef,
)


class TestYosysFsmDef:
    """Tests for YosysFsmDef."""

    def test_default_values(self):
        fsm = YosysFsmDef()
        assert fsm.fsm_name == ""
        assert fsm.module_name == ""
        assert fsm.state_count == 0
        assert fsm.encoding == "unknown"
        assert fsm.transitions == []
        assert fsm.source_file == ""

    def test_to_dict_from_dict_roundtrip(self):
        fsm = YosysFsmDef(
            fsm_name="$fsm$uart_fsm_0",
            module_name="uart_ctrl",
            state_count=4,
            encoding="one-hot",
            transitions=[
                {"from": "IDLE", "to": "START", "condition": "start"},
                {"from": "START", "to": "DATA", "condition": ""},
            ],
            source_file="uart_ctrl.sv:42",
        )
        d = fsm.to_dict()
        assert d["fsm_name"] == "$fsm$uart_fsm_0"
        assert d["state_count"] == 4
        assert len(d["transitions"]) == 2

        restored = YosysFsmDef.from_dict(d)
        assert restored.fsm_name == fsm.fsm_name
        assert restored.state_count == fsm.state_count
        assert restored.encoding == fsm.encoding
        assert restored.transitions == fsm.transitions

    def test_empty_transitions(self):
        fsm = YosysFsmDef(fsm_name="empty_fsm")
        assert fsm.to_dict()["transitions"] == []


class TestYosysCombLoopDef:
    """Tests for YosysCombLoopDef."""

    def test_default_values(self):
        loop = YosysCombLoopDef()
        assert loop.loop_signals == []
        assert loop.source_files == []
        assert loop.severity == "warn"
        assert loop.message == ""

    def test_to_dict_from_dict_roundtrip(self):
        loop = YosysCombLoopDef(
            loop_signals=["a", "b", "c"],
            source_files=["ring_osc.sv"],
            severity="error",
            message="Found logic loop in module ring_osc",
        )
        d = loop.to_dict()
        restored = YosysCombLoopDef.from_dict(d)
        assert restored.loop_signals == loop.loop_signals
        assert restored.severity == "error"

    def test_empty_loop_signals(self):
        loop = YosysCombLoopDef(severity="warn")
        d = loop.to_dict()
        assert d["loop_signals"] == []


class TestYosysGatedClockDef:
    """Tests for YosysGatedClockDef."""

    def test_default_values(self):
        clock = YosysGatedClockDef()
        assert clock.gated_clock_name == ""
        assert clock.source_clock == ""
        assert clock.enable_signal == ""
        assert clock.type == ""
        assert clock.module_name == ""

    def test_to_dict_from_dict_roundtrip(self):
        clock = YosysGatedClockDef(
            gated_clock_name="gated_spi_clk",
            source_clock="sys_clk",
            enable_signal="spi_en",
            type="latch_based",
            module_name="spi_master",
        )
        d = clock.to_dict()
        assert d["type"] == "latch_based"
        restored = YosysGatedClockDef.from_dict(d)
        assert restored.gated_clock_name == clock.gated_clock_name
        assert restored.type == clock.type

    def test_and_gate_type(self):
        clock = YosysGatedClockDef(
            gated_clock_name="gated_i2c_clk",
            source_clock="core_clk",
            type="and_gate",
            module_name="i2c",
        )
        assert clock.type == "and_gate"


class TestYosysStatDef:
    """Tests for YosysStatDef."""

    def test_default_values(self):
        stat = YosysStatDef()
        assert stat.module_name == ""
        assert stat.num_cells == 0
        assert stat.num_wires == 0
        assert stat.num_lut == 0
        assert stat.num_ff == 0
        assert stat.num_memory == 0
        assert stat.num_dsp == 0

    def test_to_dict_from_dict_roundtrip(self):
        stat = YosysStatDef(
            module_name="riscv_core",
            num_cells=1024,
            num_wires=2048,
            num_lut=480,
            num_ff=320,
            num_memory=8,
            num_dsp=4,
        )
        d = stat.to_dict()
        assert d["num_lut"] == 480
        restored = YosysStatDef.from_dict(d)
        assert restored.module_name == stat.module_name
        assert restored.num_cells == stat.num_cells
        assert restored.num_dsp == stat.num_dsp

    def test_zero_resource_module(self):
        stat = YosysStatDef(module_name="empty_wrapper", num_cells=0)
        assert stat.num_cells == 0
        assert stat.num_lut == 0
