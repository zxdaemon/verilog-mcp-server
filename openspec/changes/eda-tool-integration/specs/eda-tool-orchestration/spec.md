## ADDED Requirements

### Requirement: EdaToolOrchestrator 存在
项目 SHALL 在 `eda/orchestrator.py` 中提供 `EdaToolOrchestrator` 类，负责统一管理 EDA 工具的调用。构造函数接受配置字典，包含各工具的启用开关和路径。

#### Scenario: 导入编排器
- **WHEN** 执行 `from verilog_mcp_server.eda.orchestrator import EdaToolOrchestrator`
- **THEN** 成功导入 `EdaToolOrchestrator` 类

#### Scenario: 根据配置加载适配器
- **WHEN** 配置中 `eda_integration.slang.enabled=true` 且 `eda_integration.yosys.enabled=false`
- **THEN** `EdaToolOrchestrator` 加载 `SlangAdapter`，不加载 `YosysAdapter`

### Requirement: BaseEdaAdapter 接口
所有 EDA 工具适配器 SHALL 实现 `BaseEdaAdapter` 接口，包含以下方法：
- `check_available() -> bool`：检测工具是否在系统 PATH 中可用
- `run(project_path: str, top_module: str | None, output_dir: str) -> bool`：执行工具，生成报告
- `parse_output(output_dir: str) -> dict`：解析工具输出，返回结构化数据

#### Scenario: 检测工具可用性
- **WHEN** 调用 `SlangAdapter().check_available()` 且系统 PATH 中有 `slang`
- **THEN** 返回 `True`

#### Scenario: 检测工具不可用
- **WHEN** 调用 `DcAdapter().check_available()` 且系统 PATH 中无 `dc_shell`
- **THEN** 返回 `False`，记录 warning 日志

### Requirement: EDA 输出缓存
`EdaToolOrchestrator` SHALL 在调用工具前检查缓存。缓存策略：计算输入文件列表的 SHA256，若与缓存记录匹配且源文件未变更，直接解析缓存输出。缓存目录为 `.verilog_mcp/eda_outputs/<tool_name>/<input_hash>/`。

#### Scenario: 缓存命中
- **WHEN** 源文件未变更且已有缓存
- **THEN** 跳过工具调用，直接返回缓存的解析结果

#### Scenario: 缓存未命中
- **WHEN** 源文件已变更或无缓存
- **THEN** 调用 EDA 工具，生成输出，更新缓存

### Requirement: 异步执行支持
`EdaToolOrchestrator.run_all()` SHALL 支持异步执行多个 EDA 工具。使用 `asyncio` 或 `concurrent.futures` 并发运行独立的工具。工具执行期间 MCP Server 保持响应。

#### Scenario: 并发运行多个工具
- **WHEN** 同时启用 slang 和 Yosys
- **THEN** 两个工具并发执行，总时间接近单个最慢工具的时间

### Requirement: 错误处理与降级
当 EDA 工具调用失败（返回非零退出码、输出文件缺失、解析异常）时，`EdaToolOrchestrator` SHALL 记录错误日志，跳过该工具，继续处理其他工具。系统不因单个 EDA 工具失败而崩溃。

#### Scenario: slang 调用失败
- **WHEN** `slang` 因语法错误退出
- **THEN** 记录错误，跳过 slang 输出，Yosys 和其他工具继续正常运行
