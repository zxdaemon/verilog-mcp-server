"""Test UvmHierarchyBuilder — UVM component tree building."""

import pytest
from verilog_mcp_server.database.models import ClassDef, UvmComponentDef
from verilog_mcp_server.analysis.uvm_hierarchy import UvmHierarchyBuilder


class FakeIndexStore:
    """Minimal fake for UvmHierarchyBuilder dependencies."""
    def __init__(self, classes=None):
        self._classes = classes or []

    def get_uvm_component_classes(self):
        return self._classes

    def get_class(self, name):
        for c in self._classes:
            if c.name == name:
                return c
        return None

    def get_uvm_hierarchy(self):
        return []

    def get_uvm_tlm_connections(self):
        return []

    def get_uvm_config_entries(self):
        return []

    def search_classes(self, pattern):
        return [c for c in self._classes if pattern.lower() in c.name.lower()]


class TestUvmHierarchyBuilder:
    def test_builder_initialization(self):
        store = FakeIndexStore()
        builder = UvmHierarchyBuilder(store)
        assert builder is not None

    def test_get_test_components_empty(self):
        store = FakeIndexStore()
        builder = UvmHierarchyBuilder(store)
        tests = builder.get_test_components()
        assert tests == []

    def test_get_test_components_finds_uvm_test(self):
        cls = ClassDef(
            name="base_test",
            extends="uvm_test",
            is_uvm_component=True,
            uvm_base_class="uvm_test",
            file_path="tb.sv",
            line=1,
        )
        store = FakeIndexStore([cls])
        builder = UvmHierarchyBuilder(store)
        tests = builder.get_test_components()
        assert len(tests) == 1
        assert tests[0].component_type == "base_test"
        assert tests[0].is_test is True

    def test_get_test_components_skips_non_test(self):
        agent = ClassDef(
            name="my_agent",
            extends="uvm_agent",
            is_uvm_component=True,
            uvm_base_class="uvm_agent",
            file_path="agent.sv",
            line=1,
        )
        store = FakeIndexStore([agent])
        builder = UvmHierarchyBuilder(store)
        tests = builder.get_test_components()
        assert tests == []

    def test_build_hierarchy_from_classes(self):
        from tree_sitter_language_pack import get_parser
        parser = get_parser("systemverilog")
        src = """
class my_test extends uvm_test;
  `uvm_component_utils(my_test)
  function void build_phase(uvm_phase phase);
    my_env env = my_env::type_id::create("env", this);
  endfunction
endclass
class my_env extends uvm_env;
  function void build_phase(uvm_phase phase);
    my_agent agt = my_agent::type_id::create("agt", this);
  endfunction
endclass
class my_agent extends uvm_agent;
  int cfg;
endclass
"""
        tree = parser.parse(src)

        from verilog_mcp_server.indexer.class_extractor import ClassExtractor
        extractor = ClassExtractor()
        classes = extractor.extract_from_source_file(tree, src, "test.sv")

        store = FakeIndexStore(classes)
        builder = UvmHierarchyBuilder(store)
        components = builder.build_hierarchy(tree, src, "test.sv", classes)

        assert len(components) >= 1
        test_comps = [c for c in components if c.is_test]
        assert len(test_comps) >= 1

    def test_format_hierarchy_text(self):
        store = FakeIndexStore()
        builder = UvmHierarchyBuilder(store)
        hierarchy = {
            "component_type": "base_test",
            "instance_name": "test",
            "children": [
                {
                    "component_type": "my_env",
                    "instance_name": "env",
                    "children": [],
                }
            ],
        }
        text = builder.format_hierarchy_text(hierarchy)
        assert "base_test" in text
        assert "my_env" in text
