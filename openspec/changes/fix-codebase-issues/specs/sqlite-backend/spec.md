## ADDED Requirements

### Requirement: SQLite 二级索引

`database/sqlite_backend.py` 的 `_SCHEMA_SQL` SHALL 在创建表之后自动创建二级索引，加速常用查询。

#### Scenario: 信号名索引

- **WHEN** 数据库初始化完成
- **THEN** `signal_index` 表上存在 `idx_signal_name ON signal_index(signal_name)` 索引，加速 `search_signals` 的 LIKE 前缀匹配

#### Scenario: 文件路径索引

- **WHEN** 数据库初始化完成
- **THEN** `modules` 表上存在 `idx_modules_file_path ON modules(file_path)` 索引，加速 `remove_file()` 的按文件删除

#### Scenario: 对已有数据库添加索引

- **WHEN** 数据库文件已存在但无索引
- **THEN** `CREATE INDEX IF NOT EXISTS` 自动创建索引，不破坏已有数据

### Requirement: 批量模块加载

`database/sqlite_backend.py` 的 `SQLiteBackend` SHALL 提供 `load_all_modules()` 方法，使用单次 `SELECT * FROM modules` 加载所有模块。

#### Scenario: 批量加载

- **WHEN** 调用 `load_all_modules()`
- **THEN** 执行单次 SQL 查询，返回所有模块的 `dict` 列表，不产生 N+1 查询

#### Scenario: 空数据库

- **WHEN** 数据库中无模块
- **THEN** 返回空列表，不抛出异常

### Requirement: 反向例化索引

`database/index_store.py` SHALL 提供 `find_instantiators(module_name: str) -> list[str]` 方法，返回所有例化了指定模块的父模块名列表。

#### Scenario: 查找例化者

- **WHEN** 调用 `find_instantiators("cpu")`
- **THEN** 遍历所有已加载模块，返回 `instances` 中 `module_type == "cpu"` 的模块名列表

#### Scenario: 无例化者

- **WHEN** 调用 `find_instantiators("unused_module")`
- **THEN** 返回空列表

## MODIFIED Requirements

### Requirement: 模块写入 SQLite

`database/index_store.py` 的 `add_module()` SHALL 将模块数据写入 SQLite 数据库。

#### Scenario: 新增模块

- **WHEN** 调用 `add_module(module)` 且模块名不存在
- **THEN** 在 `modules` 表插入一行，嵌套数据（ports、signals 等）序列化为 JSON 存储

#### Scenario: 更新已有模块

- **WHEN** 调用 `add_module(module)` 且模块名已存在
- **THEN** 在 SQLite 事务中更新 `modules` 表对应行，同时更新 `files` 和 `signal_index` 表；事务失败时所有变更回滚

#### Scenario: 写入中途失败回滚

- **WHEN** `add_module(module)` 在更新 `signal_index` 时发生数据库错误
- **THEN** `modules` 和 `files` 表的变更被回滚，数据库保持调用前的一致状态

### Requirement: 搜索操作走 SQLite

`database/index_store.py` 的 `search_modules()` 和 `search_signals()` SHALL 支持从 SQLite 查询。

#### Scenario: 模糊搜索模块

- **WHEN** 调用 `search_modules("cpu")`
- **THEN** 使用 SQL `LIKE '%cpu%'` 查询 `modules` 表

#### Scenario: 按信号名搜索

- **WHEN** 调用 `search_signals("clk")`
- **THEN** 使用 `idx_signal_name` 索引加速查询 `signal_index` 表获取匹配的模块名，再加载模块数据
