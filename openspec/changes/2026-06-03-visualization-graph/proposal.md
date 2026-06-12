## Why

当前 MCP server 的所有分析结果（模块层次、信号追踪、FSM 检测、时钟域分析）均以纯文本或 Markdown 输出，缺乏可视化能力。对于复杂的 RTL 设计，文本形式的层次树和信号流难以直观理解模块间关系和数据通路。

参考 Understand-Anything 项目的知识图谱可视化架构，为 verilog-mcp-server 添加图谱可视化功能，使 AI agent 和用户能够更直观地理解 RTL 设计结构。

## What Changes

- 为现有分析引擎添加 Mermaid 格式输出（hierarchy、fsm、dataflow、clock）
- 新增统一 `rtl_visualize` MCP 工具，支持 auto 检测图类型
- 新增交互式 HTML 图谱生成器，基于 vis.js 实现可缩放/拖拽/点击的图谱
- 新增通用图数据模型（GraphData），作为分析结果到可视化的中间表示

## Capabilities

### New Capabilities

- `mermaid-hierarchy`: 模块层次树 Mermaid flowchart 输出
- `mermaid-fsm`: FSM 状态机 Mermaid stateDiagram 输出
- `mermaid-dataflow`: 信号数据流 Mermaid flowchart 输出
- `html-interactive`: 交互式 HTML 图谱生成（vis.js，支持缩放/拖拽/点击详情）
- `unified-visualize`: 统一可视化入口 `rtl_visualize`，auto 检测图类型

### Modified Capabilities

- `clock-tree`: 增强现有 `format_mermaid()` 添加主题和样式

## Impact

- `analysis/hierarchy.py` 新增 `HierarchyBuilder.format_mermaid()` 方法
- `analysis/fsm_detector.py` 新增 `FSM.format_mermaid()` 和 `FSMDetector.format_mermaid()` 方法
- `analysis/fan_in.py` 新增 `DataflowTracer.format_mermaid()` 静态方法
- `analysis/visualizer.py` **新建**，包含 GraphData 模型、转换函数、HtmlVisualizer
- `tools/visualize.py` **新建**，注册 `rtl_visualize` MCP 工具
- `tools/__init__.py` 导出 register_visualize
- `server.py` 注册 visualize tools
- 所有现有 MCP 工具接口保持不变
- 零新依赖（Mermaid 是纯文本，HTML 通过 CDN 加载 vis.js）
