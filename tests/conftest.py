"""pytest configuration and helpers"""

import pytest


def parse_source_available() -> bool:
    """Check if tree-sitter parser can be loaded (requires network on first run)"""
    try:
        from verilog_mcp_server.indexer.verilog_parser import parse_source
        tree, src = parse_source("module test(); endmodule")
        return tree is not None
    except Exception:
        return False


parse_source_skip = pytest.mark.skipif(
    not parse_source_available(),
    reason="tree-sitter parser download unavailable (network required on first run)"
)
