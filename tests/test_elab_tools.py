"""
Tests for elaboration MCP tools
"""
import pytest
from unittest.mock import MagicMock

from verilog_mcp_server.tools.elab_tools import register_tools
from verilog_mcp_server.database.models import ElaborationReport, ElaboratedInstanceDef, ResolvedSignalDef


@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    mcp.tool = lambda: lambda fn: fn
    return mcp


@pytest.fixture
def mock_store():
    store = MagicMock()
    return store


class TestRtlElabReport:
    def _capture_tools(self, mock_mcp, mock_store):
        tools = {}
        def capture(fn):
            tools[fn.__name__] = fn
            return fn
        mock_mcp.tool = lambda: capture
        register_tools(mock_mcp, mock_store)
        return tools

    def test_no_report(self, mock_mcp, mock_store):
        mock_store.get_elab_report.return_value = None
        tools = self._capture_tools(mock_mcp, mock_store)
        result = tools["rtl_elab_report"]()
        assert "暂无" in result

    def test_with_report(self, mock_mcp, mock_store):
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
            diagnostics=[{"severity": "warning", "message": "test warning", "is_error": False}],
            hierarchy={"top": ["child"]},
        )
        mock_store.get_elab_report.return_value = report
        tools = self._capture_tools(mock_mcp, mock_store)
        result = tools["rtl_elab_report"]()
        assert "top" in result
        assert "5" in result
        assert "2" in result


class TestRtlElabInstances:
    def test_no_instances(self, mock_mcp, mock_store):
        mock_store.get_elab_instances.return_value = []
        tools = {}
        def capture(fn):
            tools[fn.__name__] = fn
            return fn
        mock_mcp.tool = lambda: capture
        register_tools(mock_mcp, mock_store)
        result = tools["rtl_elab_instances"]()
        assert "未找到" in result

    def test_with_instances(self, mock_mcp, mock_store):
        mock_store.get_elab_instances.return_value = [
            ElaboratedInstanceDef(
                instance_name="u_child",
                module_type="child",
                hierarchical_path="top.genblk[0].u_child",
                is_generated=True,
            ),
        ]
        tools = {}
        def capture(fn):
            tools[fn.__name__] = fn
            return fn
        mock_mcp.tool = lambda: capture
        register_tools(mock_mcp, mock_store)
        result = tools["rtl_elab_instances"]()
        assert "u_child" in result
        assert "generate" in result


class TestRtlResolvedSignals:
    def test_no_signals(self, mock_mcp, mock_store):
        mock_store.get_resolved_signals.return_value = []
        tools = {}
        def capture(fn):
            tools[fn.__name__] = fn
            return fn
        mock_mcp.tool = lambda: capture
        register_tools(mock_mcp, mock_store)
        result = tools["rtl_resolved_signals"]("top")
        assert "未找到" in result

    def test_with_signals(self, mock_mcp, mock_store):
        mock_store.get_resolved_signals.return_value = [
            ResolvedSignalDef(
                name="data", module_name="child",
                resolved_width="logic[15:0]", resolved_bit_width=16,
            ),
        ]
        tools = {}
        def capture(fn):
            tools[fn.__name__] = fn
            return fn
        mock_mcp.tool = lambda: capture
        register_tools(mock_mcp, mock_store)
        result = tools["rtl_resolved_signals"]("child")
        assert "data" in result
        assert "16" in result
