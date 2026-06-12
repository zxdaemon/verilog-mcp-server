## ADDED Requirements

### Requirement: PyslangParser 封装 pyslang API
`PyslangParser` SHALL 封装 `pyslang.SyntaxTree` 和 `pyslang.Compilation`，提供与现有 `verilog_parser.py` 风格一致的接口。核心方法：
- `parse_files(file_paths: list[str]) -> Compilation` — 解析多个文件，返回 `pyslang.Compilation` 对象
- `elaborate(compilation: Compilation, top_module: str | None) -> DesignRoot` — 执行 elaboration，返回 elaborated design root
- `get_diagnostics(compilation: Compilation) -> list[dict]` — 获取解析/语义错误和警告列表

#### Scenario: 解析单个文件
- **WHEN** 调用 `parse_files(["top.sv"])`
- **THEN** 返回 `Compilation` 对象，无异常抛出

#### Scenario: 解析多文件设计
- **WHEN** 调用 `parse_files(["top.sv", "cpu.v", "alu.v"])`
- **THEN** `Compilation` 正确处理跨文件引用（`include、模块实例化）

#### Scenario: 检测语法错误
- **WHEN** 源码包含语法错误（如未闭合的 `module`）
- **THEN** `get_diagnostics()` 返回错误列表，含文件路径、行号、错误消息
- **AND** tree-sitter 索引继续正常进行（pyslang 错误不阻塞整体流程）

### Requirement: pyslang 支持文件列表和 include 路径
`PyslangParser.parse_files()` SHALL 接受 `include_dirs` 和 `defines` 参数，正确传递给 pyslang 的预处理阶段。支持 `.f` 文件列表解析（复用现有 `FilelistParser`）。

#### Scenario: 含 include 路径的解析
- **WHEN** 调用 `parse_files(["top.sv"], include_dirs=["./includes"])`
- **THEN** pyslang 正确找到并解析 `"./includes/common.vh"`

#### Scenario: 含宏定义的解析
- **WHEN** 调用 `parse_files(["top.sv"], defines={"WIDTH": "32"})`
- **THEN** pyslang 预处理阶段将 `` `WIDTH `` 展开为 `32`

### Requirement: pyslang 作为核心依赖
`pyproject.toml` SHALL 声明 `pyslang>=11.0.0,<12.0.0` 为运行时依赖。安装项目时自动安装 pyslang，无需用户额外操作。

#### Scenario: pip 安装自动获得 pyslang
- **WHEN** 用户执行 `pip install -e .`
- **THEN** `pyslang` 作为依赖被自动安装
- **AND** `import pyslang` 在项目中可用

### Requirement: pyslang 降级支持
当 `import pyslang` 失败时（如平台不支持预编译 wheel 且编译失败），系统 SHALL 回退到纯 tree-sitter 模式，记录 warning 日志，不影响其他功能。

#### Scenario: pyslang 不可用时降级
- **WHEN** `import pyslang` 失败（如 ARM 平台无 wheel）
- **THEN** 系统正常工作，tree-sitter 索引不受影响
- **AND** MCP 工具返回的数据不含 pyslang 增强信息
