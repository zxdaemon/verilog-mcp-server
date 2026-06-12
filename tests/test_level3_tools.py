"""测试 Level 3 分析工具"""

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import ModuleDef, PortDef, SignalDef, AlwaysBlockInfo, InstanceDef


def make_fsm_store() -> IndexStore:
    """创建带 FSM 模块的测试 IndexStore"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="traffic_light", file_path="tl.v", line_start=1, line_end=50,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="rst_n", direction="input"),
            PortDef(name="light", direction="output", var_type="reg"),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk or negedge rst_n",
                block_type="sequential",
                statements=[
                    'if (!rst_n) state <= RED;',
                    'else state <= next_state;',
                ],
            ),
            AlwaysBlockInfo(
                sensitivity_list="*",
                block_type="combinational",
                statements=[
                    'case (state)',
                    "  RED: next_state = car_sensor ? GREEN : RED;",
                    "  GREEN: next_state = YELLOW;",
                    "  YELLOW: next_state = RED;",
                    "  default: next_state = RED;",
                    'endcase',
                ],
            ),
        ],
    ))
    return store


def make_clock_tree_store() -> IndexStore:
    """创建多层多时钟域的测试 IndexStore"""
    store = IndexStore()

    # 顶层 soc — sys_clk + axi_clk 两个时钟域
    store.add_module(ModuleDef(
        name="soc", file_path="soc.v", line_start=1, line_end=100,
        ports=[PortDef(name="sys_clk", direction="input"),
               PortDef(name="axi_clk", direction="input"),
               PortDef(name="rst_n", direction="input")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge sys_clk or negedge rst_n",
            block_type="sequential", statements=["data <= next_data;"],
        ), AlwaysBlockInfo(
            sensitivity_list="posedge axi_clk",
            block_type="sequential", statements=["axi_reg <= axi_next;"],
        )],
        instances=[
            InstanceDef(module_type="cpu", instance_name="u_cpu",
                        port_connections={"clk": "sys_clk", "rst_n": "rst_n"},
                        file_path="soc.v", line=20),
            InstanceDef(module_type="uart", instance_name="u_uart",
                        port_connections={"clk": "sys_clk", "rst_n": "rst_n"},
                        file_path="soc.v", line=25),
            InstanceDef(module_type="axi_bridge", instance_name="u_axi",
                        port_connections={"clk": "axi_clk", "rst_n": "rst_n"},
                        file_path="soc.v", line=30),
        ],
    ))

    # cpu 子模块 — 本地时钟名 clk，映射到顶层 sys_clk
    store.add_module(ModuleDef(
        name="cpu", file_path="cpu.v", line_start=1, line_end=80,
        ports=[PortDef(name="clk", direction="input"),
               PortDef(name="rst_n", direction="input")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk or negedge rst_n",
            block_type="sequential", statements=["pc <= next_pc;"],
        )],
        instances=[
            InstanceDef(module_type="alu", instance_name="u_alu",
                        port_connections={"clk": "clk", "rst_n": "rst_n"},
                        file_path="cpu.v", line=30),
        ],
    ))

    # alu — 本地时钟名 clk，应通过 cpu 映射到顶层 sys_clk
    store.add_module(ModuleDef(
        name="alu", file_path="alu.v", line_start=1, line_end=30,
        ports=[PortDef(name="clk", direction="input"),
               PortDef(name="rst_n", direction="input")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk or negedge rst_n",
            block_type="sequential", statements=["result <= a + b;"],
        )],
    ))

    # uart — 使用 sys_clk
    store.add_module(ModuleDef(
        name="uart", file_path="uart.v", line_start=1, line_end=40,
        ports=[PortDef(name="clk", direction="input"),
               PortDef(name="rst_n", direction="input")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk or negedge rst_n",
            block_type="sequential", statements=["tx <= next_tx;"],
        )],
    ))

    # axi_bridge — 使用 axi_clk
    store.add_module(ModuleDef(
        name="axi_bridge", file_path="axi.v", line_start=1, line_end=40,
        ports=[PortDef(name="clk", direction="input"),
               PortDef(name="rst_n", direction="input")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk",
            block_type="sequential", statements=["araddr <= next_araddr;"],
        )],
    ))

    # 门控时钟单元
    store.add_module(ModuleDef(
        name="gated_clk_cell", file_path="gate.v", line_start=1, line_end=20,
        ports=[PortDef(name="clk_in", direction="input"),
               PortDef(name="en", direction="input"),
               PortDef(name="clk_out", direction="output")],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk_in",
            block_type="sequential",
            statements=["clk_out <= clk_in & en;"],
        )],
    ))

    return store


class TestClockTree:
    def test_build_tree_structure(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        result = builder.build("soc")

        assert len(result.clock_domains) >= 2
        clock_names = {g.root_clock_name for g in result.clock_domains}
        assert "sys_clk" in clock_names
        assert "axi_clk" in clock_names

    def test_clock_name_tracing(self):
        """clock 信号名应通过 port_connections 映射到父模块"""
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        result = builder.build("soc")

        sys_domain = next(g for g in result.clock_domains if g.root_clock_name == "sys_clk")
        paths = {m.instance_path for m in sys_domain.modules}
        # alu 的本地时钟 clk 应映射到 sys_clk，归入同一时钟域
        assert "soc.u_cpu.u_alu" in paths
        assert "soc.u_cpu" in paths
        assert "soc.u_uart" in paths

    def test_axi_domain_separate(self):
        """axi_bridge 应在独立的 axi_clk 域"""
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        result = builder.build("soc")

        axi_domain = next(g for g in result.clock_domains if g.root_clock_name == "axi_clk")
        assert len(axi_domain.modules) >= 2  # soc + axi_bridge

    def test_text_output_format(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        result = builder.build("soc")
        text = builder.format_text_tree(result)

        assert "⏰" in text
        assert "sys_clk" in text
        assert "axi_clk" in text
        assert "u_cpu" in text
        assert "u_alu" in text
        assert "时钟域" in text

    def test_mermaid_output_format(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        from verilog_mcp_server.analysis.visualizer import clock_tree_to_graph, graph_to_mermaid
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        result = builder.build("soc")
        graph = clock_tree_to_graph(result)
        mm = graph_to_mermaid(graph)

        assert "flowchart TD" in mm
        assert "subgraph" in mm
        assert "sys_clk" in mm

    def test_gated_clock_detection(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        assert builder._is_gated_clock_cell("gated_clk_cell") is True
        assert builder._is_gated_clock_cell("clk_gate") is True
        assert builder._is_gated_clock_cell("cpu") is False

    def test_top_module_not_found(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        from verilog_mcp_server.database.errors import ModuleNotFoundError
        store = make_clock_tree_store()
        builder = ClockTreeBuilder(store)
        try:
            builder.build("nonexistent")
            assert False, "should have raised"
        except ModuleNotFoundError:
            pass

    def test_unclocked_modules(self):
        from verilog_mcp_server.analysis.clock_tree import ClockTreeBuilder
        store = make_clock_tree_store()
        # 添加纯组合模块
        store.add_module(ModuleDef(
            name="combo", file_path="combo.v", line_start=1, line_end=10,
            ports=[PortDef(name="a", direction="input"),
                   PortDef(name="b", direction="output")],
        ))
        # 在 soc 中添加该模块的例化
        soc = store.get_module("soc")
        soc.instances.append(InstanceDef(
            module_type="combo", instance_name="u_combo",
            port_connections={"a": "x", "b": "y"}, file_path="soc.v", line=40,
        ))

        builder = ClockTreeBuilder(store)
        result = builder.build("soc")
        assert len(result.unclocked_modules) >= 1


class TestAlwaysClassification:
    def test_classify(self):
        from verilog_mcp_server.analysis.always_classify import AlwaysClassifier
        store = make_fsm_store()
        classifier = AlwaysClassifier(store)
        result = classifier.classify("traffic_light")
        assert len(result.sequential_blocks) >= 1
        # The FSM block is sequential with a clock
        for b in result.sequential_blocks:
            assert "posedge" in b.sensitivity or "negedge" in b.sensitivity


def make_port_dataflow_store() -> IndexStore:
    """创建用于测试 rtl_port_dataflow 的 IndexStore"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="dut", file_path="dut.v", line_start=1, line_end=30,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="data_out", direction="output", var_type="reg"),
        ],
        signals=[
            SignalDef(name="data_out", var_type="reg"),
            SignalDef(name="data_out_next", var_type="reg"),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk",
                block_type="sequential",
                statements=["data_out <= data_out_next;"],
            ),
        ],
    ))
    store.add_module(ModuleDef(
        name="no_port", file_path="no_port.v", line_start=1, line_end=10,
        ports=[PortDef(name="clk", direction="input")],
    ))
    return store


class TestPortDataflow:
    def test_port_dataflow_normal_path(self):
        """rtl_port_dataflow 正常路径不崩溃"""
        from mcp.server.fastmcp import FastMCP
        from verilog_mcp_server.tools.level3_analysis import register_tools

        store = make_port_dataflow_store()
        mcp = FastMCP("test")
        register_tools(mcp, store)

        tool_fn = None
        for tool_info in mcp._tool_manager._tools.values():
            if tool_info.name == "rtl_port_dataflow":
                tool_fn = tool_info.fn
                break

        assert tool_fn is not None
        result = tool_fn(module_name="dut", port_name="data_out")
        assert "data_out" in result
        assert "端口数据流" in result

    def test_port_dataflow_no_port(self):
        """rtl_port_dataflow 端口不存在时不崩溃"""
        from mcp.server.fastmcp import FastMCP
        from verilog_mcp_server.tools.level3_analysis import register_tools

        store = make_port_dataflow_store()
        mcp = FastMCP("test")
        register_tools(mcp, store)

        tool_fn = None
        for tool_info in mcp._tool_manager._tools.values():
            if tool_info.name == "rtl_port_dataflow":
                tool_fn = tool_info.fn
                break

        result = tool_fn(module_name="no_port", port_name="nonexistent")
        # 不应崩溃，应返回提示信息
        assert "端口数据流" in result or "ℹ️" in result or "未追踪" in result
