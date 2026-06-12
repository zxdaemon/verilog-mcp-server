## ADDED Requirements

### Requirement: TypeDef 数据模型
`database/models.py` SHALL 定义 `TypeDef` dataclass，继承 `SerializableModel`，包含字段：`name`（类型名）、`kind`（struct/enum/typedef/union）、`members`（成员名列表）、`source_text`（原始声明文本）、`file_path`、`line`。

#### Scenario: TypeDef 序列化往返
- **WHEN** 创建 `TypeDef(name="state_t", kind="enum", members=["IDLE", "ACTIVE", "DONE"], ...)` 并调用 `to_dict()` + `from_dict()`
- **THEN** 往返后的对象与原对象相等

### Requirement: typedef enum 提取
`indexer/type_extractor.py` SHALL 从 `typedef_declaration` 和 `enum_declaration` 节点中提取 typedef enum 定义，生成 `TypeDef(kind="enum")` 记录，members 包含 enum 成员的标识符列表。

#### Scenario: typedef enum 定义
- **WHEN** 源文件包含 `typedef enum logic [1:0] {IDLE, ACTIVE, DONE} state_t;`
- **THEN** 系统提取 `TypeDef(name="state_t", kind="enum", members=["IDLE", "ACTIVE", "DONE"])`

### Requirement: typedef struct 提取
`indexer/type_extractor.py` SHALL 从 `typedef_declaration` 和 `struct_declaration` 节点中提取 typedef struct 定义，生成 `TypeDef(kind="struct")` 记录，members 包含 struct 字段名列表。

#### Scenario: typedef struct 定义
- **WHEN** 源文件包含 `typedef struct packed {logic [7:0] data; logic valid;} bus_t;`
- **THEN** 系统提取 `TypeDef(name="bus_t", kind="struct", members=["data", "valid"])`

### Requirement: IndexStore 类型索引
`database/index_store.py` SHALL 新增 `add_type(type_def)` 和 `get_type(name)` 方法，支持按类型名查询 `TypeDef` 记录。

#### Scenario: 类型查询
- **WHEN** 索引包含 `state_t` 的 TypeDef，调用 `index_store.get_type("state_t")`
- **THEN** 返回 `TypeDef(name="state_t", kind="enum", members=["IDLE", "ACTIVE", "DONE"])`
