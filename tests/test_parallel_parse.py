"""测试并行解析支持"""

import os
import pytest
from pathlib import Path
from verilog_mcp_server.indexer.verilog_parser import parse_single_file, parse_file


class TestParallelParse:
    def test_parse_single_file(self, tmp_path):
        f = tmp_path / "test.v"
        f.write_text("module test(input clk, output reg [7:0] data); endmodule")
        result = parse_single_file(str(f))
        assert result is not None
        file_path, tree, src = result
        assert file_path == str(f)
        assert tree is not None
        assert "module test" in src

    def test_parse_single_file_missing(self):
        result = parse_single_file("/nonexistent/path/test.v")
        assert result is None

    def test_parse_file_standard(self, tmp_path):
        f = tmp_path / "mod.v"
        f.write_text("module mod(input a, output b); assign b = a; endmodule")
        result = parse_file(str(f))
        assert result is not None
        tree, src = result
        assert "module mod" in src


class TestParallelThreshold:
    """验证并行解析的基础设施就绪（实际多进程测试在集成验证中）"""

    def test_parse_single_file_returns_tuple(self, tmp_path):
        """parse_single_file 返回 (file_path, tree, source) 元组"""
        f = tmp_path / "p.v"
        f.write_text("module p(); endmodule")
        result = parse_single_file(str(f))
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_multiple_files_independent(self, tmp_path):
        """验证多个文件可独立解析"""
        modules = ["a", "b", "c"]
        files = []
        for m in modules:
            f = tmp_path / f"{m}.v"
            f.write_text(f"module {m}(); endmodule")
            files.append(str(f))

        results = []
        for f in files:
            r = parse_single_file(f)
            assert r is not None
            results.append(r)

        assert len(results) == 3
        for i, (path, tree, src) in enumerate(results):
            assert modules[i] in src
