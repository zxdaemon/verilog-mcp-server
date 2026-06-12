## Why

代码库分析发现 1 个确认的运行时崩溃 bug（`rtl_port_dataflow` 中 `NameError`）、数据库层 N+1 查询和非原子事务、分析引擎 O(depth × modules) 性能陷阱，以及广泛存在的代码重复和异常吞没问题。这些直接影响服务稳定性和分析结果可靠性，需在功能开发前修复。

## What Changes

### 严重问题修复（P0）

- 修复 `rtl_port_dataflow` 中 `lines` 变量未定义导致的 `NameError` 崩溃
- 消除 `get_all_modules()` 的 N+1 查询模式，改为批量加载
- 消除 `fan_in`/`fan_out` 跨模块追踪中每层递归调用 `get_all_modules()` 的 O(depth × modules) 性能问题
- 为 `save_module` 添加显式 `BEGIN`/`COMMIT` 事务保护

### 中等问题修复（P1）

- 收敛 `except Exception` 为具体异常类型
- 为 `signal_index(signal_name)` 和 `modules(file_path)` 添加 SQLite 二级索引
- 将 `DataflowTracer._visited` 从实例属性改为局部变量，消除并发隐患
- 消除 `IndexBuilder` 中每模块两次 AST 遍历的浪费

### 轻微问题修复（P2）

- 将 HTML 模板从 Python 内联字符串提取为独立 `.html` 文件
- 修复 `graph_data.title` 用 `.format()` 插值在含 `{`/`}` 时崩溃的问题
- 添加 `atexit` 注册确保 `SQLiteBackend.close()` 在退出时调用
- 统一可视化 CDN 使用本地 fallback
- `rtl_port_dataflow` 的异常处理收敛为 `DomainError`

## Capabilities

### New Capabilities

- `sqlite-connection-lifecycle`: SQLite 连接生命周期管理 — atexit 清理、模板文件加载替代内联字符串

### Modified Capabilities

- `sqlite-backend`: 添加二级索引、显式事务保护、批量加载接口
- `incremental-update`: `get_all_modules()` 改为批量加载，消除 N+1 查询

## Impact

- `database/sqlite_backend.py` — 添加索引、事务、批量加载方法
- `database/index_store.py` — `get_all_modules()` 委托批量加载
- `analysis/fan_in.py` — 消除递归中 `get_all_modules()` 调用，`_visited` 局部化
- `analysis/fan_out.py` — 同上
- `analysis/visualizer.py` — 模板外置、format 崩溃修复、CDN fallback
- `tools/level3_analysis.py` — `rtl_port_dataflow` NameError 修复
- `indexer/builder.py` — 避免双 AST 遍历
- `server.py` — atexit 注册
