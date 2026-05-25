## ADDED Requirements

### Requirement: 工具业务逻辑作为独立可测试函数

每个 `tools/level*.py` 中的 tool 逻辑 SHALL 拆分为两层：
- `_do_*()` 函数：接收 `IndexStore` + tool 参数，返回数据对象（如 `list[ModuleDef]`、`TraceResult` 等），仅在出错时抛出 `DomainError`
- `_fmt_*()` 函数：接收数据对象，返回格式化后的 Markdown 字符串

`register_tools()` SHALL 仅负责创建引擎实例、用 `@mcp.tool()` 装饰 tool 函数、在内部调用 `_do_*`/`_fmt_*`。

#### Scenario: 搜索逻辑可脱离 MCP 测试

- **WHEN** 调用 `_do_search_module(index_store, "adder")`
- **THEN** 返回匹配 "adder" 的 `list[ModuleDef]`，不依赖任何 MCP 框架

#### Scenario: 格式化逻辑为纯函数

- **WHEN** 调用 `_fmt_module_summary(mod)` 其中 `mod` 是包含端口和信号的 ModuleDef
- **THEN** 返回包含端口列表、信号列表、文件路径的 Markdown 字符串
- **AND** 函数不访问 IndexStore 或任何外部状态

### Requirement: 现有 MCP tool 接口保持不变

所有 MCP tool 的名称、参数签名（名称、类型、默认值）和返回值类型 SHALL 保持不变。外部 MCP 客户端 SHALL 不察觉任何变化。

#### Scenario: MCP tool 调用行为不变

- **WHEN** MCP 客户端调用 `rtl_search_module(pattern="top")`
- **THEN** 返回结果与重构前格式相同（模块名、文件路径、端口数）
