## MODIFIED Requirements

### Requirement: pyproject.toml 存在且完整
项目根目录 SHALL 包含 `pyproject.toml`，声明项目元数据、Python 版本要求（>=3.11）和全部运行时依赖。`[tool.pytest.ini_options]` 段 SHALL 配置 `testpaths = ["tests"]` 和 `python_files = ["test_*.py"]`。

#### Scenario: 通过 pyproject.toml 安装依赖
- **WHEN** 开发者执行 `uv pip install -r requirements.txt` 或 `pip install -e .`
- **THEN** 所有依赖（mcp、tree-sitter-language-pack、pyyaml）被正确安装
- **AND** `uv run pytest` 可以正常运行

## ADDED Requirements

### Requirement: pyproject.toml 声明 pyslang 依赖
`pyproject.toml` 的 `dependencies` 段 SHALL 包含 `pyslang>=11.0.0,<12.0.0`。该依赖为必需（非 optional），安装项目时自动安装。

#### Scenario: pip 安装包含 pyslang
- **WHEN** 执行 `pip install -e .`
- **THEN** `pyslang` 被自动安装为运行时依赖

### Requirement: pyslang 版本兼容性
项目代码 SHALL 兼容 pyslang v11.x API。当 pyslang v12 发布时，需要验证 API 兼容性后再升级版本约束。

#### Scenario: pyslang v11 正常工作
- **WHEN** 环境中安装 pyslang 11.0.0
- **THEN** 所有 pyslang 相关功能正常工作
