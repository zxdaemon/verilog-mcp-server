## MODIFIED Requirements

### Requirement: pyproject.toml 存在且完整
项目根目录 SHALL 包含 `pyproject.toml`，声明项目元数据、Python 版本要求（>=3.11）和全部运行时依赖。`[tool.pytest.ini_options]` 段 SHALL 配置 `testpaths = ["tests"]` 和 `python_files = ["test_*.py"]`。

#### Scenario: 通过 pyproject.toml 安装依赖
- **WHEN** 开发者执行 `uv pip install -r requirements.txt` 或 `pip install -e .`
- **THEN** 所有依赖（mcp、tree-sitter-language-pack、pyyaml）被正确安装
- **AND** `uv run pytest` 可以正常运行

## ADDED Requirements

### Requirement: config.yaml 支持 EDA 工具配置
`config.yaml` SHALL 新增 `eda_integration` 配置段，包含各工具的启用开关、可执行文件路径、额外参数。示例：
```yaml
eda_integration:
  enabled: true
  output_dir: ".verilog_mcp/eda_outputs"
  slang:
    enabled: true
    path: "slang"
    extra_args: "--ignore-unknown-modules"
  yosys:
    enabled: true
    path: "yosys"
  dc_shell:
    enabled: false
    path: "/usr/synopsys/dc/bin/dc_shell"
  pt_shell:
    enabled: false
    path: "/usr/synopsys/pt/bin/pt_shell"
```

#### Scenario: 配置 EDA 工具路径
- **WHEN** 用户在 `config.yaml` 中配置 `eda_integration.slang.path: "/custom/path/slang"`
- **THEN** `EdaToolOrchestrator` 使用指定路径调用 slang

#### Scenario: 禁用所有 EDA 工具
- **WHEN** 用户设置 `eda_integration.enabled: false`
- **THEN** 系统完全不调用任何 EDA 工具，纯 tree-sitter 模式运行

### Requirement: 项目扫描器支持 EDA 输出目录排除
`ProjectScanner` SHALL 默认排除 `.verilog_mcp/eda_outputs/` 目录，避免将 EDA 生成的中间文件误识别为 RTL 源文件。

#### Scenario: EDA 输出目录被排除
- **WHEN** `ProjectScanner` 扫描项目目录
- **THEN** `.verilog_mcp/eda_outputs/` 下的文件不被纳入索引
