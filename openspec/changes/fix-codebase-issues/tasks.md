## 1. P0: 崩溃 bug 修复

- [x] 1.1 修复 `rtl_port_dataflow` NameError — `tools/level3_analysis.py:298-318`：将 `lines` 初始化提前到 `try` 块开头，确保 `result is not None` 路径可正常返回
- [x] 1.2 添加 `rtl_port_dataflow` 正常路径的单元测试（当前无覆盖）

## 2. P0: 数据库层修复

- [x] 2.1 在 `sqlite_backend.py` 的 `_SCHEMA_SQL` 中添加 `idx_signal_name` 和 `idx_modules_file_path` 二级索引
- [x] 2.2 在 `sqlite_backend.py` 中新增 `load_all_modules()` 方法，单次 `SELECT * FROM modules`
- [x] 2.3 在 `index_store.py` 的 `get_all_modules()` 中委托 DB 后端的 `load_all_modules()`，消除 N+1 查询
- [x] 2.4 为 `sqlite_backend.py` 的 `save_module()` 添加 `with self._conn:` 事务包裹（三个写操作原子化）

## 3. P0: 跨模块追踪性能

- [x] 3.1 在 `index_store.py` 中新增 `find_instantiators(module_name)` 方法，返回例化了指定模块的父模块名列表
- [x] 3.2 重构 `fan_in.py` 的 `_trace_input_port_fan_in()`，用 `find_instantiators()` 替代 `get_all_modules()` 遍历
- [x] 3.3 重构 `fan_out.py` 的 `_trace_output_port_fan_out()`，同上替换

## 4. P1: 异常收敛

- [x] 4.1 将 `verilog_parser.py` 中 `get_node_text`、`get_node_line` 等的 `except Exception` 替换为具体异常类型
- [x] 4.2 将 `clock_tree.py:137` 和 `expr_walker.py:78` 的 `except Exception` 替换为具体类型
- [x] 4.3 将 `tools/visualize.py:115` 的 `except Exception` 替换为 `except DomainError`

## 5. P1: 并发隐患与 AST 遍历

- [x] 5.1 将 `DataflowTracer._visited` 从实例属性改为 `trace_signal()` 内的局部变量，通过参数传递
- [x] 5.2 重构 `IndexBuilder` 中每模块的两次 AST 遍历为一次，让提取器返回 AST 节点引用

## 6. P2: 可视化模板与稳定性

- [x] 6.1 创建 `verilog_mcp_server/templates/visualizer.html`，将 `_HTML_TEMPLATE` 从 Python 内联字符串移入
- [x] 6.2 重构 `HtmlVisualizer.generate()` 使用 `importlib.resources` 加载模板 + `string.Template.safe_substitute()` 替代 `.format()`
- [x] 6.3 更新 `verilog-mcp-server.spec` 的 `datas` 包含 `templates/` 目录
- [x] 6.4 在 `sqlite_backend.py` 的 `SQLiteBackend.__init__()` 中添加 `atexit.register(self.close)`

## 7. 验证

- [x] 7.1 运行全量测试 `pytest tests/ -v`，确保所有已有测试通过
- [x] 7.2 验证 PyInstaller 打包正常，`templates/` 目录正确包含
