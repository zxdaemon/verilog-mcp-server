"""
Verilog/SystemVerilog 代码分析数据模型
"""

from __future__ import annotations
import json as _json
from dataclasses import dataclass, field, fields
from typing import get_origin, get_args, get_type_hints, Optional


class SerializableModel:
    """dataclass 序列化基类，自动提供 to_dict() / from_dict() / to_row() / from_row()"""

    def to_dict(self) -> dict:
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            result[f.name] = self._serialize_value(value)
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "SerializableModel":
        hints = get_type_hints(cls)
        kwargs = {}
        for f in fields(cls):
            raw = d.get(f.name)
            kwargs[f.name] = cls._deserialize_value(raw, f.name, hints)
        return cls(**kwargs)

    # ── SQLite 行序列化 ──

    def to_row(self) -> dict:
        """序列化为 SQLite 行 dict，嵌套字段转为 JSON 字符串"""
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            result[f.name] = self._serialize_value(value)
        return result

    @classmethod
    def from_row(cls, row: dict) -> "SerializableModel":
        """从 SQLite 行 dict 反序列化"""
        return cls.from_dict(row)

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, SerializableModel):
            return value.to_dict()
        if isinstance(value, list):
            return [SerializableModel._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: SerializableModel._serialize_value(v) for k, v in value.items()}
        return value

    @classmethod
    def _deserialize_value(cls, raw, field_name: str, hints: dict):
        if raw is None:
            return None
        field_type = hints.get(field_name)
        if field_type is None:
            return raw
        origin = get_origin(field_type)
        if origin is list:
            args = get_args(field_type)
            if args and issubclass(args[0], SerializableModel):
                return [args[0].from_dict(item) for item in raw]
            return raw
        if isinstance(field_type, type) and issubclass(field_type, SerializableModel):
            return field_type.from_dict(raw)
        return raw


@dataclass
class DriverInfo(SerializableModel):
    """信号驱动源信息"""
    type: str          # assign / always_block / port_connection / instance_output
    source: str        # 具体描述
    file_path: str = ""
    line: int = 0


@dataclass
class LoadInfo(SerializableModel):
    """信号负载端信息"""
    type: str          # assign / always_block / port_connection / instance_input
    target: str        # 具体描述
    file_path: str = ""
    line: int = 0


@dataclass
class PortDef(SerializableModel):
    """模块端口定义"""
    name: str
    direction: str               # input / output / inout
    width_range: Optional[str] = None   # e.g. "[7:0]" or None
    var_type: str = "wire"       # wire / reg / logic / integer
    signed: bool = False
    description: str = ""        # 可附加注释


@dataclass
class ParamDef(SerializableModel):
    """模块参数定义"""
    name: str
    default_value: Optional[str] = None
    type: str = "parameter"      # parameter / localparam


@dataclass
class InstanceDef(SerializableModel):
    """模块例化定义"""
    module_type: str             # 被例化的 module 名
    instance_name: str           # 例化标签
    port_connections: dict[str, str] = field(default_factory=dict)  # {formal_port: actual_signal}
    param_overrides: dict[str, str] = field(default_factory=dict)   # {param_name: override_value}
    file_path: str = ""
    line: int = 0


@dataclass
class SignalDef(SerializableModel):
    """信号定义"""
    name: str
    var_type: str = "wire"       # wire / reg / logic / integer / real
    width_range: Optional[str] = None
    signed: bool = False
    drivers: list[DriverInfo] = field(default_factory=list)
    loads: list[LoadInfo] = field(default_factory=list)


@dataclass
class AlwaysBlockInfo(SerializableModel):
    """Always 块信息"""
    sensitivity_list: str = ""   # e.g. "posedge clk or negedge rst_n"
    block_type: str = "sequential"  # sequential / combinational / latch
    statements: list[str] = field(default_factory=list)


@dataclass
class AssignmentInfo(SerializableModel):
    """连续赋值 assign 语句"""
    lhs: str           # 左侧目标
    rhs: str           # 右侧表达式
    file_path: str = ""
    line: int = 0


@dataclass
class TypeDef(SerializableModel):
    """类型定义 (struct / enum / typedef)"""
    name: str
    kind: str                    # struct / enum / typedef / union
    members: list[str] = field(default_factory=list)
    source_text: str = ""
    file_path: str = ""
    line: int = 0


@dataclass
class ModuleDef(SerializableModel):
    """模块完整定义"""
    name: str
    file_path: str
    line_start: int = 0
    line_end: int = 0
    ports: list[PortDef] = field(default_factory=list)
    parameters: list[ParamDef] = field(default_factory=list)
    signals: list[SignalDef] = field(default_factory=list)
    instances: list[InstanceDef] = field(default_factory=list)
    always_blocks: list[AlwaysBlockInfo] = field(default_factory=list)
    assignments: list[AssignmentInfo] = field(default_factory=list)

    # SQLite 列名到字段的映射
    _NESTED_FIELDS = ("ports", "params", "signals", "instances", "always_blocks", "assignments")
    _NESTED_TYPES = {
        "ports": PortDef, "params": ParamDef, "signals": SignalDef,
        "instances": InstanceDef, "always_blocks": AlwaysBlockInfo,
        "assignments": AssignmentInfo,
    }

    def to_row(self) -> dict:
        """序列化为 SQLite 行：基础字段直接存储，嵌套字段 JSON 字符串"""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "ports_json": _json.dumps([p.to_dict() for p in self.ports], ensure_ascii=False),
            "params_json": _json.dumps([p.to_dict() for p in self.parameters], ensure_ascii=False),
            "signals_json": _json.dumps([s.to_dict() for s in self.signals], ensure_ascii=False),
            "instances_json": _json.dumps([i.to_dict() for i in self.instances], ensure_ascii=False),
            "always_blocks_json": _json.dumps([a.to_dict() for a in self.always_blocks], ensure_ascii=False),
            "assignments_json": _json.dumps([a.to_dict() for a in self.assignments], ensure_ascii=False),
        }

    @classmethod
    def from_row(cls, row: dict) -> "ModuleDef":
        """从 SQLite 行 dict 反序列化"""
        return cls(
            name=row["name"],
            file_path=row["file_path"],
            line_start=row.get("line_start") or 0,
            line_end=row.get("line_end") or 0,
            ports=[PortDef.from_dict(d) for d in _json.loads(row.get("ports_json") or "[]")],
            parameters=[ParamDef.from_dict(d) for d in _json.loads(row.get("params_json") or "[]")],
            signals=[SignalDef.from_dict(d) for d in _json.loads(row.get("signals_json") or "[]")],
            instances=[InstanceDef.from_dict(d) for d in _json.loads(row.get("instances_json") or "[]")],
            always_blocks=[AlwaysBlockInfo.from_dict(d) for d in _json.loads(row.get("always_blocks_json") or "[]")],
            assignments=[AssignmentInfo.from_dict(d) for d in _json.loads(row.get("assignments_json") or "[]")],
        )
