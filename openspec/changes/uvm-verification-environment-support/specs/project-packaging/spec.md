## MODIFIED Requirements

### Requirement: pyproject.toml 存在且完整
项目根目录 SHALL 包含 `pyproject.toml`，声明项目元数据、Python 版本要求（>=3.11）和全部运行时依赖。`[tool.pytest.ini_options]` 段 SHALL 配置 `testpaths = ["tests"]` 和 `python_files = ["test_*.py"]`。

#### Scenario: 通过 pyproject.toml 安装依赖
- **WHEN** 开发者执行 `uv pip install -r requirements.txt` 或 `pip install -e .`
- **THEN** 所有依赖（mcp、tree-sitter-language-pack、pyyaml）被正确安装
- **AND** `uv run pytest` 可以正常运行

## ADDED Requirements

### Requirement: 项目扫描器识别 UVM 验证文件
`ProjectScanner` SHALL 在扫描项目目录时，将 UVM 验证文件（`.sv` 文件中包含 `class` 定义或 `package` 定义）纳入索引范围。默认文件扩展名保持 `.v` / `.sv` / `.svh` 不变，但排除规则不应排除以 `_env`/`_agent`/`_test`/`_seq`/`_drv`/`_mon`/`_scb` 结尾的 `.sv` 文件。

#### Scenario: UVM 验证文件被索引
- **WHEN** 项目目录包含 `my_agent.sv`、`my_test.sv`、`my_env.sv`
- **THEN** 这些文件被 `ProjectScanner` 发现并纳入索引

#### Scenario: 排除规则不误伤 UVM 文件
- **WHEN** 项目目录包含 `tb/` 子目录，其中有 UVM 验证代码
- **THEN** `tb/` 目录下的 `.sv` 文件默认不被排除（除非显式配置排除）

### Requirement: 索引构建器支持 class 提取
`IndexBuilder` SHALL 在构建索引时，除了提取 module/interface/package，还调用 `ClassExtractor` 和 `FunctionExtractor` 提取 class 和 function/task 定义，一并存入 `IndexStore`。

#### Scenario: 索引包含 class 数据
- **WHEN** 调用 `rtl_build_index` 索引包含 UVM 代码的项目
- **THEN** 索引状态统计中包含 class 数量和 method 数量

#### Scenario: 增量更新处理 class 变更
- **WHEN** UVM 验证文件被修改后调用 `rtl_update_index`
- **THEN** 仅重新解析变更文件中的 class 和 method，其他文件不受影响
