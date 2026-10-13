"""VMS-09 回归：hierarchy elab 子树按路径前缀构建（不漏不过收）"""
import pytest

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, InstanceDef, ElaboratedInstanceDef,
)
from verilog_mcp_server.tools.level2_relation import _do_hierarchy_instances


def _elab(name, mtype, path, parent="", generated=False):
    return ElaboratedInstanceDef(
        instance_name=name, module_type=mtype, hierarchical_path=path,
        parent_module=parent, is_generated=generated, file_path="", line=0,
    )


def make_store(tmp_path) -> IndexStore:
    """带临时 DB 的 store：elab 路径中实例名刻意 ≠ 模块类型（u_hhe→HHE / core→CORE），
    parent_module 字段填旧实现的错误形态以证明修复不依赖它
    （save/get_elab_instances 走 DB 后端，须给 db_path）"""
    store = IndexStore(db_path=str(tmp_path / "hier.db"))
    for name in ("top", "HHE", "CORE", "LEAF", "DISTRACT", "ORPH"):
        store.add_module(ModuleDef(
            name=name, file_path=f"{name}.v", line_start=1, line_end=10,
            ports=[PortDef(name="clk", direction="input")],
        ))
    # tree-sitter 静态实例（回退路径用）：top 例化 ORPH
    top = store.get_module("top")
    top.instances.append(InstanceDef(
        module_type="ORPH", instance_name="u_orph",
        port_connections={}, file_path="top.v", line=5,
    ))
    store.save_elab_instances([
        _elab("top", "top", "top"),
        _elab("u_hhe", "HHE", "top.u_hhe", parent="top"),
        _elab("dist", "DISTRACT", "top.dist", parent="top"),
        _elab("core", "CORE", "top.u_hhe.core", parent="u_hhe"),
        _elab("leaf_a", "LEAF", "top.u_hhe.core.leaf_a", parent="core"),
        _elab("", "LEAF", "top.u_hhe.core.arr[0]", parent="core", generated=True),
        _elab("", "LEAF", "top.u_hhe.core.arr[1]", parent="core", generated=True),
        # generate 域实例：父段 top.u_hhe.g 非实例路径，须解析到 top.u_hhe
        _elab("", "LEAF", "top.u_hhe.g.w[0]", parent="", generated=True),
    ])
    return store


class TestElabSubtree:
    def test_subtree_no_forest_leak(self, tmp_path):
        """请求 HHE 子树：只含 HHE 后代，顶层兄弟（DISTRACT/top）不泄漏"""
        rows = _do_hierarchy_instances(make_store(tmp_path), "HHE", max_depth=10)
        paths = [r["instance_path"] for r in rows]
        assert paths == [
            "top.u_hhe.core",
            "top.u_hhe.core.leaf_a",
            "top.u_hhe.core.arr[0]",
            "top.u_hhe.core.arr[1]",
            "top.u_hhe.g.w[0]",
        ]

    def test_generate_scope_children_resolved(self, tmp_path):
        """generate 域实例（中间段 g 非实例）仍挂到正确实例父"""
        rows = _do_hierarchy_instances(make_store(tmp_path), "HHE", max_depth=10)
        gen = [r for r in rows if r["instance_path"] == "top.u_hhe.g.w[0]"]
        assert len(gen) == 1 and gen[0]["is_generated"]

    def test_multiple_roots_all_listed(self, tmp_path):
        """类型多处例化（LEAF ×4）：每处各自成根且计入扁平列表"""
        rows = _do_hierarchy_instances(make_store(tmp_path), "LEAF", max_depth=10)
        paths = {r["instance_path"] for r in rows}
        assert paths == {
            "top.u_hhe.core.leaf_a",
            "top.u_hhe.core.arr[0]",
            "top.u_hhe.core.arr[1]",
            "top.u_hhe.g.w[0]",
        }

    def test_uninstantiated_falls_back_to_treesitter(self, tmp_path):
        """elab 无实例的类型（ORPH）回退 tree-sitter 静态展开，不抛错"""
        rows = _do_hierarchy_instances(make_store(tmp_path), "ORPH", max_depth=10)
        assert rows == []  # ORPH 自身无子级，但能建树不抛错

    def test_unknown_module_raises(self):
        with pytest.raises(Exception):
            _do_hierarchy_instances(make_store(tmp_path), "NO_SUCH", max_depth=10)
