## ADDED Requirements

### Requirement: SerializableModel 基类提供通用序列化

`database/models.py` SHALL 定义 `SerializableModel` 基类，提供 `to_dict() -> dict` 和 `from_dict(cls, d: dict) -> Self` 两个方法。所有 dataclass 模型（ModuleDef、PortDef、SignalDef、InstanceDef、DriverInfo、LoadInfo、ParamDef、AlwaysBlockInfo、AssignmentInfo）SHALL 继承 `SerializableModel`。

`to_dict()` SHALL 递归处理：
- 基础类型（str、int、bool、None）直接返回
- `SerializableModel` 子类调用其 `to_dict()`
- `list[SerializableModel]` 对每个元素调用 `to_dict()`

`from_dict()` SHALL 通过 `field(metadata={"elem_type": Type})` 标注识别列表元素类型以进行递归反序列化。

#### Scenario: 嵌套模型序列化往返

- **WHEN** 创建 `ModuleDef(name="top", ports=[PortDef(name="clk", direction="input")])` 并执行 `ModuleDef.from_dict(mod.to_dict())`
- **THEN** 反序列化后的对象与原始对象深度相等（所有字段值相同，嵌套对象类型正确）

#### Scenario: 无需标注的基础类型序列化

- **WHEN** `PortDef(name="clk", direction="input")` 执行 `port.to_dict()`
- **THEN** 返回 `{"name": "clk", "direction": "input", "width_range": None, "var_type": "wire", "signed": False, "description": ""}`

### Requirement: 现有 to_dict/from_dict 实现迁移到 SerializableModel

所有 dataclass 模型 SHALL 删除其手动编写的 `to_dict()` 和 `from_dict()` 方法，改为由 `SerializableModel` 基类自动提供。IndexStore 的 `save()`/`load()` 方法行为 SHALL 保持不变。

#### Scenario: IndexStore 保存和加载行为不变

- **WHEN** 使用 IndexStore 构建索引后执行 `save(path)` 和 `load(path)`
- **THEN** 加载后的 `module_count`、模块名列表、端口数量与保存前一致

### Requirement: dataclass 支持 SQLite 行序列化

`database/models.py` 的 `SerializableModel` 基类 SHALL 新增 `to_row()` 和 `from_row()` 方法，用于 SQLite 行存储。

#### Scenario: ModuleDef 行序列化

- **WHEN** 调用 `module.to_row()`
- **THEN** 返回 dict，其中基础字段（name、file_path、line_start、line_end）直接存储，嵌套字段（ports、signals 等）序列化为 JSON 字符串

#### Scenario: ModuleDef 行反序列化

- **WHEN** 调用 `ModuleDef.from_row(row_dict)`
- **THEN** 从行 dict 构造 `ModuleDef` 对象，嵌套字段从 JSON 字符串反序列化
