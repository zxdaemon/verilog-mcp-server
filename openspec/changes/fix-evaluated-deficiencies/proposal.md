## Why

近期代码库评估发现 6 类不足：2 个测试失败、README 与代码不同步、`indexer/__init__.py` 错误导出、`rtl_port_dataflow` 跨层级追踪功能不完整、FSM 检测局限于 case+next_state 模式、CDC 检测缺乏同步器识别导致误报。这些问题影响工具可靠性、文档准确性和分析精度，需要系统性修复。

## What Changes

- **测试修复**：修复 `test_extract_instances`（错误传入 root_node 而非 module_declaration）和 `test_no_ports_module`（非 ANSI header 返回 None 未检查）
- **文档同步**：更新 README，删除不存在的 `rtl_list_modules`，修正工具分类，补全 Level3 工具列表
- **导出修复**：从 `indexer/__init__.py` 的 `__all__` 中移除不存在的 `VerilogParser`
- **端口数据流增强**：实现 `rtl_port_dataflow` 的完整跨层级端口穿透追踪
- **FSM 检测增强**：支持非 case+next_state 编码风格的状态机（基于状态寄存器识别 + always 块敏感列表分析）
- **CDC 检测精度改进**：引入同步器模式识别（双触发器同步器、握手同步器），降低跨时钟域信号误报率

## Capabilities

### New Capabilities
- `cdc-synchronizer-detection`: 跨时钟域同步器识别与精确 CDC 检测 — 在现有 CDC 启发式检测基础上，识别双触发器同步器和握手同步器模式，区分安全的同步信号和真正的 CDC 风险信号
- `port-dataflow-tracing`: 端口数据流跨层级穿透追踪 — 从模块端口出发，穿透例化边界追踪信号到最终驱动源或负载

### Modified Capabilities
- `ast-fsm-detection`: 扩展状态机检测支持非标准编码风格 — 当前仅支持 case+next_state 模式，需增加基于状态寄存器识别和敏感列表分析的通用检测

## Impact

- `tests/test_instance_extractor.py` — 修复测试 helper 使用方式
- `tests/test_port_extractor.py` — 增强空模块边界处理
- `README.md` — 同步工具列表和分类
- `verilog_mcp_server/indexer/__init__.py` — 修正导出列表
- `verilog_mcp_server/tools/level3_analysis.py` — 增强 `rtl_port_dataflow` 实现
- `verilog_mcp_server/analysis/fsm_detector.py` — 扩展状态机检测算法
- `verilog_mcp_server/analysis/clock_analyzer.py` / `analysis/cross_ref.py` — 添加同步器识别逻辑
