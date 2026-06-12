"""测试 filelist 集成：+incdir+、+define+ 传递，CLI 参数"""
import os
import tempfile
import pytest
from pathlib import Path

from verilog_mcp_server.indexer.filelist_parser import FilelistParser
from verilog_mcp_server.indexer.project_scanner import ProjectScanner


class TestFilelistParser:
    """测试 FilelistParser 的 +define+ 提取"""

    def test_parse_define_simple(self, tmp_path):
        f = tmp_path / "test.f"
        f.write_text("+define+DEBUG\n+define+WIDTH=8\n")
        parser = FilelistParser()
        result = parser.parse(str(f))
        assert result["defines"] == {"DEBUG": "", "WIDTH": "8"}

    def test_parse_define_with_value(self, tmp_path):
        f = tmp_path / "test.f"
        f.write_text("+define+BUS_WIDTH=32\n+define+ADDR_SIZE=16\n")
        parser = FilelistParser()
        result = parser.parse(str(f))
        assert result["defines"]["BUS_WIDTH"] == "32"
        assert result["defines"]["ADDR_SIZE"] == "16"

    def test_parse_incdir(self, tmp_path):
        inc = tmp_path / "include"
        inc.mkdir()
        f = tmp_path / "test.f"
        f.write_text(f"+incdir+{inc}\n")
        parser = FilelistParser()
        result = parser.parse(str(f))
        assert str(inc) in result["incdirs"]

    def test_parse_define_recursive(self, tmp_path):
        """递归 -f 子文件的 defines 应合并"""
        sub = tmp_path / "sub.f"
        sub.write_text("+define+SUB_DEF=1\n")
        main = tmp_path / "main.f"
        main.write_text(f"+define+MAIN_DEF=2\n-f {sub}\n")
        parser = FilelistParser()
        result = parser.parse(str(main))
        assert result["defines"]["MAIN_DEF"] == "2"
        assert result["defines"]["SUB_DEF"] == "1"

    def test_parse_files_and_defines_together(self, tmp_path):
        sv = tmp_path / "test.sv"
        sv.write_text("module test; endmodule\n")
        f = tmp_path / "test.f"
        f.write_text(f"+define+SIM\n{sv}\n")
        parser = FilelistParser()
        result = parser.parse(str(f))
        assert len(result["files"]) == 1
        assert result["defines"]["SIM"] == ""


class TestProjectScanner:
    """测试 ProjectScanner 返回 filelist 元数据"""

    def test_scan_returns_tuple(self, tmp_path):
        sv = tmp_path / "test.sv"
        sv.write_text("module test; endmodule\n")
        f = tmp_path / "test.f"
        f.write_text(f"+define+SIM\n+incdir+{tmp_path}\n{sv}\n")
        scanner = ProjectScanner({"paths": [str(f)]})
        files, incdirs, defines = scanner.scan()
        assert isinstance(files, list)
        assert isinstance(incdirs, list)
        assert isinstance(defines, dict)
        assert len(files) == 1
        assert str(tmp_path) in incdirs
        assert "SIM" in defines

    def test_scan_directory_no_filelist(self, tmp_path):
        sv = tmp_path / "test.sv"
        sv.write_text("module test; endmodule\n")
        scanner = ProjectScanner({"paths": [str(tmp_path)]})
        files, incdirs, defines = scanner.scan()
        assert len(files) == 1
        assert incdirs == []
        assert defines == {}

    def test_scan_multiple_filelists_merge(self, tmp_path):
        sv1 = tmp_path / "a.sv"
        sv1.write_text("module a; endmodule\n")
        sv2 = tmp_path / "b.sv"
        sv2.write_text("module b; endmodule\n")
        f1 = tmp_path / "a.f"
        f1.write_text(f"+define+DEF_A\n+incdir+{tmp_path}\n{sv1}\n")
        f2 = tmp_path / "b.f"
        f2.write_text(f"+define+DEF_B\n{sv2}\n")
        scanner = ProjectScanner({"paths": [str(f1), str(f2)]})
        files, incdirs, defines = scanner.scan()
        assert len(files) == 2
        assert "DEF_A" in defines
        assert "DEF_B" in defines
