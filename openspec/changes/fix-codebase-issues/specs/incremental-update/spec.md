## MODIFIED Requirements

### Requirement: 按文件删除模块

`database/index_store.py` SHALL 提供 `remove_file(file_path)` 方法，删除指定文件的所有模块和相关索引。

#### Scenario: 删除文件的所有模块

- **WHEN** 调用 `remove_file("top.v")` 且该文件有 3 个模块
- **THEN** 使用 `idx_modules_file_path` 索引快速定位模块，从 `modules` 表删除 3 行，从 `files` 表删除 3 行，从 `signal_index` 表删除相关条目

#### Scenario: 删除不存在的文件

- **WHEN** 调用 `remove_file("nonexistent.v")`
- **THEN** 不产生错误，静默返回
