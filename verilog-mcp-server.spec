# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('verilog_mcp_server/config.yaml', 'verilog_mcp_server')]
binaries = []
hiddenimports = [
    'verilog_mcp_server',
    'verilog_mcp_server.server',
    'verilog_mcp_server.database',
    'verilog_mcp_server.database.models',
    'verilog_mcp_server.database.index_store',
    'verilog_mcp_server.database.errors',
    'verilog_mcp_server.database.sqlite_backend',
    'verilog_mcp_server.indexer',
    'verilog_mcp_server.indexer.builder',
    'verilog_mcp_server.indexer.module_extractor',
    'verilog_mcp_server.indexer.port_extractor',
    'verilog_mcp_server.indexer.signal_extractor',
    'verilog_mcp_server.indexer.instance_extractor',
    'verilog_mcp_server.indexer.verilog_parser',
    'verilog_mcp_server.indexer.project_scanner',
    'verilog_mcp_server.indexer.type_extractor',
    'verilog_mcp_server.tools',
    'verilog_mcp_server.tools.level1_search',
    'verilog_mcp_server.tools.level2_relation',
    'verilog_mcp_server.tools.level3_analysis',
    'verilog_mcp_server.analysis',
    'verilog_mcp_server.analysis.hierarchy',
    'verilog_mcp_server.analysis.dataflow',
    'verilog_mcp_server.analysis.fan_in',
    'verilog_mcp_server.analysis.fan_out',
    'verilog_mcp_server.analysis.cross_ref',
    'verilog_mcp_server.analysis.fsm_detector',
    'verilog_mcp_server.analysis.clock_analyzer',
    'verilog_mcp_server.analysis.always_classify',
    'verilog_mcp_server.analysis.clock_tree',
    'verilog_mcp_server.analysis.signal_classifier',
    'verilog_mcp_server.analysis.expr_walker',
    'mcp.server',
    'mcp.server.fastmcp',
    'mcp.server.stdio',
    'mcp.types',
]
tmp_ret = collect_all('tree_sitter_language_pack')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['verilog_mcp_server/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='verilog-mcp-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
