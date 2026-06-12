## ADDED Requirements

### Requirement: 输入端口跨层级 fan-in 追踪
`DataflowTracer.trace_port_dataflow()` SHALL 支持 `direction="input"` 模式：从模块输入端口出发，穿透子模块例化边界，追踪信号到最终驱动源（顶层输入或组合逻辑输出）。

#### Scenario: 输入端口穿透子模块例化
- **WHEN** 模块 `A` 有输入端口 `din`，`A` 内部例化 `B` 并将 `din` 连接到 `B.din_b`，`B` 内部 `din_b` 驱动寄存器 `reg_b`
- **THEN** `trace_port_dataflow("A", "din", "input")` 返回路径 `A.din → B.din_b → B.reg_b`

#### Scenario: 多层级穿透
- **WHEN** 三级模块链 `Top → Mid → Leaf`，`Top.in` 穿透到 `Mid.in_m` 再穿透到 `Leaf.in_l`
- **THEN** 追踪深度 max_depth=3 时返回完整路径，max_depth=2 时在 `Mid.in_m` 处停止

### Requirement: 输出端口跨层级 fan-out 追踪
`DataflowTracer.trace_port_dataflow()` SHALL 支持 `direction="output"` 模式：从模块输出端口出发，穿透父模块例化边界，追踪信号到最终负载（顶层输出或其他模块输入端口）。

#### Scenario: 输出端口穿透父模块例化
- **WHEN** 模块 `B` 有输出端口 `dout_b`，`A` 例化 `B` 并将 `B.dout_b` 连接到 `A.dout` 和内部信号 `internal`
- **THEN** `trace_port_dataflow("B", "dout_b", "output")` 返回路径 `B.dout_b → A.dout` 和 `B.dout_b → A.internal`

### Requirement: 端口穿透的例化边界映射
追踪过程中 SHALL 正确处理例化边界的端口映射：形式端口名 ↔ 实际信号名的双向转换。

#### Scenario: 位置端口连接映射
- **WHEN** 模块例化使用位置端口连接 `B u_b(din, dout);`
- **THEN** 追踪器正确将位置索引映射到形式端口名 `din_b` / `dout_b`

#### Scenario: 命名端口连接映射
- **WHEN** 模块例化使用命名端口连接 `B u_b(.din_b(din_a), .dout_b(dout_a));`
- **THEN** 追踪器正确解析 `.formal(actual)` 映射关系

### Requirement: rtl_port_dataflow 工具输出完整追踪结果
`tools/level3_analysis.py` 中的 `rtl_port_dataflow` SHALL 调用 `trace_port_dataflow` 并返回包含完整路径、穿透深度、模块边界信息的结构化结果，不再使用简化的 fan-in 模式替代。

#### Scenario: 完整端口数据流报告
- **WHEN** 调用 `rtl_port_dataflow(module="Top", port="data_in", direction="input")`
- **THEN** 返回包含 `paths`（路径列表）、`depth`（最大深度）、`crosses_module_boundaries`（是否跨模块）、`terminal_nodes`（终端节点列表）的结果
