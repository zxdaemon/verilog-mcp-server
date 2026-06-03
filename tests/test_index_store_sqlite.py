"""测试 IndexStore 的 SQLite 集成"""

import pytest
from verilog_mcp_server.database.models import ModuleDef, PortDef, SignalDef, TypeDef
from verilog_mcp_server.database.index_store import IndexStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    return IndexStore(db_path=db_path)


@pytest.fixture
def sample_module():
    return ModuleDef(
        name="alu",
        file_path="rtl/alu.v",
        line_start=1,
        line_end=50,
        ports=[PortDef(name="a", direction="input"), PortDef(name="out", direction="output")],
        signals=[SignalDef(name="tmp", var_type="wire")],
    )


def test_add_and_get_module(store, sample_module):
    store.add_module(sample_module)
    loaded = store.get_module("alu")
    assert loaded is not None
    assert loaded.name == "alu"
    assert len(loaded.ports) == 2


def test_get_module_cache_hit(store, sample_module):
    store.add_module(sample_module)
    # 第二次从缓存获取
    loaded = store.get_module("alu")
    assert loaded is not None
    assert loaded.name == "alu"


def test_get_nonexistent_module(store):
    assert store.get_module("nonexistent") is None


def test_get_all_modules(store, sample_module):
    store.add_module(sample_module)
    store.add_module(ModuleDef(name="ctrl", file_path="rtl/ctrl.v"))
    all_mods = store.get_all_modules()
    assert len(all_mods) == 2


def test_get_module_names(store, sample_module):
    store.add_module(sample_module)
    names = store.get_module_names()
    assert "alu" in names


def test_module_count(store, sample_module):
    assert store.module_count == 0
    store.add_module(sample_module)
    assert store.module_count == 1


def test_has_module(store, sample_module):
    assert not store.has_module("alu")
    store.add_module(sample_module)
    assert store.has_module("alu")


def test_search_modules(store, sample_module):
    store.add_module(sample_module)
    store.add_module(ModuleDef(name="alu_top", file_path="rtl/top.v"))
    results = store.search_modules("alu")
    assert len(results) == 2


def test_search_signals(store, sample_module):
    store.add_module(sample_module)
    results = store.search_signals("a")
    assert len(results) == 1
    assert results[0][0].name == "alu"
    assert results[0][1] == "a"


def test_search_signals_with_module_filter(store, sample_module):
    store.add_module(sample_module)
    store.add_module(ModuleDef(name="ctrl", file_path="rtl/ctrl.v",
                               ports=[PortDef(name="a", direction="input")]))
    results = store.search_signals("a", module_name="alu")
    assert len(results) == 1


def test_get_modules_for_file(store, sample_module):
    store.add_module(sample_module)
    mods = store.get_modules_for_file("rtl/alu.v")
    assert len(mods) == 1
    assert mods[0].name == "alu"


def test_get_module_for_line(store, sample_module):
    store.add_module(sample_module)
    mod = store.get_module_for_line("rtl/alu.v", 25)
    assert mod is not None
    assert mod.name == "alu"
    assert store.get_module_for_line("rtl/alu.v", 999) is None


def test_remove_file(store, sample_module):
    store.add_module(sample_module)
    store.remove_file("rtl/alu.v")
    assert store.get_module("alu") is None
    assert store.module_count == 0
    assert store.get_modules_for_file("rtl/alu.v") == []


def test_remove_nonexistent_file(store):
    store.remove_file("nonexistent.v")  # should not raise


def test_clear(store, sample_module):
    store.add_module(sample_module)
    store.add_type(TypeDef(name="t", kind="enum"))
    store.clear()
    assert store.module_count == 0
    assert store.get_all_types() == []


def test_add_type(store):
    td = TypeDef(name="state_t", kind="enum", members=["IDLE", "RUN"])
    store.add_type(td)
    loaded = store.get_type("state_t")
    assert loaded is not None
    assert loaded.members == ["IDLE", "RUN"]


def test_get_all_types(store):
    store.add_type(TypeDef(name="a", kind="enum"))
    store.add_type(TypeDef(name="b", kind="struct"))
    types = store.get_all_types()
    assert len(types) == 2


def test_module_update_replaces_old(store, sample_module):
    store.add_module(sample_module)
    updated = ModuleDef(
        name="alu", file_path="rtl/alu_v2.v", line_start=10, line_end=100,
        ports=[PortDef(name="x", direction="input")],
    )
    store.add_module(updated)
    loaded = store.get_module("alu")
    assert loaded.file_path == "rtl/alu_v2.v"
    assert len(loaded.ports) == 1
    assert loaded.ports[0].name == "x"
    # 旧文件路径下不应再有模块
    assert store.get_modules_for_file("rtl/alu.v") == []


def test_persistence_across_instances(tmp_path, sample_module):
    db_path = str(tmp_path / "test.db")
    store1 = IndexStore(db_path=db_path)
    store1.add_module(sample_module)
    store1.save()

    store2 = IndexStore(db_path=db_path)
    loaded = store2.get_module("alu")
    assert loaded is not None
    assert loaded.name == "alu"
    assert len(loaded.ports) == 2
