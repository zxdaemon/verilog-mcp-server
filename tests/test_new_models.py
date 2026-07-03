"""测试新数据模型的序列化往返一致性"""

from verilog_mcp_server.database.models import (
    PackageDef,
    PackageImportDef,
    SvaDef,
    FunctionDef,
    PortDef,
    TypeDef,
    ParamDef,
    InstanceDef,
)


class TestPackageDef:
    def test_roundtrip(self):
        pkg = PackageDef(
            name="my_pkg",
            file_path="my_pkg.sv",
        )
        d = pkg.to_dict()
        p2 = PackageDef.from_dict(d)
        assert p2.name == "my_pkg"
        assert p2.file_path == "my_pkg.sv"
        assert p2.typedefs == []
        assert p2.parameters == []

    def test_with_typedefs(self):
        td = TypeDef(name="state_t", kind="enum", members=["IDLE", "ACTIVE"])
        pkg = PackageDef(name="types_pkg", typedefs=[td])
        p2 = PackageDef.from_dict(pkg.to_dict())
        assert len(p2.typedefs) == 1
        assert p2.typedefs[0].name == "state_t"
        assert p2.typedefs[0].kind == "enum"
        assert isinstance(p2.typedefs[0], TypeDef)

    def test_with_parameters(self):
        p = ParamDef(name="WIDTH", default_value="32", type="parameter")
        pkg = PackageDef(name="param_pkg", parameters=[p])
        p2 = PackageDef.from_dict(pkg.to_dict())
        assert len(p2.parameters) == 1
        assert p2.parameters[0].name == "WIDTH"
        assert isinstance(p2.parameters[0], ParamDef)


class TestPackageImportDef:
    def test_wildcard_import(self):
        imp = PackageImportDef(package="my_pkg", symbol="*", wildcard=True)
        d = imp.to_dict()
        i2 = PackageImportDef.from_dict(d)
        assert i2.package == "my_pkg"
        assert i2.symbol == "*"
        assert i2.wildcard is True

    def test_named_import(self):
        imp = PackageImportDef(package="my_pkg", symbol="my_func", wildcard=False)
        i2 = PackageImportDef.from_dict(imp.to_dict())
        assert i2.package == "my_pkg"
        assert i2.symbol == "my_func"
        assert i2.wildcard is False


class TestSvaDef:
    def test_concurrent_assert(self):
        sva = SvaDef(
            type="concurrent",
            keyword="assert",
            property="a |=> b",
            clock="@(posedge clk)",
            action="$error(\"assertion failed\");",
        )
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.type == "concurrent"
        assert s2.keyword == "assert"
        assert s2.property == "a |=> b"
        assert s2.clock == "@(posedge clk)"

    def test_immediate_assert(self):
        sva = SvaDef(
            type="immediate",
            keyword="assert",
            expression="a == b",
        )
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.type == "immediate"
        assert s2.expression == "a == b"
        assert s2.property == ""

    def test_property_decl(self):
        sva = SvaDef(
            type="property",
            keyword="property",
            name="my_prop",
            body="@(posedge clk) a |=> b",
        )
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.type == "property"
        assert s2.name == "my_prop"
        assert s2.body == "@(posedge clk) a |=> b"

    def test_sequence_decl(self):
        sva = SvaDef(
            type="sequence",
            keyword="sequence",
            name="my_seq",
            body="a ##1 b ##1 c",
        )
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.type == "sequence"
        assert s2.name == "my_seq"
        assert s2.body == "a ##1 b ##1 c"

    def test_assume(self):
        sva = SvaDef(type="concurrent", keyword="assume", property="a |-> b")
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.keyword == "assume"

    def test_cover(self):
        sva = SvaDef(type="concurrent", keyword="cover", property="a ##1 b")
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.keyword == "cover"

    def test_defaults(self):
        sva = SvaDef(type="concurrent", keyword="assert")
        s2 = SvaDef.from_dict(sva.to_dict())
        assert s2.name == ""
        assert s2.expression == ""
        assert s2.property == ""
        assert s2.clock == ""
        assert s2.action == ""
        assert s2.body == ""


class TestFunctionDef:
    def test_function_roundtrip(self):
        func = FunctionDef(
            name="calc",
            kind="function",
            return_type="logic [7:0]",
            file_path="test.sv",
            line=10,
        )
        f2 = FunctionDef.from_dict(func.to_dict())
        assert f2.name == "calc"
        assert f2.kind == "function"
        assert f2.return_type == "logic [7:0]"
        assert f2.file_path == "test.sv"
        assert f2.line == 10

    def test_function_with_ports(self):
        func = FunctionDef(
            name="adder",
            kind="function",
            return_type="int",
            ports=[
                PortDef(name="a", direction="input", var_type="int"),
                PortDef(name="b", direction="input", var_type="int"),
            ],
        )
        f2 = FunctionDef.from_dict(func.to_dict())
        assert len(f2.ports) == 2
        assert f2.ports[0].name == "a"
        assert f2.ports[1].name == "b"
        assert isinstance(f2.ports[0], PortDef)

    def test_task_roundtrip(self):
        task = FunctionDef(
            name="drive_bus",
            kind="task",
            ports=[
                PortDef(name="addr", direction="input", var_type="logic", width_range="[7:0]"),
            ],
            body="task drive_bus(input logic [7:0] addr); ... endtask",
            file_path="test.sv",
            line=20,
        )
        t2 = FunctionDef.from_dict(task.to_dict())
        assert t2.kind == "task"
        assert len(t2.ports) == 1
        assert t2.ports[0].name == "addr"
        assert t2.ports[0].width_range == "[7:0]"

    def test_defaults(self):
        func = FunctionDef(name="do_nothing")
        f2 = FunctionDef.from_dict(func.to_dict())
        assert f2.kind == "function"
        assert f2.return_type == ""
        assert f2.ports == []
        assert f2.body == ""
        assert f2.file_path == ""
        assert f2.line == 0


class TestInstanceDefPrimitive:
    def test_is_primitive_flag(self):
        inst = InstanceDef(
            module_type="and",
            instance_name="u_and",
            is_primitive=True,
        )
        d = inst.to_dict()
        i2 = InstanceDef.from_dict(d)
        assert i2.is_primitive is True

    def test_default_is_primitive(self):
        inst = InstanceDef(module_type="counter", instance_name="u_cnt")
        d = inst.to_dict()
        i2 = InstanceDef.from_dict(d)
        assert i2.is_primitive is False
