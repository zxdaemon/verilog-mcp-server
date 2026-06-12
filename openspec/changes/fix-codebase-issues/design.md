## Context

代码库分析报告（`reports/codebase-analysis-2026-06-04.md`）识别出 20 个问题，本设计聚焦其中严重和中等级别（#1-#10）的修复方案，兼覆盖若干低成本的轻微问题。

当前架构：四层分层（indexer → database → analysis → tools），SQLite + 内存缓存，tree-sitter 解析。

## Goals / Non-Goals

**Goals:**
- 修复 `rtl_port_dataflow` 的 `NameError` 崩溃（P0 级 bug）
- 消除数据库 N+1 查询和非原子事务
- 减少跨模块追踪的性能瓶颈
- 收敛异常处理，避免静默吞错
- 添加缺失的 SQLite 索引

**Non-Goals:**
- 不引入分析结果缓存（涉及更复杂的失效策略，留给独立 change）
- 不重构代码重复（影响面大，留给独立 change）
- 不修改公共 API 签名（保持向后兼容）

## Decisions

### 1. `get_all_modules()` 批量加载

**选择**: 在 `IndexStore.get_all_modules()` 中检测 DB 后端时，委托给 `SQLiteBackend.load_all_modules()` 的单次 `SELECT * FROM modules` 查询，一次性填充内存缓存。

**替代方案**: 在调用方逐个 `_ensure_loaded()` 改为循环 `get_module()` → 拒绝，因为 `get_module` 已有缓存逻辑，但批量 SQL 查询仍然比 N 次 round-trip 高效。

### 2. `fan_in/fan_out` 父模块查找优化

**选择**: 在 `IndexStore` 中新增 `find_instantiators(module_name: str) -> list[str]` 方法，预先建立 `{module_name: [instantiator_modules]}` 反向索引。`fan_in._trace_input_port_fan_in()` 和 `fan_out._trace_output_port_fan_out()` 改为调用此方法而非遍历 `get_all_modules()`。

**替代方案**: 使用 SQL JOIN 查询 → 过于依赖 DB 层，内存反向索引与现有缓存策略更一致。

### 3. 事务保护

**选择**: 在 `SQLiteBackend.save_module()` 方法体内添加 `self._conn.execute("BEGIN")` / `self._conn.commit()` 包裹三个写操作（modules + files + signal_index）。异常时 `ROLLBACK`。

**替代方案**: 使用 context manager (`with self._conn:`) → sqlite3 模块原生支持，更简洁。采用此方案。

### 4. `DataflowTracer._visited` 局部化

**选择**: 从 `__init__` 中移除 `self._visited`，改为在 `trace_signal()` 方法内部创建局部变量 `visited: set[tuple[str, str, str]] = set()`，通过参数传递给内部递归函数。

### 5. 异常收敛

**选择**: 各处的 `except Exception` 替换为 `except (tree_sitter.ParserError, ValueError, KeyError, IndexError)` 等具体类型集。分析层保留 `except DomainError`。

### 6. HTML 模板外置

**选择**: 使用 `importlib.resources.files()` 从包数据目录加载 `templates/visualizer.html`，不再内联在 Python 文件中。模板中的 `{variable}` 占位符使用 `string.Template` 的 `$variable` 语法，避免 `.format()` 的 `{`/`}` 冲突。

### 7. SQLite 索引

**选择**: 在 `_SCHEMA_SQL` 中添加：
```sql
CREATE INDEX IF NOT EXISTS idx_signal_name ON signal_index(signal_name);
CREATE INDEX IF NOT EXISTS idx_modules_file_path ON modules(file_path);
```

这些索引在 `CREATE TABLE IF NOT EXISTS` 之后执行，对已有数据库也生效。

## Risks / Trade-offs

- **反向索引内存开销**: `find_instantiators` 的 `{module: [parents]}` 字典与现有 `_meta` 占用相当，对千模块级设计可忽略（< 1MB）
- **事务包裹写放大**: `save_module` 用 `with self._conn:` 后，SQLite 在事务期间持有写锁。当前为单线程 stdio 模式无影响，若未来改为多线程需重新评估
- **模板外置增加部署复杂度**: 需要确保 PyInstaller 打包时包含 `templates/` 目录（在 `.spec` 中添加 datas）
