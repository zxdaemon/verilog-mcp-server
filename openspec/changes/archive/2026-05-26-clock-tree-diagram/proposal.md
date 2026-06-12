## Why

当前 `rtl_clock_domains` 只能分析单个模块的时钟域（提取 always 块中的时钟信号），无法展示设计整体的时钟分布架构。实际项目中用户需要从顶层出发，了解时钟如何从 PLL 传播到各子模块、哪些模块在同一时钟域、门控时钟如何派生、以及复位信号关联关系。

## What Changes

- 新建 `analysis/clock_tree.py` 时钟树构建引擎，遍历模块层次树，通过 `port_connections` 追踪时钟信号名在层次间的映射，将模块按根时钟域分组
- 新建 MCP tool `rtl_clock_tree(top_module, max_depth, output_format)` — ASCII 树状图 + Mermaid flowchart 两种输出格式
- 支持可配置的门控时钟模块识别（通过模块名模式匹配）
- 输出包含：时钟域-模块映射、复位信号汇总、门控时钟点标记、无时钟模块列表

## Capabilities

### New Capabilities

- `clock-tree`: 全局时钟域结构图，跨模块追踪时钟信号，按时钟域分组展示所有模块及复位关系

### Modified Capabilities

<!-- 无现有 capability 需修改 -->

## Impact

- 新增文件: `analysis/clock_tree.py`
- 修改: `analysis/__init__.py`（导出 `ClockTreeBuilder`）
- 修改: `tools/level3_analysis.py`（注册 `rtl_clock_tree` tool）
- 修改: `tests/test_level3_tools.py`（新增测试）
- 依赖复用: `ClockAnalyzer`（单模块时钟检测）、`HierarchyBuilder`（层次遍历）、`InstanceDef.port_connections`（信号名映射）
- 所有现有 tool 接口和行为不变
