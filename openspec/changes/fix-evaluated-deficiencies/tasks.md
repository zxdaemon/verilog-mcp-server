## 1. 测试修复与代码一致性

- [x] 1.1 修复 `test_extract_instances`：从 source_file AST 中找到 `module_declaration` 节点再传入 `InstanceExtractor.extract_from_module_body()`
- [x] 1.2 修复 `test_no_ports_module`：增强 `_find_module_node` helper，支持 `module_nonansi_header` fallback，找不到时优雅跳过
- [x] 1.3 从 `indexer/__init__.py` 的 `__all__` 中移除不存在的 `VerilogParser`
- [x] 1.4 运行测试验证修复：`pytest tests/test_instance_extractor.py tests/test_port_extractor.py -v`

## 2. README 文档同步

- [x] 2.1 删除 README 中不存在的 `rtl_list_modules` 工具描述
- [x] 2.2 将 `rtl_hierarchy` 从 Level 2 修正为 Level 1 分类
- [x] 2.3 补全 Level 3 工具列表：添加 `rtl_reset_domains` 和 `rtl_cross_domain_signals`
- [x] 2.4 核对所有工具名称、参数与 `tools/` 目录中实际代码一致

## 3. 端口数据流跨层级追踪

- [x] 3.1 在 `analysis/fan_in.py` 的 `DataflowTracer` 中新增 `trace_port_dataflow(module_name, port_name, direction, max_depth)` 方法
- [x] 3.2 实现 `direction="input"` 路径：从模块输入端口 → 内部信号 → 穿透子模块例化输出端口 → 最终驱动源
- [x] 3.3 实现 `direction="output"` 路径：从模块输出端口 → 穿透父模块例化 → 追踪到最终负载
- [x] 3.4 实现例化边界端口映射（形式端口 ↔ 实际信号），支持位置端口和命名端口
- [x] 3.5 重构 `tools/level3_analysis.py` 的 `rtl_port_dataflow`，调用新的 `trace_port_dataflow` 替代简化的 fan-in 模式
- [x] 3.6 为端口数据流追踪编写单元测试（含多级穿透、位置端口、命名端口场景）

## 4. FSM 检测增强

- [x] 4.1 在 `analysis/fsm_detector.py` 中新增 `FSMDetector._detect_fsm_by_register()` 方法
- [x] 4.2 实现时序 always 块中非复位赋值寄存器提取（状态寄存器候选）
- [x] 4.3 实现组合逻辑块中寄存器读取检测与分支行为分析
- [x] 4.4 实现状态寄存器过滤：排除计数器、移位寄存器等非 FSM 模式
- [x] 4.5 修改 `FSMDetector.detect()`，合并 case+next_state 检测和寄存器检测的结果，去重
- [x] 4.6 为无 case 的 if-else FSM 和 one-hot FSM 编写单元测试
- [x] 4.7 验证原有 case 模式 FSM 测试仍通过，无回归

## 5. CDC 检测精度改进

- [x] 5.1 在 `analysis/clock_analyzer.py` 中新增 `ClockAnalyzer._detect_synchronizer(module_def, signal_name)` 方法
- [x] 5.2 实现双触发器同步器识别：连续两级同目标时钟的时序 always 块采样
- [x] 5.3 实现握手同步器识别：跨时钟域请求-应答信号对的锁存/采样回路检测
- [x] 5.4 修改 `rtl_cross_domain_signals` 工具输出，为每个信号标注风险等级和同步器类型
- [x] 5.5 为双触发器同步器和握手同步器场景编写单元测试
- [x] 5.6 验证原有 CDC 测试仍通过，无回归

## 6. 全量验证

- [x] 6.1 运行完整测试套件：`pytest tests/ -v`，确保 100% 通过
- [x] 6.2 运行类型检查（如有）：`mypy verilog_mcp_server/`
- [x] 6.3 验证 README 中工具列表与实际代码一致
- [x] 6.4 验证 `indexer/__init__.py` 导出列表无无效引用
