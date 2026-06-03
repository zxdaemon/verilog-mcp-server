"""Allow running as `python -m verilog_mcp_server`"""

import sys

if getattr(sys, 'frozen', False):
    from verilog_mcp_server.server import main
else:
    from .server import main

main()
