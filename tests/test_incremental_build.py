"""测试增量构建流程"""

import os
import pytest
from pathlib import Path
from verilog_mcp_server.indexer.builder import IndexBuilder
from verilog_mcp_server.database.index_store import IndexStore


@pytest.fixture
def rtl_project(tmp_path):
    """创建一个小型 RTL 项目"""
    rtl_dir = tmp_path / "rtl"
    rtl_dir.mkdir()

    # 主模块
    (rtl_dir / "top.v").write_text("""\
module top (
    input  clk,
    input  rst_n,
    output [7:0] data_out
);
    sub u_sub (.clk(clk), .data(data_out));
endmodule
""")

    # 子模块
    (rtl_dir / "sub.v").write_text("""\
module sub (
    input  clk,
    output [7:0] data
);
    reg [7:0] counter;
    assign data = counter;
    always @(posedge clk) begin
        counter <= counter + 1;
    end
endmodule
""")

    return rtl_dir


@pytest.fixture
def config(rtl_project, tmp_path):
    return {
        "index": {
            "paths": [str(rtl_project)],
            "extensions": [".v", ".sv", ".svh"],
            "exclude_dirs": [],
            "exclude_files": [],
            "language_map": {".v": "systemverilog"},
        },
        "cache": {
            "path": str(tmp_path / "cache.db"),
            "auto_load": True,
            "auto_save": False,
        },
    }


@pytest.fixture
def store(config):
    db_path = config["cache"]["path"]
    return IndexStore(db_path=db_path)


def test_full_build(config, store):
    builder = IndexBuilder(config, store)
    builder.build()
    assert store.module_count == 2
    assert store.has_module("top")
    assert store.has_module("sub")


def test_incremental_no_changes(config, store):
    builder = IndexBuilder(config, store)
    builder.build()
    initial_count = store.module_count

    # 增量构建无变更文件
    builder.build_incremental(changed_files=[])
    assert store.module_count == initial_count


def test_incremental_single_file(config, store, rtl_project):
    builder = IndexBuilder(config, store)
    builder.build()
    assert store.has_module("sub")

    # 修改 sub.v
    (rtl_project / "sub.v").write_text("""\
module sub (
    input  clk,
    input  en,
    output [7:0] data
);
    reg [7:0] counter;
    assign data = counter;
    always @(posedge clk) begin
        if (en)
            counter <= counter + 1;
    end
endmodule
""")

    builder.build_incremental(changed_files=[str(rtl_project / "sub.v")])
    assert store.module_count == 2
    sub = store.get_module("sub")
    assert sub is not None
    # 新端口 en 应存在
    port_names = [p.name for p in sub.ports]
    assert "en" in port_names


def test_incremental_detect_deleted_file(config, store, rtl_project):
    builder = IndexBuilder(config, store)
    builder.build()
    assert store.has_module("sub")

    # 删除 sub.v
    (rtl_project / "sub.v").unlink()

    builder.build_incremental(changed_files=[])
    assert store.module_count == 1
    assert not store.has_module("sub")
    assert store.has_module("top")


def test_incremental_detect_new_file(config, store, rtl_project):
    builder = IndexBuilder(config, store)
    builder.build()
    assert store.module_count == 2

    # 新增文件
    (rtl_project / "adder.v").write_text("""\
module adder (
    input [7:0] a,
    input [7:0] b,
    output [8:0] sum
);
    assign sum = a + b;
endmodule
""")

    builder.build_incremental(changed_files=[])
    assert store.module_count == 3
    assert store.has_module("adder")


def test_compute_file_hash_deterministic(tmp_path):
    f = tmp_path / "test.v"
    f.write_text("module test; endmodule")
    h1 = IndexBuilder._compute_file_hash(str(f))
    h2 = IndexBuilder._compute_file_hash(str(f))
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_compute_file_hash_detects_change(tmp_path):
    f = tmp_path / "test.v"
    f.write_text("module test; endmodule")
    h1 = IndexBuilder._compute_file_hash(str(f))
    f.write_text("module test_modified; endmodule")
    h2 = IndexBuilder._compute_file_hash(str(f))
    assert h1 != h2


def test_build_incremental_parameter(config, store):
    """测试 build(incremental=True) 路径"""
    builder = IndexBuilder(config, store)
    builder.build(incremental=True)
    # 首次增量构建应发现所有新文件
    assert store.module_count == 2
