# 代码库分析报告

日期: 2026-06-04

## 优点

### 架构设计
- 四层清晰分层（indexer → database → analysis → tools），无循环导入
- 数据模型全部使用 dataclass，配合 `to_dict()`/`to_row()` 双序列化
- 工具注册采用依赖注入（`IndexStore` 通过参数传入），无全局状态
- 惰性加载设计合理：`IndexStore` 启动时只加载元数据，按需加载完整模块

### 类型与错误处理
- `from __future__ import annotations` 全量使用，无 `Any` 类型
- 定义了领域异常层级（`database/errors.py`），工具层统一捕获并返回用户可读错误

### MCP 工具设计
- 三级工具 + 可视化工具分层合理，各层职责清晰
- 工具 docstring 直接作为 MCP 描述暴露给 LLM 客户端

### 数据库
- SQLite WAL 模式 + `synchronous=NORMAL`，性能与数据安全平衡
- `INSERT OR REPLACE` 幂等 upsert，支持增量重建

### 可视化
- 通用 `GraphData` 模型 + 四种转换函数（层次/FSM/数据流/时钟），可输出 Mermaid 和 HTML
- HTML 支持分层布局、双击钻取、面包屑导航、图例配色

---

## 缺点

### 严重

| # | 问题 | 位置 |
|---|------|------|
| 1 | `rtl_port_dataflow` 有 NameError bug — 当 `result` 非 None 时 `lines` 未定义，line 318 必崩溃 | `tools/level3_analysis.py:298-318` |
| 2 | `get_all_modules()` 存在 N+1 查询 — 逐个调用 `_ensure_loaded` 而非批量 `load_all_modules()` | `database/index_store.py:187-193` |
| 3 | `fan_in/fan_out` 在遍历每层递归时调用 `get_all_modules()` — 复杂度 O(depth × total_modules) | `analysis/fan_in.py:166`, `analysis/fan_out.py:60` |
| 4 | `save_module` 的事务非原子 — 三次写操作之间无显式 `BEGIN/COMMIT`，中途失败导致部分数据 | `database/sqlite_backend.py:83-102` |

### 中等

| # | 问题 | 位置 |
|---|------|------|
| 5 | 大量代码重复 — DFS 树遍历、父模块查找、文本树格式化、Mermaid 生成、信号/端口线性搜索、`_sanitize_id` 等均有 2-4 处重复实现 | `hierarchy.py`, `fan_in.py`, `fan_out.py`, `cross_ref.py`, `clock_tree.py`, `visualizer.py` |
| 6 | 裸 `except Exception` 5+ 处 — 吞掉 `KeyboardInterrupt` 等关键异常 | `clock_tree.py:137`, `expr_walker.py:78`, `verilog_parser.py:99,113,122`, `visualize.py:115` |
| 7 | 缺少 SQLite 二级索引 — `signal_index` 的 `LIKE` 模糊查询、`modules.file_path` 删除查询均未建索引 | `database/sqlite_backend.py` |
| 8 | 分析引擎无结果缓存 — 每次调用 `build_tree()`/`trace_signal()` 等均从头计算 | 所有 `analysis/*.py` |
| 9 | `DataflowTracer._visited` 是实例属性而非局部变量 — 并发调用会互相污染 | `analysis/fan_in.py:74` |
| 10 | `IndexBuilder` 对每个模块做两次 AST 遍历 — 提取器已找到节点但不返回，builder 再次搜索 | `indexer/builder.py:67-89` |

### 轻微

| # | 问题 | 位置 |
|---|------|------|
| 11 | 286 行 HTML 模板内联在 Python 文件中，难以维护和格式化 | `analysis/visualizer.py:222-508` |
| 12 | `config: dict` 无类型定义 — 无法静态检查配置键名 | `server.py:57,97`, `indexer/builder.py:27` |
| 13 | `graph_data.title` 用 `.format()` 插值 — 若含 `{`/`}` 会崩溃 | `analysis/visualizer.py:554` |
| 14 | 可视化 CDN 硬编码 — unpkg 不可用时 HTML 页面白屏 | `analysis/visualizer.py:229` |
| 15 | 无 `atexit` 清理 — `SQLiteBackend.close()` 存在但从未调用 | `database/sqlite_backend.py:73` |
| 16 | 分析引擎方法签名不统一 — `build_tree`/`trace_signal`/`analyze`/`classify`/`build` 命名各异 | 各 `analysis/*.py` |
| 17 | 测试缺少 `pytest.mark` 分类和覆盖率配置 | `tests/`, `pyproject.toml` |
| 18 | `clock_tree.py` 327 行无任何测试覆盖 | `tests/` |
| 19 | `InstanceExtractor._index_store` 通过外部赋值注入 — 若未设置则静默退化 | `indexer/instance_extractor.py`, `indexer/builder.py:34` |
| 20 | JSON 元数据冗余解析 — 启动时解析 `ports_json` 构建信号索引，但 `signal_index` 表已有相同数据 | `database/index_store.py:56-92` |
