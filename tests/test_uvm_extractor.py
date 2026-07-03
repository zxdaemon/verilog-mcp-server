"""Test UvmExtractor — UVM pattern extraction helpers."""

import pytest
from tree_sitter_language_pack import get_parser

from verilog_mcp_server.indexer.uvm_extractor import UvmExtractor


@pytest.fixture
def parser():
    return get_parser("systemverilog")


@pytest.fixture
def extractor():
    return UvmExtractor()


def parse(parser, src: str):
    return parser.parse(src)


class TestCreateCalls:
    def test_find_create_call(self, parser, extractor):
        src = """
function void build_phase(uvm_phase phase);
  my_agent agt = my_agent::type_id::create("agt", this);
endfunction
"""
        tree = parse(parser, src)
        calls = extractor.find_create_calls(tree.root_node(), src)
        assert len(calls) >= 1
        assert calls[0]["instance_name"] == "agt"

    def test_create_call_detects_component_type(self, parser, extractor):
        src = """
function void build_phase(uvm_phase phase);
  my_driver drv = my_driver::type_id::create("drv", this);
endfunction
"""
        tree = parse(parser, src)
        calls = extractor.find_create_calls(tree.root_node(), src)
        assert len(calls) >= 1
        assert calls[0]["component_type"] == "my_driver"


class TestConfigDbCalls:
    def test_find_config_db_set(self, parser, extractor):
        src = """
function void build_phase(uvm_phase phase);
  uvm_config_db#(int)::set(this, "agt.*", "count", 42);
endfunction
"""
        tree = parse(parser, src)
        calls = extractor.find_config_db_calls(tree.root_node(), src)
        assert len(calls) >= 1
        assert calls[0]["operation"] == "set"
        assert calls[0]["field_name"] == "count"
        assert calls[0]["type_param"] == "int"

    def test_find_config_db_get(self, parser, extractor):
        src = """
function void build_phase(uvm_phase phase);
  uvm_config_db#(virtual my_if)::get(this, "", "vif", vif);
endfunction
"""
        tree = parse(parser, src)
        calls = extractor.find_config_db_calls(tree.root_node(), src)
        assert len(calls) >= 1
        assert calls[0]["operation"] == "get"
        assert calls[0]["field_name"] == "vif"


class TestTlmPortDeclarations:
    def test_tlm_analysis_port(self, parser, extractor):
        src = "class my_monitor extends uvm_monitor; uvm_analysis_port#(my_trans) mon_ap; endclass"
        tree = parse(parser, src)
        root = tree.root_node()
        # Find class_declaration node
        for i in range(root.child_count()):
            if root.child(i).kind() == "class_declaration":
                ports = extractor.find_tlm_port_declarations(root.child(i), src)
                assert len(ports) >= 1
                assert ports[0]["port_name"] == "mon_ap"
                assert ports[0]["port_type"] == "uvm_analysis_port"
                return
        pytest.fail("No class_declaration found")

    def test_tlm_blocking_put_port(self, parser, extractor):
        src = "class my_driver extends uvm_driver; uvm_blocking_put_port#(my_trans) put_port; endclass"
        tree = parse(parser, src)
        root = tree.root_node()
        for i in range(root.child_count()):
            if root.child(i).kind() == "class_declaration":
                ports = extractor.find_tlm_port_declarations(root.child(i), src)
                assert len(ports) >= 1
                assert ports[0]["port_type"] == "uvm_blocking_put_port"
                return
        pytest.fail("No class_declaration found")


class TestTlmConnections:
    def test_find_connect_call(self, parser, extractor):
        src = """
function void connect_phase(uvm_phase phase);
  agt.mon_ap.connect(sb.analysis_export);
endfunction
"""
        tree = parse(parser, src)
        connects = extractor.find_tlm_connections(tree.root_node(), src)
        assert len(connects) >= 1
        assert "connect" in connects[0]["source_port"]
        assert connects[0]["target_port"] == "sb.analysis_export"


class TestNewCalls:
    def test_find_new_call(self, parser, extractor):
        src = """
function void build_phase(uvm_phase phase);
  my_component comp = new("comp", this);
endfunction
"""
        tree = parse(parser, src)
        calls = extractor.find_new_calls(tree.root_node(), src)
        assert len(calls) >= 1
        assert calls[0]["instance_name"] == "comp"
