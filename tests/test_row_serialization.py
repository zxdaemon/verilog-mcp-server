"""测试 to_row() / from_row() 往返一致性（SQLite 行序列化）"""

from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, ParamDef, SignalDef, DriverInfo, LoadInfo,
    InstanceDef, AlwaysBlockInfo, AssignmentInfo, TypeDef,
)


def _make_full_module() -> ModuleDef:
    return ModuleDef(
        name="alu_top",
        file_path="rtl/alu_top.sv",
        line_start=10,
        line_end=120,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="data_out", direction="output", width_range="[31:0]",
                    var_type="logic", signed=True, description="输出数据"),
        ],
        parameters=[
            ParamDef(name="WIDTH", default_value="32"),
            ParamDef(name="DEPTH", default_value="8", type="localparam"),
        ],
        signals=[
            SignalDef(name="internal_reg", var_type="reg", width_range="[7:0]",
                      drivers=[DriverInfo(type="always_block", source="always @(posedge clk)",
                                          file_path="rtl/alu_top.sv", line=50)],
                      loads=[LoadInfo(type="assign", target="assign out = internal_reg",
                                      file_path="rtl/alu_top.sv", line=80)]),
        ],
        instances=[
            InstanceDef(module_type="adder", instance_name="u_adder",
                        port_connections={"a": "op_a", "b": "op_b", "sum": "result"},
                        param_overrides={"WIDTH": "16"},
                        file_path="rtl/alu_top.sv", line=60),
        ],
        always_blocks=[
            AlwaysBlockInfo(sensitivity_list="posedge clk or negedge rst_n",
                            block_type="sequential",
                            statements=["if (!rst_n) data <= 0;", "else data <= next;"]),
        ],
        assignments=[
            AssignmentInfo(lhs="result", rhs="a + b", file_path="rtl/alu_top.sv", line=90),
        ],
    )


def test_module_to_row_basic_fields():
    mod = _make_full_module()
    row = mod.to_row()
    assert row["name"] == "alu_top"
    assert row["file_path"] == "rtl/alu_top.sv"
    assert row["line_start"] == 10
    assert row["line_end"] == 120


def test_module_to_row_nested_are_json_strings():
    import json
    mod = _make_full_module()
    row = mod.to_row()
    # 嵌套字段应为 JSON 字符串
    assert isinstance(row["ports_json"], str)
    assert isinstance(row["params_json"], str)
    assert isinstance(row["signals_json"], str)
    assert isinstance(row["instances_json"], str)
    assert isinstance(row["always_blocks_json"], str)
    assert isinstance(row["assignments_json"], str)
    # 反序列化验证
    ports = json.loads(row["ports_json"])
    assert len(ports) == 2
    assert ports[0]["name"] == "clk"


def test_module_from_row_roundtrip():
    mod = _make_full_module()
    row = mod.to_row()
    mod2 = ModuleDef.from_row(row)

    assert mod2.name == mod.name
    assert mod2.file_path == mod.file_path
    assert mod2.line_start == mod.line_start
    assert mod2.line_end == mod.line_end

    assert len(mod2.ports) == 2
    assert isinstance(mod2.ports[0], PortDef)
    assert mod2.ports[1].width_range == "[31:0]"
    assert mod2.ports[1].signed is True

    assert len(mod2.parameters) == 2
    assert isinstance(mod2.parameters[0], ParamDef)
    assert mod2.parameters[1].type == "localparam"

    assert len(mod2.signals) == 1
    assert isinstance(mod2.signals[0], SignalDef)
    assert len(mod2.signals[0].drivers) == 1
    assert isinstance(mod2.signals[0].drivers[0], DriverInfo)
    assert len(mod2.signals[0].loads) == 1
    assert isinstance(mod2.signals[0].loads[0], LoadInfo)

    assert len(mod2.instances) == 1
    assert isinstance(mod2.instances[0], InstanceDef)
    assert mod2.instances[0].port_connections == {"a": "op_a", "b": "op_b", "sum": "result"}
    assert mod2.instances[0].param_overrides == {"WIDTH": "16"}

    assert len(mod2.always_blocks) == 1
    assert isinstance(mod2.always_blocks[0], AlwaysBlockInfo)
    assert mod2.always_blocks[0].sensitivity_list == "posedge clk or negedge rst_n"

    assert len(mod2.assignments) == 1
    assert isinstance(mod2.assignments[0], AssignmentInfo)
    assert mod2.assignments[0].lhs == "result"


def test_module_from_row_empty_nested():
    """嵌套字段为空列表时的反序列化"""
    mod = ModuleDef(name="empty", file_path="empty.v")
    row = mod.to_row()
    mod2 = ModuleDef.from_row(row)
    assert mod2.ports == []
    assert mod2.parameters == []
    assert mod2.signals == []
    assert mod2.instances == []
    assert mod2.always_blocks == []
    assert mod2.assignments == []


def test_module_from_row_missing_json_fields():
    """JSON 字段缺失时应安全处理"""
    row = {
        "name": "test", "file_path": "test.v",
        "line_start": 0, "line_end": 0,
    }
    mod = ModuleDef.from_row(row)
    assert mod.name == "test"
    assert mod.ports == []


def test_typedef_roundtrip():
    td = TypeDef(name="state_t", kind="enum",
                 members=["IDLE", "RUN", "DONE"],
                 source_text="typedef enum {IDLE, RUN, DONE} state_t;",
                 file_path="fsm.sv", line=5)
    d = td.to_dict()
    td2 = TypeDef.from_dict(d)
    assert td2.name == "state_t"
    assert td2.kind == "enum"
    assert td2.members == ["IDLE", "RUN", "DONE"]
