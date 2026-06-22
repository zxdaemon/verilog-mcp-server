# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = [
    ('verilog_mcp_server/config.yaml', 'verilog_mcp_server'),
    ('verilog_mcp_server/templates', 'verilog_mcp_server/templates'),
    ('tree-sitter-cache', 'tree-sitter-cache'),
]

# 如果 yosys 二进制存在，打包进去
_YOSYS_BIN = None
for _p in ['verilog_mcp_server/eda/bin/yosys', 'yosys']:
    if os.path.isfile(_p) and os.access(_p, os.X_OK):
        _YOSYS_BIN = _p
        break

binaries = []
if _YOSYS_BIN:
    binaries.append((_YOSYS_BIN, 'eda/bin'))

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
    'verilog_mcp_server.indexer.package_extractor',
    'verilog_mcp_server.indexer.sva_extractor',
    'verilog_mcp_server.indexer.macro_extractor',
    'verilog_mcp_server.indexer.filelist_parser',
    'verilog_mcp_server.indexer.pyslang_parser',
    'verilog_mcp_server.indexer.pyslang_extractor',
    'verilog_mcp_server.tools',
    'verilog_mcp_server.tools.level1_search',
    'verilog_mcp_server.tools.level2_relation',
    'verilog_mcp_server.tools.level3_analysis',
    'verilog_mcp_server.tools.visualize',
    'verilog_mcp_server.tools.elab_tools',
    'verilog_mcp_server.tools.yosys_tools',
    'verilog_mcp_server.eda',
    'verilog_mcp_server.eda.base_adapter',
    'verilog_mcp_server.eda.cache',
    'verilog_mcp_server.eda.yosys_adapter',
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
    'verilog_mcp_server.analysis.visualizer',
    'verilog_mcp_server.templates',
    'mcp.server',
    'mcp.server.fastmcp',
    'mcp.server.stdio',
    'mcp.types',
]
tmp_ret = collect_all('tree_sitter_language_pack')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyslang')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['verilog_mcp_server/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['scripts/tree_sitter_cache_hook.py', 'scripts/yosys_runtime_hook.py'],
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
