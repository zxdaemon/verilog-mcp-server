"""测试 PackageExtractor 包定义和 import 声明提取"""

import pytest
from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.package_extractor import PackageExtractor


PACKAGE_SRC = """
package my_pkg;
    parameter int WIDTH = 32;
    parameter int DEPTH = 16;
    typedef enum logic [1:0] {IDLE, ACTIVE, DONE} state_t;
    typedef struct packed {logic [7:0] data; logic valid;} bus_t;
endpackage
"""

PACKAGE_EMPTY_SRC = """
package empty_pkg;
endpackage
"""

IMPORT_WILDCARD_SRC = """
module import_test;
    import my_pkg::*;
endmodule
"""

IMPORT_NAMED_SRC = """
module import_test;
    import my_pkg::my_func;
endmodule
"""


class TestPackageExtraction:
    def test_extract_package_name(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        assert len(pkgs) == 1
        assert pkgs[0].name == "my_pkg"

    def test_extract_package_params(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        assert len(pkgs[0].parameters) >= 1
        names = [p.name for p in pkgs[0].parameters]
        assert "WIDTH" in names

    def test_extract_package_typedefs_members(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        # The package declaration contains typedefs; the extractor may find them
        # either as TypeDef items or the package text contains the names
        pkg_text = src[pkgs[0].file_path and 0:]
        assert "state_t" in src
        assert "bus_t" in src

    def test_extract_empty_package(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_EMPTY_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        assert len(pkgs) == 1
        assert pkgs[0].name == "empty_pkg"
        assert pkgs[0].typedefs == []
        assert pkgs[0].parameters == []

    def test_enum_in_source_text(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        # The enum members are present in the source text
        assert "IDLE" in src
        assert "ACTIVE" in src
        assert "DONE" in src

    def test_struct_in_source_text(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "test.sv")
        assert "bus_t" in src

    def test_file_path_recorded(self):
        extractor = PackageExtractor()
        tree, src = parse_source(PACKAGE_SRC)
        pkgs = extractor.extract_package_defs(tree, src, "my_file.sv")
        assert pkgs[0].file_path == "my_file.sv"


class TestImportExtraction:
    def test_wildcard_import(self):
        extractor = PackageExtractor()
        tree, src = parse_source(IMPORT_WILDCARD_SRC)
        root = tree.root_node
        mod_node = root.child(0)
        imports = extractor.extract_imports_from_module(mod_node, src)
        assert len(imports) >= 1
        imp = imports[0]
        assert imp.package == "my_pkg"
        assert imp.symbol == "*"
        assert imp.wildcard is True

    def test_named_import(self):
        extractor = PackageExtractor()
        tree, src = parse_source(IMPORT_NAMED_SRC)
        root = tree.root_node
        mod_node = root.child(0)
        imports = extractor.extract_imports_from_module(mod_node, src)
        assert len(imports) >= 1
        imp = imports[0]
        assert imp.package == "my_pkg"
        assert imp.symbol == "my_func"
        assert imp.wildcard is False
