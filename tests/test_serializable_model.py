"""测试 SerializableModel 序列化往返一致性"""

from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, ParamDef, SignalDef, DriverInfo, LoadInfo,
    InstanceDef, AlwaysBlockInfo, AssignmentInfo,
)


def test_port_def_roundtrip():
    port = PortDef(name="clk", direction="input")
    d = port.to_dict()
    p2 = PortDef.from_dict(d)
    assert p2.name == "clk"
    assert p2.direction == "input"
    assert p2.width_range is None
    assert p2.var_type == "wire"


def test_port_def_with_width():
    port = PortDef(name="data", direction="output", width_range="[7:0]",
                   var_type="reg", signed=True)
    p2 = PortDef.from_dict(port.to_dict())
    assert p2.width_range == "[7:0]"
    assert p2.var_type == "reg"
    assert p2.signed is True


def test_module_def_nested_roundtrip():
    mod = ModuleDef(
        name="top",
        file_path="top.v",
        line_start=10,
        line_end=50,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="rst_n", direction="input"),
        ],
        parameters=[ParamDef(name="WIDTH", default_value="32")],
        signals=[
            SignalDef(name="internal_wire", var_type="wire", width_range="[31:0]",
                      drivers=[DriverInfo(type="assign", source="assign internal_wire = a + b")],
                      loads=[LoadInfo(type="always_block", target="always @(posedge clk)")]),
        ],
        instances=[
            InstanceDef(module_type="adder", instance_name="u_adder",
                        port_connections={"a": "data_a", "b": "data_b", "sum": "sum_result"},
                        file_path="top.v", line=30),
        ],
        always_blocks=[AlwaysBlockInfo(
            sensitivity_list="posedge clk or negedge rst_n",
            block_type="sequential",
            statements=["if (!rst_n) count <= 0; else count <= count + 1;"],
        )],
        assignments=[AssignmentInfo(lhs="result", rhs="pipeline_reg", file_path="top.v", line=45)],
    )

    mod2 = ModuleDef.from_dict(mod.to_dict())

    assert mod2.name == "top"
    assert mod2.file_path == "top.v"
    assert len(mod2.ports) == 2
    assert isinstance(mod2.ports[0], PortDef)
    assert mod2.ports[0].name == "clk"
    assert len(mod2.parameters) == 1
    assert isinstance(mod2.parameters[0], ParamDef)
    assert mod2.parameters[0].name == "WIDTH"
    assert len(mod2.signals) == 1
    assert isinstance(mod2.signals[0], SignalDef)
    assert len(mod2.signals[0].drivers) == 1
    assert isinstance(mod2.signals[0].drivers[0], DriverInfo)
    assert len(mod2.signals[0].loads) == 1
    assert isinstance(mod2.signals[0].loads[0], LoadInfo)
    assert len(mod2.instances) == 1
    assert isinstance(mod2.instances[0], InstanceDef)
    assert mod2.instances[0].port_connections == {"a": "data_a", "b": "data_b", "sum": "sum_result"}
    assert len(mod2.always_blocks) == 1
    assert isinstance(mod2.always_blocks[0], AlwaysBlockInfo)
    assert len(mod2.assignments) == 1
    assert isinstance(mod2.assignments[0], AssignmentInfo)


def test_instance_def_roundtrip():
    inst = InstanceDef(module_type="counter", instance_name="u_counter",
                       port_connections={"clk": "clk", "count": "counter_val"},
                       param_overrides={"WIDTH": "16"},
                       file_path="top.v", line=35)
    i2 = InstanceDef.from_dict(inst.to_dict())
    assert i2.module_type == "counter"
    assert i2.instance_name == "u_counter"
    assert i2.port_connections == {"clk": "clk", "count": "counter_val"}
    assert i2.param_overrides == {"WIDTH": "16"}


def test_always_block_info_roundtrip():
    ab = AlwaysBlockInfo(sensitivity_list="posedge clk",
                         block_type="sequential",
                         statements=["data <= next_data;"])
    ab2 = AlwaysBlockInfo.from_dict(ab.to_dict())
    assert ab2.sensitivity_list == "posedge clk"
    assert ab2.block_type == "sequential"
    assert ab2.statements == ["data <= next_data;"]


def test_assignment_info_roundtrip():
    assign = AssignmentInfo(lhs="result", rhs="a + b", file_path="top.v", line=20)
    a2 = AssignmentInfo.from_dict(assign.to_dict())
    assert a2.lhs == "result"
    assert a2.rhs == "a + b"
