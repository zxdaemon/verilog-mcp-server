## ADDED Requirements

### Requirement: 按文件删除模块

`database/index_store.py` SHALL 提供 `remove_file(file_path)` 方法，删除指定文件的所有模块和相关索引。

#### Scenario: 删除文件的所有模块

- **WHEN** 调用 `remove_file("top.v")` 且该文件有 3 个模块
- **THEN** 从 `modules` 表删除 3 行，从 `files` 表删除 3 行，从 `signal_index` 表删除相关条目

#### Scenario: 删除不存在的文件

- **WHEN** 调用 `remove_file("nonexistent.v")`
- **THEN** 不产生错误，静默返回

### Requirement: 增量构建模式

`indexer/builder.py` SHALL 支持 `build_incremental(changed_files)` 方法，仅重新解析指定文件。

#### Scenario: 增量更新单个文件

- **WHEN** 调用 `build_incremental(["top.v"])`
- **THEN** 先调用 `remove_file("top.v")` 清除旧数据，再重新解析 `top.v` 并插入新数据

#### Scenario: 增量更新多个文件

- **WHEN** 调用 `build_incremental(["top.v", "sub.v"])`
- **THEN** 依次对每个文件执行"删除旧数据 → 重新解析 → 插入新数据"

### Requirement: 文件变更检测

`indexer/builder.py` SHALL 通过文件 mtime 和 SHA256 检测文件是否变更。

#### Scenario: 文件内容已修改

- **WHEN** 文件 mtime 比数据库中记录新，且 SHA256 不同
- **THEN** 将该文件标记为需要重新解析

#### Scenario: 文件未变更

- **WHEN** 文件 mtime 和 SHA256 均与数据库记录一致
- **THEN** 跳过该文件

### Requirement: 新增和删除文件处理

`indexer/builder.py` SHALL 处理项目中新增和删除的文件。

#### Scenario: 新增文件

- **WHEN** 扫描发现数据库中不存在的文件
- **THEN** 解析该文件并插入新模块

#### Scenario: 文件已删除

- **WHEN** 数据库中有某文件的模块但文件已不存在
- **THEN** 调用 `remove_file()` 清除该文件的所有数据
