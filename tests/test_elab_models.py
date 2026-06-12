"""
Tests for elaboration data models
"""
import pytest

from verilog_mcp_server.database.models import (
    ElaboratedInstanceDef,
    ResolvedSignalDef,
    MacroExpansionInfo,
    ElaborationReport,
)


class TestElaboratedInstanceDef:
    def test_basic_creation(self):
        inst = ElaboratedInstanceDef(
            instance_name="u_child",
            module_type="child",
            hierarchical_path="top.genblk[0].u_child",
        )
        assert inst.instance_name == "u_child"
        assert inst.is_generated is False

    def test_to_dict(self):
        inst = ElaboratedInstanceDef(
            instance_name="u_child",
            module_type="child",
            hierarchical_path="top.genblk[0].u_child",
            is_generated=True,
        )
        d = inst.to_dict()
        assert d["instance_name"] == "u_child"
        assert d["is_generated"] is True

    def test_from_dict(self):
        d = {
            "instance_name": "u_child",
            "module_type": "child",
            "hierarchical_path": "top.genblk[0].u_child",
            "is_generated": True,
            "generate_condition": "i < 2",
        }
        inst = ElaboratedInstanceDef.from_dict(d)
        assert inst.instance_name == "u_child"
        assert inst.is_generated is True
        assert inst.generate_condition == "i < 2"

    def test_roundtrip(self):
        inst = ElaboratedInstanceDef(
            instance_name="u_child",
            module_type="child",
            hierarchical_path="top.genblk[0].u_child",
            is_generated=True,
            generate_condition="i < 2",
            generate_source="generate for",
            parent_module="top",
            file_path="/tmp/top.sv",
            line=10,
        )
        d = inst.to_dict()
        inst2 = ElaboratedInstanceDef.from_dict(d)
        assert inst2.instance_name == inst.instance_name
        assert inst2.is_generated == inst.is_generated
        assert inst2.hierarchical_path == inst.hierarchical_path


class TestResolvedSignalDef:
    def test_basic_creation(self):
        sig = ResolvedSignalDef(
            name="data",
            module_name="child",
            resolved_width="logic[15:0]",
            resolved_bit_width=16,
        )
        assert sig.name == "data"
        assert sig.resolved_bit_width == 16

    def test_roundtrip(self):
        sig = ResolvedSignalDef(
            name="data",
            module_name="child",
            var_type="wire",
            original_width="[WIDTH-1:0]",
            resolved_width="logic[15:0]",
            resolved_bit_width=16,
            is_signed=False,
        )
        d = sig.to_dict()
        sig2 = ResolvedSignalDef.from_dict(d)
        assert sig2.name == sig.name
        assert sig2.resolved_bit_width == sig.resolved_bit_width
        assert sig2.original_width == sig.original_width


class TestMacroExpansionInfo:
    def test_basic_creation(self):
        macro = MacroExpansionInfo(
            name="WIDTH",
            definition="32",
            expansion_count=5,
        )
        assert macro.name == "WIDTH"
        assert macro.expansion_count == 5

    def test_roundtrip(self):
        macro = MacroExpansionInfo(
            name="WIDTH",
            definition="32",
            definition_file="/tmp/defs.vh",
            definition_line=5,
            expansion_count=3,
            expansion_locations=[{"file": "a.sv", "line": 10}],
        )
        d = macro.to_dict()
        macro2 = MacroExpansionInfo.from_dict(d)
        assert macro2.name == macro.name
        assert macro2.expansion_count == macro.expansion_count
        assert len(macro2.expansion_locations) == 1


class TestElaborationReport:
    def test_basic_creation(self):
        report = ElaborationReport(
            top_modules=["top"],
            total_instances=5,
            generated_instances=2,
        )
        assert report.top_modules == ["top"]
        assert report.total_instances == 5

    def test_roundtrip(self):
        report = ElaborationReport(
            top_modules=["top"],
            total_instances=5,
            generated_instances=2,
            non_generated_instances=3,
            unique_module_types=2,
            resolved_signals=10,
            tree_sitter_module_count=2,
            pyslang_module_count=2,
            error_count=0,
            warning_count=1,
            diagnostics=[{"severity": "warning", "message": "test"}],
            hierarchy={"top": ["child"]},
        )
        d = report.to_dict()
        report2 = ElaborationReport.from_dict(d)
        assert report2.total_instances == report.total_instances
        assert report2.generated_instances == report.generated_instances
        assert report2.hierarchy == report.hierarchy
        assert len(report2.diagnostics) == 1
