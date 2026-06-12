## ADDED Requirements

### Requirement: 多进程并行解析

`indexer/builder.py` SHALL 使用 `ProcessPoolExecutor` 并行调用 tree-sitter 解析文件。

#### Scenario: 大型项目并行解析

- **WHEN** 项目有 100 个 .v 文件，CPU 有 8 核
- **THEN** 使用 8 个进程并行解析，总时间约为串行的 1/8

#### Scenario: 解析结果收集

- **WHEN** 所有进程完成解析
- **THEN** 主进程收集所有解析结果，按顺序提取模块/信号/例化等

### Requirement: 并行阈值

`indexer/builder.py` SHALL 根据文件数量决定是否使用并行。

#### Scenario: 小项目不使用并行

- **WHEN** 项目文件数少于 10
- **THEN** 使用串行解析（避免进程启动开销）

#### Scenario: 中型项目使用并行

- **WHEN** 项目文件数 >= 10
- **THEN** 使用并行解析

### Requirement: Worker 数量配置

`indexer/builder.py` SHALL 支持配置并行 worker 数量。

#### Scenario: 默认 worker 数量

- **WHEN** 未指定 worker 数量
- **THEN** 默认使用 `min(cpu_count, 8)`

#### Scenario: 自定义 worker 数量

- **WHEN** 调用 `build_index(path, max_workers=4)`
- **THEN** 使用 4 个 worker 进程

### Requirement: 解析函数可序列化

`indexer/verilog_parser.py` 的 `parse_single_file` SHALL 为顶层函数，支持 pickle 序列化以供 ProcessPoolExecutor 使用。

#### Scenario: 跨进程调用

- **WHEN** `parse_single_file` 被传递给 worker 进程
- **THEN** 函数和参数可正常序列化/反序列化，返回解析结果
