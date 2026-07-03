"""Test ClassExtractor — class definition extraction."""

import pytest
from tree_sitter_language_pack import get_parser

from verilog_mcp_server.indexer.class_extractor import ClassExtractor


@pytest.fixture
def parser():
    return get_parser("systemverilog")


@pytest.fixture
def extractor():
    return ClassExtractor()


def parse(parser, src: str):
    return parser.parse(src)


class TestBasicClassExtraction:
    def test_simple_class(self, parser, extractor):
        src = "class my_class; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes) == 1
        assert classes[0].name == "my_class"
        assert classes[0].extends == ""

    def test_class_with_extends(self, parser, extractor):
        src = "class my_agent extends uvm_agent; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes) == 1
        assert classes[0].name == "my_agent"
        assert classes[0].extends == "uvm_agent"

    def test_multiple_classes(self, parser, extractor):
        src = """
class foo; int a; endclass
class bar extends foo; int b; endclass
"""
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes) == 2
        names = {c.name for c in classes}
        assert names == {"foo", "bar"}

    def test_class_file_path_and_line(self, parser, extractor):
        src = "class my_class; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].file_path == "test.sv"
        assert classes[0].line > 0


class TestClassMembers:
    def test_member_variables(self, parser, extractor):
        src = "class my_class; int x; string name; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes[0].member_vars) == 2
        names = {v["name"] for v in classes[0].member_vars}
        assert names == {"x", "name"}

    def test_method_extraction(self, parser, extractor):
        src = """
class my_class;
  function void do_stuff(int x);
    return;
  endfunction
endclass
"""
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes[0].methods) == 1
        assert classes[0].methods[0]["name"] == "do_stuff"
        assert classes[0].methods[0]["method_type"] == "function"

    def test_task_extraction(self, parser, extractor):
        src = """
class my_class;
  task run_phase(uvm_phase phase);
  endtask
endclass
"""
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert len(classes[0].methods) == 1
        m = classes[0].methods[0]
        assert m["name"] == "run_phase"
        assert m["method_type"] == "task"


class TestUvmDetection:
    def test_direct_uvm_extends(self, parser, extractor):
        src = "class my_agent extends uvm_agent; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].is_uvm_component is True
        assert classes[0].uvm_base_class == "uvm_agent"

    def test_indirect_uvm_extends(self, parser, extractor):
        src = """
class my_base extends uvm_component; int x; endclass
class my_agent extends my_base; int y; endclass
"""
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        agent = [c for c in classes if c.name == "my_agent"][0]
        assert agent.is_uvm_component is True
        assert agent.uvm_base_class == "uvm_component"

    def test_uvm_component_utils_macro(self, parser, extractor):
        src = "class my_test extends uvm_test; `uvm_component_utils(my_test) int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].is_uvm_component is True

    def test_non_uvm_class(self, parser, extractor):
        src = "class plain_class; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].is_uvm_component is False
        assert classes[0].uvm_base_class == ""

    def test_uvm_test_detection(self, parser, extractor):
        src = "class base_test extends uvm_test; int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].is_uvm_component is True
        assert classes[0].uvm_base_class == "uvm_test"


class TestParameterizedClass:
    def test_parameterized_extends(self, parser, extractor):
        src = "class my_class extends base_class #(.WIDTH(32)); int x; endclass"
        tree = parse(parser, src)
        classes = extractor.extract_from_source_file(tree, src, "test.sv")
        assert classes[0].extends == "base_class"
        assert "WIDTH" in classes[0].type_params
