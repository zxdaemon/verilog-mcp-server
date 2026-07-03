"""测试 SQLiteBackend 的 CRUD 操作"""

import pytest
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, ParamDef, SignalDef, InstanceDef,
    AlwaysBlockInfo, AssignmentInfo, TypeDef,
    PackageDef, FunctionDef,
)
from verilog_mcp_server.database.sqlite_backend import SQLiteBackend


@pytest.fixture
def db(tmp_path):
    backend = SQLiteBackend(str(tmp_path / "test.db"))
    yield backend
    backend.close()


@pytest.fixture
def sample_module():
    return ModuleDef(
        name="alu",
        file_path="rtl/alu.v",
        line_start=1,
        line_end=50,
        ports=[
            PortDef(name="a", direction="input", width_range="[7:0]"),
            PortDef(name="b", direction="input", width_range="[7:0]"),
            PortDef(name="out", direction="output", width_range="[7:0]"),
        ],
        parameters=[ParamDef(name="WIDTH", default_value="8")],
        signals=[SignalDef(name="tmp", var_type="wire")],
        instances=[],
        always_blocks=[],
        assignments=[AssignmentInfo(lhs="out", rhs="a + b", file_path="rtl/alu.v", line=20)],
    )


def test_save_and_load_module(db, sample_module):
    db.save_module(sample_module)
    loaded = db.load_module("alu")
    assert loaded is not None
    assert loaded.name == "alu"
    assert loaded.file_path == "rtl/alu.v"
    assert len(loaded.ports) == 3
    assert loaded.ports[0].name == "a"


def test_load_nonexistent_module(db):
    assert db.load_module("nonexistent") is None


def test_load_all_modules(db, sample_module):
    db.save_module(sample_module)
    mod2 = ModuleDef(name="ctrl", file_path="rtl/ctrl.v")
    db.save_module(mod2)
    all_mods = db.load_all_modules()
    assert len(all_mods) == 2
    names = {m.name for m in all_mods}
    assert names == {"alu", "ctrl"}


def test_load_module_names(db, sample_module):
    db.save_module(sample_module)
    names = db.load_module_names()
    assert names == ["alu"]


def test_delete_module(db, sample_module):
    db.save_module(sample_module)
    db.delete_module("alu")
    assert db.load_module("alu") is None
    # signal_index 也应被清理
    assert db.search_signal_index("a") == []


def test_delete_modules_by_file(db, sample_module):
    mod2 = ModuleDef(name="alu_sub", file_path="rtl/alu.v")
    db.save_module(sample_module)
    db.save_module(mod2)
    db.delete_modules_by_file("rtl/alu.v")
    assert db.load_module("alu") is None
    assert db.load_module("alu_sub") is None


def test_search_modules(db, sample_module):
    db.save_module(sample_module)
    db.save_module(ModuleDef(name="alu_top", file_path="rtl/top.v"))
    results = db.search_modules("alu")
    assert len(results) == 2
    names = [m.name for m in results]
    assert "alu" in names
    assert "alu_top" in names


def test_signal_index(db, sample_module):
    db.save_module(sample_module)
    # 精确搜索
    results = db.search_signal_index("a")
    assert ("alu", "a") in results
    # 模糊搜索
    results = db.search_signal_index_fuzzy("ou")
    assert ("alu", "out") in results


def test_signal_index_with_module_filter(db, sample_module):
    db.save_module(sample_module)
    db.save_module(ModuleDef(name="ctrl", file_path="rtl/ctrl.v",
                             ports=[PortDef(name="a", direction="input")]))
    results = db.search_signal_index("a", module_name="alu")
    assert len(results) == 1
    assert results[0] == ("alu", "a")


def test_save_and_load_type(db):
    td = TypeDef(name="state_t", kind="enum", members=["IDLE", "RUN"])
    db.save_type(td)
    loaded = db.load_type("state_t")
    assert loaded is not None
    assert loaded.name == "state_t"
    assert loaded.kind == "enum"
    assert loaded.members == ["IDLE", "RUN"]


def test_load_all_types(db):
    db.save_type(TypeDef(name="state_t", kind="enum"))
    db.save_type(TypeDef(name="data_t", kind="struct", members=["a", "b"]))
    types = db.load_all_types()
    assert len(types) == 2


def test_file_meta(db):
    db.set_file_meta("rtl/top.v", 1234567890.0, "abc123")
    meta = db.get_file_meta("rtl/top.v")
    assert meta is not None
    assert meta["mtime"] == 1234567890.0
    assert meta["sha256"] == "abc123"


def test_file_meta_nonexistent(db):
    assert db.get_file_meta("nonexistent.v") is None


def test_delete_file_meta(db):
    db.set_file_meta("rtl/top.v", 1.0, "x")
    db.delete_file_meta("rtl/top.v")
    assert db.get_file_meta("rtl/top.v") is None


def test_get_all_file_metas(db):
    db.set_file_meta("a.v", 1.0, "x")
    db.set_file_meta("b.v", 2.0, "y")
    metas = db.get_all_file_metas()
    assert len(metas) == 2
    assert metas["a.v"]["mtime"] == 1.0


def test_clear_all(db, sample_module):
    db.save_module(sample_module)
    db.save_type(TypeDef(name="t", kind="enum"))
    db.set_file_meta("f.v", 1.0, "x")
    db.clear_all()
    assert db.load_all_modules() == []
    assert db.load_all_types() == []
    assert db.get_all_file_metas() == {}


def test_save_and_load_package(db):
    pkg = PackageDef(
        name="my_pkg",
        file_path="rtl/pkg.sv",
        typedefs=[TypeDef(name="state_t", kind="enum", members=["IDLE", "RUN"])],
        parameters=[ParamDef(name="WIDTH", default_value="32")],
    )
    db.save_package(pkg)
    loaded = db.load_package("my_pkg")
    assert loaded is not None
    assert loaded.name == "my_pkg"
    assert loaded.file_path == "rtl/pkg.sv"
    assert len(loaded.typedefs) == 1
    assert loaded.typedefs[0].name == "state_t"
    assert len(loaded.parameters) == 1


def test_load_all_packages(db):
    db.save_package(PackageDef(name="a_pkg", file_path="a.sv"))
    db.save_package(PackageDef(name="b_pkg", file_path="b.sv"))
    pkgs = db.load_all_packages()
    assert len(pkgs) == 2
    names = {p.name for p in pkgs}
    assert names == {"a_pkg", "b_pkg"}


def test_save_and_load_function(db):
    func = FunctionDef(
        name="adder",
        kind="function",
        return_type="logic [7:0]",
        ports=[PortDef(name="a", direction="input"), PortDef(name="b", direction="input")],
        file_path="rtl/func.sv",
        line=10,
    )
    db.save_function(func)
    loaded = db.load_function("adder")
    assert loaded is not None
    assert loaded.name == "adder"
    assert loaded.return_type == "logic [7:0]"
    assert len(loaded.ports) == 2
    assert loaded.ports[0].direction == "input"


def test_load_all_functions(db):
    db.save_function(FunctionDef(name="double", kind="function"))
    db.save_function(FunctionDef(name="drive_bus", kind="task"))
    funcs = db.load_all_functions()
    assert len(funcs) == 2
    names = {f.name for f in funcs}
    assert names == {"double", "drive_bus"}


def test_clear_all_clears_packages_and_functions(db):
    db.save_package(PackageDef(name="p", file_path="p.sv"))
    db.save_function(FunctionDef(name="f", kind="function"))
    db.clear_all()
    assert db.load_all_packages() == []
    assert db.load_all_functions() == []


def test_module_with_complex_port_connections(db):
    mod = ModuleDef(
        name="top", file_path="top.v",
        instances=[
            InstanceDef(module_type="sub", instance_name="u_sub",
                        port_connections={"clk": "clk", "data_in": "bus_data[7:0]",
                                          "data_out": "result"},
                        param_overrides={"DEPTH": "16"}),
        ],
    )
    db.save_module(mod)
    loaded = db.load_module("top")
    inst = loaded.instances[0]
    assert inst.port_connections["data_in"] == "bus_data[7:0]"
    assert inst.param_overrides["DEPTH"] == "16"
