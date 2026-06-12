## ADDED Requirements

### Requirement: 文件变更检测

`indexer/builder.py` SHALL 通过 mtime + SHA256 检测文件变更。

#### Scenario: 文件内容修改

- **WHEN** 文件 `top.v` 的 mtime 比缓存记录新
- **THEN** 将该文件标记为需要重新解析

#### Scenario: 文件未变更

- **WHEN** 文件 `sub.v` 的 mtime 和 SHA256 与缓存一致
- **THEN** 跳过该文件，复用缓存中的索引数据

### Requirement: 增量构建模式

`indexer/builder.py` SHALL 在 `build_incremental()` 中仅重新解析变更文件。

#### Scenario: 单文件修改

- **WHEN** 项目有 100 个文件，仅 `top.v` 被修改
- **THEN** 仅重新解析 `top.v` 并更新其模块索引，其余 99 个文件复用缓存

#### Scenario: 新增文件

- **WHEN** 项目中新增 `new_module.v`
- **THEN** 解析新文件并将其模块添加到索引

#### Scenario: 删除文件

- **WHEN** 缓存中有 `old_module.v` 但文件已不存在
- **THEN** 从索引中移除 `old_module.v` 的所有模块

### Requirement: 缓存格式扩展

`database/index_store.py` SHALL 在 JSON 缓存中存储文件哈希和缓存版本。

#### Scenario: 缓存包含文件哈希

- **WHEN** 执行增量构建
- **THEN** JSON 缓存包含 `_file_hashes: {"top.v": "sha256...", ...}` 字段

#### Scenario: 缓存版本不匹配

- **WHEN** 缓存版本号与当前代码版本不一致
- **THEN** 忽略缓存，执行全量构建

### Requirement: 增量构建 CLI 参数

`server.py` SHALL 在 `rtl_build_index` 工具中支持增量模式。

#### Scenario: 指定增量模式

- **WHEN** 调用 `rtl_build_index(path, incremental=True)`
- **THEN** 使用增量构建模式
