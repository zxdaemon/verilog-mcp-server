## ADDED Requirements

### Requirement: SQLite 数据库初始化

`database/index_store.py` SHALL 在 `IndexStore(db_path)` 中创建或打开 SQLite 数据库，并自动创建所需的表结构。

#### Scenario: 首次创建数据库

- **WHEN** `IndexStore("/tmp/cache.db")` 且文件不存在
- **THEN** 创建数据库文件，建立 `modules`、`files`、`signal_index`、`types` 四张表

#### Scenario: 打开已有数据库

- **WHEN** `IndexStore("/tmp/cache.db")` 且文件已存在
- **THEN** 直接打开数据库，不重建表结构

### Requirement: 模块写入 SQLite

`database/index_store.py` 的 `add_module()` SHALL 将模块数据写入 SQLite 数据库。

#### Scenario: 新增模块

- **WHEN** 调用 `add_module(module)` 且模块名不存在
- **THEN** 在 `modules` 表插入一行，嵌套数据（ports、signals 等）序列化为 JSON 存储

#### Scenario: 更新已有模块

- **WHEN** 调用 `add_module(module)` 且模块名已存在
- **THEN** 更新 `modules` 表对应行，同时更新 `files` 和 `signal_index` 表

### Requirement: 模块从 SQLite 读取

`database/index_store.py` 的 `get_module()` SHALL 从 SQLite 读取模块数据并反序列化。

#### Scenario: 查询存在的模块

- **WHEN** 调用 `get_module("top")` 且模块存在于数据库
- **THEN** 返回 `ModuleDef` 对象，嵌套数据从 JSON 列反序列化

#### Scenario: 查询不存在的模块

- **WHEN** 调用 `get_module("nonexistent")`
- **THEN** 返回 `None`

### Requirement: 搜索操作走 SQLite

`database/index_store.py` 的 `search_modules()` 和 `search_signals()` SHALL 支持从 SQLite 查询。

#### Scenario: 模糊搜索模块

- **WHEN** 调用 `search_modules("cpu")`
- **THEN** 使用 SQL `LIKE '%cpu%'` 查询 `modules` 表

#### Scenario: 按信号名搜索

- **WHEN** 调用 `search_signals("clk")`
- **THEN** 查询 `signal_index` 表获取匹配的模块名，再加载模块数据

### Requirement: 内存缓存层

`database/index_store.py` SHALL 在 SQLite 之上维护内存缓存，加速热路径查询。

#### Scenario: 缓存命中

- **WHEN** 连续两次调用 `get_module("top")`
- **THEN** 第二次直接从内存缓存返回，不访问 SQLite

#### Scenario: 缓存失效

- **WHEN** 调用 `add_module(module)` 更新模块
- **THEN** 同时更新内存缓存和 SQLite，保持一致

### Requirement: JSON 兼容导入

`database/index_store.py` SHALL 支持从旧版 JSON 缓存导入数据。

#### Scenario: 检测并迁移旧缓存

- **WHEN** 启动时 `.db` 文件不存在但 `.json` 文件存在
- **THEN** 读取 JSON 数据，写入 SQLite，完成一次性迁移
