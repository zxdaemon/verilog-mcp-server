"""批 6 顺手件三刀回归测试（VMS-06①/② + VMS-13 增量孤儿，2026-10-13）

- 刀① packed 维度收集：signal_extractor / port_extractor 多 packed 维度全保留
- 刀② instance_connections 实例数组基名匹配
- 刀③ 增量构建失败告警 + file_meta 条件写（孤儿不再固化）
"""

import pytest

from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.signal_extractor import SignalExtractor
from verilog_mcp_server.indexer.port_extractor import PortExtractor
from verilog_mcp_server.analysis.cross_ref import CrossReference
from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import ModuleDef, InstanceDef, PortDef

# ── 刀① packed 维度收集 ──

MODULE_2D = """\
module test_2d (
    input  wire [1:0][7:0] din,
    output wire [1:0][27:0] dout
);
    wire [1:0][27:0] bus;
    reg  [3:0][7:0] regs;
    logic [2:0][5:0] lg;
    wire [7:0] plain;
    reg flat;
endmodule
"""

MODULE_NONANSI_2D = """\
module test_nonansi_2d (a, b);
    input [1:0][7:0] a;
    output [3:0][1:0] b;
    wire [1:0][7:0] a;
    reg  [3:0][1:0] b;
endmodule
"""


def _module_node(tree, src):
    from verilog_mcp_server.indexer.verilog_parser import find_child

    def search(node):
        if node.type == "module_declaration":
            return node
        for i in range(node.child_count):
            r = search(node.child(i))
            if r:
                return r
        return None

    return search(tree.root_node)


def test_net_declaration_2d_packed():
    ex = SignalExtractor()
    tree, src = parse_source(MODULE_2D)
    sigs = {s.name: s for s in ex.extract_signals(_module_node(tree, src), src)}
    assert sigs["bus"].width_range == "[1:0][27:0]"
    assert sigs["regs"].width_range == "[3:0][7:0]"
    assert sigs["lg"].width_range == "[2:0][5:0]"


def test_data_declaration_2d_packed():
    ex = SignalExtractor()
    tree, src = parse_source(MODULE_2D)
    sigs = {s.name: s for s in ex.extract_signals(_module_node(tree, src), src)}
    # regs/lg 走 data_declaration 分支，上面已断言；此处补单维回归
    assert sigs["plain"].width_range == "[7:0]"
    assert sigs["flat"].width_range is None


def test_ansi_port_2d_packed():
    ex = PortExtractor()
    tree, src = parse_source(MODULE_2D)
    node = _module_node(tree, src)
    ports = {p.name: p for p in ex.extract_from_module(node, src)}
    assert ports["din"].width_range == "[1:0][7:0]"
    assert ports["dout"].width_range == "[1:0][27:0]"


def test_nonansi_port_2d_packed():
    ex = PortExtractor()
    tree, src = parse_source(MODULE_NONANSI_2D)
    node = _module_node(tree, src)
    ports = {p.name: p for p in ex.extract_from_module(node, src)}
    assert ports["a"].width_range == "[1:0][7:0]"
    assert ports["b"].width_range == "[3:0][1:0]"


# ── 刀② 实例数组基名匹配 ──

def _make_store(tmp_path):
    store = IndexStore(db_path=str(tmp_path / "t.db"))
    child = ModuleDef(name="CPM_REG_E", file_path="c.v")
    child.ports = [PortDef(name="Clk", direction="input", var_type="wire"),
                   PortDef(name="DataOut", direction="output", var_type="wire", width_range="[27:0]")]
    parent = ModuleDef(name="HHE", file_path="p.v")
    parent.instances = [InstanceDef(
        module_type="CPM_REG_E",
        instance_name="u_CmbCfgInfoP[1:0]",
        port_connections={"Clk": "Clk", "DataOut": "CmbCfgInfo"},
    )]
    store.add_module(child)
    store.add_module(parent)
    return store


def test_instance_connections_bare_name_hits_array_entry(tmp_path):
    cr = CrossReference(_make_store(tmp_path))
    conns = cr.instance_connections("u_CmbCfgInfoP", "HHE")
    assert [c.formal_port for c in conns] == ["Clk", "DataOut"]


def test_instance_connections_element_name_hits_array_entry(tmp_path):
    cr = CrossReference(_make_store(tmp_path))
    conns = cr.instance_connections("u_CmbCfgInfoP[1]", "HHE")
    assert len(conns) == 2


def test_instance_connections_suffixed_name_still_exact(tmp_path):
    cr = CrossReference(_make_store(tmp_path))
    conns = cr.instance_connections("u_CmbCfgInfoP[1:0]", "HHE")
    assert len(conns) == 2


def test_instance_connections_unknown_still_raises(tmp_path):
    cr = CrossReference(_make_store(tmp_path))
    with pytest.raises(ValueError):
        cr.instance_connections("u_no_such", "HHE")


# ── 刀③ 增量失败告警 + file_meta 条件写 ──

@pytest.fixture
def b6_project(tmp_path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top (input clk);\n"
        "    wire [1:0][7:0] bus;\n"
        "endmodule\n")
    (rtl / "sub.v").write_text(
        "module sub (input clk);\n"
        "endmodule\n")
    return rtl


@pytest.fixture
def b6_config(b6_project, tmp_path):
    return {
        "index": {"paths": [str(b6_project)], "extensions": [".v", ".sv"],
                  "exclude_dirs": [], "exclude_files": [],
                  "language_map": {".v": "systemverilog"}},
        "cache": {"path": str(tmp_path / "cache.db"),
                  "auto_load": True, "auto_save": False},
    }


def _file_meta(store):
    return set(store._db.get_all_file_metas().keys())


def test_incremental_no_module_file_warns_and_skips_filemeta(b6_config, tmp_path, caplog):
    from verilog_mcp_server.indexer.builder import IndexBuilder
    store = IndexStore(db_path=b6_config["cache"]["path"])
    builder = IndexBuilder(b6_config, store)
    builder.build()
    assert store.has_module("top") and store.has_module("sub")

    # 新增一个合法但无模块声明的文件 → 增量路径 warning + file_meta 不写
    (tmp_path / "rtl" / "notes.v").write_text("// just a comment, no module\n")
    with caplog.at_level("WARNING"):
        builder.build_incremental()
    assert "本轮不入库" in caplog.text
    assert not any("notes.v" in p for p in _file_meta(store))


def test_incremental_broken_file_keeps_old_fingerprint(b6_config, tmp_path, caplog):
    from verilog_mcp_server.indexer.builder import IndexBuilder
    store = IndexStore(db_path=b6_config["cache"]["path"])
    builder = IndexBuilder(b6_config, store)
    builder.build()
    assert store.has_module("sub")

    # sub.v 改为无模块声明内容 → 增量后 modules 移除、file_meta 保留旧指纹
    # （修复前：file_meta 被无条件刷新 → 孤儿固化，mtime 不再变化后永不自愈）
    (tmp_path / "rtl" / "sub.v").write_text("// broken: module removed\n")
    with caplog.at_level("WARNING"):
        builder.build_incremental()
    assert "本轮不入库" in caplog.text
    assert not store.has_module("sub")
    assert any("sub.v" in p for p in _file_meta(store)), "旧指纹应保留以备自愈重扫"
