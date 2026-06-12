## ADDED Requirements

### Requirement: ClassExtractor 从 source_file 提取 class 定义
`ClassExtractor` SHALL 从 `source_file` 级 AST 中提取所有 `class_declaration` 节点，返回 `ClassDef` 列表。每个 `ClassDef` 包含类名、继承父类名、参数化类型列表、成员变量列表、方法名列表、是否为 UVM 组件标志。

#### Scenario: 简单 class 提取
- **WHEN** 源码包含 `class my_driver extends uvm_driver #(my_item); ... endclass`
- **THEN** 提取出类名 `my_driver`，父类 `uvm_driver`，参数化类型 `my_item`

#### Scenario: 无继承的 class
- **WHEN** 源码包含 `class my_helper; ... endclass`
- **THEN** 提取出类名 `my_helper`，父类为空字符串

#### Scenario: 多层参数化 class
- **WHEN** 源码包含 `class my_env #(int N=4) extends uvm_env; ... endclass`
- **THEN** 提取出类名 `my_env`，参数化类型列表包含 `int N=4`

### Requirement: ClassDef 数据模型完整序列化
`ClassDef` dataclass SHALL 支持 `to_dict()` / `from_dict()`（JSON 序列化）和 `to_row()` / `from_row()`（SQLite 行存储），与现有 `ModuleDef` 的序列化策略一致。

#### Scenario: ClassDef 往返序列化
- **WHEN** 创建 `ClassDef(name="my_agent", extends="uvm_agent", ...)` 并调用 `to_dict()` 后 `from_dict()`
- **THEN** 还原后的对象与原对象字段值一致

#### Scenario: ClassDef SQLite 行存储
- **WHEN** 创建 `ClassDef` 并调用 `to_row()`，再将行数据传入 `from_row()`
- **THEN** 还原后的对象与原对象字段值一致

### Requirement: 成员变量提取
`ClassExtractor` SHALL 提取 class 体内的 `data_declaration` 节点作为成员变量，记录变量名、类型、位宽、访问修饰符（`local`/`protected`/`rand`）。

#### Scenario: 提取 class 成员变量
- **WHEN** class 体内声明 `rand int delay; logic [7:0] data;`
- **THEN** 提取成员 `delay`（类型 `int`，修饰符 `rand`）和 `data`（类型 `logic`，位宽 `[7:0]`）

### Requirement: UVM 组件识别
`ClassExtractor` SHALL 识别 UVM 组件类：检查 extends 父类名是否匹配已知 UVM 基类（`uvm_component`、`uvm_env`、`uvm_agent`、`uvm_driver`、`uvm_monitor`、`uvm_sequencer`、`uvm_scoreboard`、`uvm_subscriber`、`uvm_test`）。

#### Scenario: UVM agent 类识别
- **WHEN** class 声明 `class my_agent extends uvm_agent;`
- **THEN** `is_uvm_component` 为 `True`，`uvm_base_class` 为 `"uvm_agent"`

#### Scenario: 非 UVM class 识别
- **WHEN** class 声明 `class my_helper extends base_helper;` 且 `base_helper` 不继承任何 UVM 基类
- **THEN** `is_uvm_component` 为 `False`

### Requirement: 多层继承基类推导
`ClassExtractor` SHALL 处理多层继承：若 `my_agent extends my_base_agent extends uvm_agent`，则 `my_agent` 的 `uvm_base_class` 推导为 `"uvm_agent"`。

#### Scenario: 多层封装基类
- **WHEN** 源码中 `my_base_agent extends uvm_agent` 和 `my_agent extends my_base_agent` 同时存在
- **THEN** `my_agent` 的 `uvm_base_class` 为 `"uvm_agent"`
