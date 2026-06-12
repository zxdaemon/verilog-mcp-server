"""
Tests for SQLite backend elaboration operations
"""
import os
import tempfile

import pytest

from verilog_mcp_server.database.sqlite_backend import SQLiteBackend
from verilog_mcp_server.database.models import (
    ElaboratedInstanceDef,
    ResolvedSignalDef,
    MacroExpansionInfo,
    ElaborationReport,
)


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    backend = SQLiteBackend(path)
    yield backend
    backend.close()
    os.unlink(path)


class TestElaboratedInstanceOperations:
    def test_save_and_get(self, db):
        inst = ElaboratedInstanceDef(
            instance_name="u_child",
            module_type="child",
            hierarchical_path="top.genblk[0].u_child",
            is_generated=True,
        )
        db.save_elaborated_instance(inst)
        results = db.get_all_elaborated_instances()
        assert len(results) == 1
        assert results[0].instance_name == "u_child"
        assert results[0].is_generated is True

    def test_get_by_module(self, db):
        db.save_elaborated_instance(
            ElaboratedInstanceDef(
                instance_name="u1", module_type="child",
                hierarchical_path="top.u1", is_generated=False,
            )
        )
        db.save_elaborated_instance(
            ElaboratedInstanceDef(
                instance_name="u2", module_type="child",
                hierarchical_path="top.u2", is_generated=False,
            )
        )
        db.save_elaborated_instance(
            ElaboratedInstanceDef(
                instance_name="u3", module_type="other",
                hierarchical_path="top.u3", is_generated=False,
            )
        )
        results = db.get_elaborated_instances_by_module("child")
        assert len(results) == 2

    def test_clear(self, db):
        db.save_elaborated_instance(
            ElaboratedInstanceDef(
                instance_name="u1", module_type="child",
                hierarchical_path="top.u1", is_generated=False,
            )
        )
        db.clear_elaborated_instances()
        assert len(db.get_all_elaborated_instances()) == 0


class TestResolvedSignalOperations:
    def test_save_and_get(self, db):
        sig = ResolvedSignalDef(
            name="data", module_name="child",
            resolved_width="logic[15:0]", resolved_bit_width=16,
        )
        db.save_resolved_signal(sig)
        results = db.get_all_resolved_signals()
        assert len(results) == 1
        assert results[0].name == "data"
        assert results[0].resolved_bit_width == 16

    def test_get_by_module(self, db):
        db.save_resolved_signal(
            ResolvedSignalDef(name="a", module_name="top", resolved_bit_width=8)
        )
        db.save_resolved_signal(
            ResolvedSignalDef(name="b", module_name="top", resolved_bit_width=16)
        )
        db.save_resolved_signal(
            ResolvedSignalDef(name="c", module_name="other", resolved_bit_width=32)
        )
        results = db.get_resolved_signals_by_module("top")
        assert len(results) == 2


class TestMacroExpansionOperations:
    def test_save_and_get(self, db):
        macro = MacroExpansionInfo(
            name="WIDTH", definition="32",
            expansion_count=5,
            expansion_locations=[{"file": "a.sv", "line": 10}],
        )
        db.save_macro_expansion(macro)
        results = db.get_macro_expansions()
        assert len(results) == 1
        assert results[0].name == "WIDTH"
        assert results[0].expansion_count == 5


class TestElaborationReportOperations:
    def test_save_and_get_latest(self, db):
        report = ElaborationReport(
            top_modules=["top"],
            total_instances=5,
            generated_instances=2,
            error_count=0,
            warning_count=1,
        )
        report_id = db.save_elaboration_report(report)
        assert report_id > 0

        latest = db.get_latest_elaboration_report()
        assert latest is not None
        assert latest.total_instances == 5
        assert latest.generated_instances == 2

    def test_get_all_reports(self, db):
        db.save_elaboration_report(
            ElaborationReport(total_instances=1, top_modules=["a"])
        )
        db.save_elaboration_report(
            ElaborationReport(total_instances=2, top_modules=["b"])
        )
        reports = db.get_all_elaboration_reports()
        assert len(reports) == 2
        # Latest first (by id)
        assert reports[0].total_instances == 2

    def test_no_reports(self, db):
        latest = db.get_latest_elaboration_report()
        assert latest is None
