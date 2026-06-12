## ADDED Requirements

### Requirement: SQLite 数据库初始化扩展表
`database/sqlite_backend.py` 的 `_SCHEMA_SQL` SHALL 在初始化时创建 `classes`、`methods`、`uvm_components`、`uvm_tlm_ports`、`uvm_config_entries` 五张表。`classes` 表存储 `ClassDef` 的 JSON 序列化数据；`methods` 表存储 `MethodDef` 数据；`uvm_components` 表存储组件层次关系；`uvm_tlm_ports` 表存储 TLM 端口声明；`uvm_config_entries` 表存储 config_db set/get 记录。

#### Scenario: 首次创建数据库含 class 表
- **WHEN** `IndexStore("/tmp/cache.db")` 且文件不存在
- **THEN** 创建 `modules`、`files`、`signal_index`、`types`、`classes`、`methods`、`uvm_components`、`uvm_tlm_ports`、`uvm_config_entries` 九张表

#### Scenario: 兼容已有数据库升级
- **WHEN** `IndexStore` 打开已有数据库（不含 class 表）
- **THEN** 自动执行 `CREATE TABLE IF NOT EXISTS` 添加新表，不破坏已有数据

### Requirement: ClassDef 写入 SQLite
`SQLiteBackend` SHALL 提供 `save_class(class_def: ClassDef)` 方法，将 class 数据序列化为 JSON 写入 `classes` 表。同一文件路径的 class 更新时覆盖旧数据。

#### Scenario: 新增 class
- **WHEN** 调用 `save_class(class_def)` 且 class 名不存在
- **THEN** 在 `classes` 表插入一行，嵌套数据序列化为 JSON

#### Scenario: 更新已有 class
- **WHEN** 调用 `save_class(class_def)` 且 class 名已存在
- **THEN** 更新 `classes` 表对应行

### Requirement: ClassDef 从 SQLite 读取
`SQLiteBackend` SHALL 提供 `get_class(class_name: str)` 和 `get_classes_by_file(file_path: str)` 方法，从 `classes` 表读取并反序列化 `ClassDef`。

#### Scenario: 查询存在的 class
- **WHEN** 调用 `get_class("my_driver")` 且 class 存在于数据库
- **THEN** 返回 `ClassDef` 对象

#### Scenario: 按文件查询 class
- **WHEN** 调用 `get_classes_by_file("my_agent.sv")`
- **THEN** 返回该文件中定义的所有 class 列表

### Requirement: MethodDef 写入和读取 SQLite
`SQLiteBackend` SHALL 提供 `save_method(method_def: MethodDef)`、`get_methods_by_class(class_name: str)`、`get_methods_by_package(package_name: str)` 方法，在 `methods` 表中存储和查询 method 数据。

#### Scenario: 按 class 查询方法
- **WHEN** 调用 `get_methods_by_class("my_driver")`
- **THEN** 返回 `my_driver` 类中定义的所有 function/task 列表

### Requirement: UVM 组件层次写入 SQLite
`SQLiteBackend` SHALL 提供 `save_uvm_component(component: UvmComponentDef)` 和 `get_uvm_hierarchy(test_class: str | None)` 方法，在 `uvm_components` 表中存储组件层次关系。

#### Scenario: 存储组件层次
- **WHEN** 调用 `save_uvm_component` 存储 test → env → agent → driver 的层次
- **THEN** 数据正确写入，支持通过 `parent_id` 重建树结构

### Requirement: IndexStore 暴露 class/method 查询接口
`IndexStore` SHALL 在现有 `get_module()`/`search_modules()` 等接口基础上，新增 `get_class()`/`search_classes()`/`get_methods_by_class()`/`get_uvm_hierarchy()` 等查询方法，复用现有的内存缓存机制。

#### Scenario: IndexStore 查询 class
- **WHEN** 调用 `index_store.get_class("my_driver")`
- **THEN** 优先从内存缓存返回，未命中时从 SQLite 加载并缓存
