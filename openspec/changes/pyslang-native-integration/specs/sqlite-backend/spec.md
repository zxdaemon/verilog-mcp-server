## ADDED Requirements

### Requirement: SQLite 数据库初始化扩展 elaboration 表
`database/sqlite_backend.py` 的 `_SCHEMA_SQL` SHALL 在初始化时创建 `elaborated_instances`、`resolved_signals`、`macro_expansions`、`elaboration_reports` 四张表。
- `elaborated_instances`：存储 `ElaboratedInstanceDef` 的 JSON 序列化数据
- `resolved_signals`：存储 `ResolvedSignalDef` 的 JSON 序列化数据
- `macro_expansions`：存储 `MacroExpansionInfo` 的 JSON 序列化数据
- `elaboration_reports`：存储 `ElaborationReport` 的 JSON 序列化数据

#### Scenario: 首次创建数据库含 elaboration 表
- **WHEN** `IndexStore("/tmp/cache.db")` 且文件不存在
- **THEN** 创建全部表，含新增的 elaboration 相关表

#### Scenario: 兼容已有数据库升级
- **WHEN** `IndexStore` 打开已有数据库（不含 elaboration 表）
- **THEN** 自动执行 `CREATE TABLE IF NOT EXISTS` 添加新表

### Requirement: ElaboratedInstanceDef 写入和读取 SQLite
`SQLiteBackend` SHALL 提供 `save_elaborated_instance(instance: ElaboratedInstanceDef)`、`get_elaborated_instances_by_module(module_name: str)`、`get_all_elaborated_instances()` 方法。

#### Scenario: 按模块查询 elaborated 实例
- **WHEN** 调用 `get_elaborated_instances_by_module("top")`
- **THEN** 返回 `top` 模块下所有 generate 展开后的实例列表

### Requirement: ResolvedSignalDef 写入和读取 SQLite
`SQLiteBackend` SHALL 提供 `save_resolved_signal(signal: ResolvedSignalDef)`、`get_resolved_signals_by_module(module_name: str)` 方法。

#### Scenario: 按模块查询求值后信号
- **WHEN** 调用 `get_resolved_signals_by_module("fifo")`
- **THEN** 返回 `fifo` 模块中所有信号的 `resolved_width`

### Requirement: ElaborationReport 写入和读取 SQLite
`SQLiteBackend` SHALL 提供 `save_elaboration_report(report: ElaborationReport)`、`get_latest_elaboration_report()` 方法。每次 pyslang elaboration 完成后保存报告。

#### Scenario: 存储 elaboration 报告
- **WHEN** pyslang elaboration 完成后
- **THEN** 调用 `save_elaboration_report()` 存储报告到 `elaboration_reports` 表

### Requirement: IndexStore 暴露 elaboration 查询接口
`IndexStore` SHALL 在现有查询接口基础上，新增 `get_elaborated_instances()`、`get_resolved_signals()`、`get_macro_expansions()`、`get_elaboration_report()` 方法，复用现有内存缓存机制。

#### Scenario: IndexStore 查询 elaborated 实例
- **WHEN** 调用 `index_store.get_elaborated_instances(module_name="top")`
- **THEN** 优先从内存缓存返回，未命中时从 SQLite 加载并缓存
