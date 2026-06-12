"""Verilog/SystemVerilog RTL 语义分析 MCP Server"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("verilog-mcp-server")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .server import create_app, load_config, setup_logging, main

__all__ = ["create_app", "load_config", "setup_logging", "main", "__version__"]
