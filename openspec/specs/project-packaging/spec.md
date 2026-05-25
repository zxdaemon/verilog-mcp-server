## ADDED Requirements

### Requirement: pyproject.toml 存在且完整

项目根目录 SHALL 包含 `pyproject.toml`，声明项目元数据、Python 版本要求（>=3.11）和全部运行时依赖。`[tool.pytest.ini_options]` 段 SHALL 配置 `testpaths = ["tests"]` 和 `python_files = ["test_*.py"]`。

#### Scenario: 通过 pyproject.toml 安装依赖

- **WHEN** 开发者执行 `uv pip install -r requirements.txt` 或 `pip install -e .`
- **THEN** 所有依赖（mcp、tree-sitter-language-pack、pyyaml）被正确安装
- **AND** `uv run pytest` 可以正常运行

### Requirement: .gitignore 存在

项目根目录 SHALL 包含 `.gitignore`，排除 `__pycache__/`、`*.pyc`、`.venv/`、`*.egg-info/`、`/tmp/` 等生成目录和文件。

#### Scenario: git status 不显示生成文件

- **WHEN** 执行 `git status`
- **THEN** `__pycache__/` 和 `.venv/` 目录不出现在未跟踪文件列表中
