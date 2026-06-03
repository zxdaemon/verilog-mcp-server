"""测试旧 JSON 缓存迁移到 SQLite"""

import json
import pytest
from verilog_mcp_server.database.models import ModuleDef, PortDef
from verilog_mcp_server.database.index_store import IndexStore


@pytest.fixture
def json_cache(tmp_path):
    """创建一个旧版 JSON 缓存文件"""
    data = {
        "modules": {
            "alu": {
                "name": "alu",
                "file_path": "rtl/alu.v",
                "line_start": 1,
                "line_end": 50,
                "ports": [
                    {"name": "a", "direction": "input", "width_range": "[7:0]",
                     "var_type": "wire", "signed": False, "description": ""},
                    {"name": "out", "direction": "output", "width_range": "[7:0]",
                     "var_type": "wire", "signed": False, "description": ""},
                ],
                "parameters": [],
                "signals": [],
                "instances": [],
                "always_blocks": [],
                "assignments": [],
            },
            "ctrl": {
                "name": "ctrl",
                "file_path": "rtl/ctrl.v",
                "line_start": 1,
                "line_end": 30,
                "ports": [{"name": "clk", "direction": "input", "width_range": None,
                           "var_type": "wire", "signed": False, "description": ""}],
                "parameters": [],
                "signals": [],
                "instances": [],
                "always_blocks": [],
                "assignments": [],
            },
        },
        "files": {
            "rtl/alu.v": ["alu"],
            "rtl/ctrl.v": ["ctrl"],
        },
    }
    json_path = tmp_path / "cache.json"
    with open(json_path, "w") as f:
        json.dump(data, f)
    return str(json_path)


def test_migrate_from_json(tmp_path, json_cache):
    db_path = str(tmp_path / "cache.db")
    store = IndexStore(db_path=db_path)
    assert store.module_count == 0

    result = store.migrate_from_json(json_cache)
    assert result is True
    assert store.module_count == 2

    alu = store.get_module("alu")
    assert alu is not None
    assert alu.name == "alu"
    assert len(alu.ports) == 2
    assert alu.ports[0].name == "a"

    ctrl = store.get_module("ctrl")
    assert ctrl is not None
    assert ctrl.name == "ctrl"


def test_migrate_persists_to_sqlite(tmp_path, json_cache):
    db_path = str(tmp_path / "cache.db")
    store1 = IndexStore(db_path=db_path)
    store1.migrate_from_json(json_cache)

    # 新实例应能从 SQLite 加载
    store2 = IndexStore(db_path=db_path)
    assert store2.module_count == 2
    assert store2.get_module("alu") is not None


def test_migrate_nonexistent_json(tmp_path):
    db_path = str(tmp_path / "cache.db")
    store = IndexStore(db_path=db_path)
    result = store.migrate_from_json("/nonexistent/path.json")
    assert result is False


def test_migrate_without_db(tmp_path, json_cache):
    store = IndexStore()
    result = store.migrate_from_json(json_cache)
    assert result is False
