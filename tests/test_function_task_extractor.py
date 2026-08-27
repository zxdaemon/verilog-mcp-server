"""测试 FunctionTaskExtractor function/task 提取"""

import pytest
from verilog_mcp_server.indexer.verilog_parser import parse_source
from verilog_mcp_server.indexer.function_task_extractor import FunctionTaskExtractor


def _find_module_node(tree, src):
    root = tree.root_node
    for i in range(root.child_count):
        c = root.child(i)
        if c.type == "module_declaration":
            return c
    return root


FUNCTION_SRC = """
module func_test(input clk, input [7:0] data_in, output [7:0] result);
    function automatic logic [7:0] adder(
        input logic [7:0] a,
        input logic [7:0] b
    );
        adder = a + b;
    endfunction
endmodule
"""

TASK_SRC = """
module task_test(input clk);
    task drive_bus(
        input logic [7:0] addr,
        output logic enable
    );
        enable = 1'b1;
    endtask
endmodule
"""

SIMPLE_FUNCTION_SRC = """
module simple_func;
    function int double(input int x);
        double = x * 2;
    endfunction
endmodule
"""


class TestFunctionExtraction:
    def test_extract_function_name(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert len(funcs_list) >= 1
        assert funcs_list[0].name == "adder"

    def test_function_return_type(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert "logic" in funcs_list[0].return_type.lower()

    def test_function_ports(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert len(funcs_list[0].ports) >= 1
        port_names = [p.name for p in funcs_list[0].ports]
        assert "a" in port_names
        assert "b" in port_names

    def test_function_port_direction(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert funcs_list[0].ports[0].direction == "input"

    def test_function_file_path_and_line(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert funcs_list[0].file_path == "test.sv"
        assert funcs_list[0].line > 0

    def test_simple_function(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(SIMPLE_FUNCTION_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        funcs_list = [f for f in funcs if f.kind == "function"]
        assert len(funcs_list) == 1
        assert funcs_list[0].name == "double"
        assert funcs_list[0].return_type == "int"


class TestTaskExtraction:
    def test_extract_task_name(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(TASK_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        tasks = [f for f in funcs if f.kind == "task"]
        assert len(tasks) >= 1
        assert tasks[0].name == "drive_bus"

    def test_task_ports(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(TASK_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        tasks = [f for f in funcs if f.kind == "task"]
        assert len(tasks[0].ports) >= 1
        port_dirs = [(p.name, p.direction) for p in tasks[0].ports]
        names = [p[0] for p in port_dirs]
        assert "addr" in names

    def test_task_kind_distinct_from_function(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(TASK_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        tasks = [f for f in funcs if f.kind == "task"]
        functions = [f for f in funcs if f.kind == "function"]
        assert len(tasks) >= 1
        assert len(functions) == 0  # no function in this source


class TestMixedFunctionTask:
    MIXED_SRC = """
module mixed_test(input clk);
    function int get_value(input int idx);
        get_value = idx + 1;
    endfunction
    task print_val(input int v);
        $display("val=%d", v);
    endtask
endmodule
"""

    def test_extracts_both(self):
        extractor = FunctionTaskExtractor()
        tree, src = parse_source(self.MIXED_SRC)
        mod = _find_module_node(tree, src)
        funcs = extractor.extract_from_module(mod, src, "test.sv")
        assert len([f for f in funcs if f.kind == "function"]) == 1
        assert len([f for f in funcs if f.kind == "task"]) == 1
        assert funcs[0].name == "get_value"
        assert funcs[1].name == "print_val"
