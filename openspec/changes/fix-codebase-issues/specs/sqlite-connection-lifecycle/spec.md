## ADDED Requirements

### Requirement: 正常关闭时清理数据库连接

`database/sqlite_backend.py` 的 `SQLiteBackend` SHALL 在进程正常退出时自动关闭数据库连接。

#### Scenario: atexit 注册

- **WHEN** `SQLiteBackend.__init__()` 成功打开数据库连接
- **THEN** 自动调用 `atexit.register(self.close)`，确保退出时执行 `self._conn.close()`

#### Scenario: 重复 close 安全

- **WHEN** `SQLiteBackend.close()` 被多次调用
- **THEN** 第二次及后续调用静默返回，不抛出异常

### Requirement: HTML 模板独立文件

`analysis/visualizer.py` 的 HTML 模板 SHALL 存储在独立的 `templates/visualizer.html` 文件中，使用 `importlib.resources` 加载。

#### Scenario: 模板加载

- **WHEN** `HtmlVisualizer.generate()` 被调用
- **THEN** 从 `verilog_mcp_server/templates/visualizer.html` 加载模板内容，使用 `string.Template.safe_substitute()` 填充变量

#### Scenario: 打包包含模板

- **WHEN** 使用 PyInstaller 打包为独立可执行文件
- **THEN** `templates/` 目录被包含在打包数据中，运行时 `importlib.resources.files()` 可正常访问

### Requirement: HTML 标题中的特殊字符安全

`HtmlVisualizer.generate()` SHALL 正确处理 `graph_data.title` 中包含 `{`、`}`、`$` 等特殊字符的情况。

#### Scenario: 标题含花括号

- **WHEN** `graph_data.title = "top{foo}"`
- **THEN** HTML 正常生成，标题正确显示，不抛出 `KeyError`
