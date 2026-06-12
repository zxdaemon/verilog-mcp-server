## ADDED Requirements

### Requirement: TLM 端口类型识别
`UvmTlmAnalyzer` SHALL 从 class 成员变量声明中识别 TLM 端口类型。支持的端口类型包括：`uvm_blocking_put_port`、`uvm_nonblocking_get_port`、`uvm_analysis_port`、`uvm_blocking_put_export`、`uvm_nonblocking_get_export`、`uvm_analysis_export`、`uvm_analysis_imp`。

#### Scenario: 识别 analysis_port
- **WHEN** class 内声明 `uvm_analysis_port #(my_item) ap;`
- **THEN** 识别端口名 `ap`，类型 `uvm_analysis_port`，泛型参数 `my_item`

#### Scenario: 识别 put_port 和 get_port
- **WHEN** class 内声明 `uvm_blocking_put_port #(req) put_port; uvm_nonblocking_get_port #(rsp) get_port;`
- **THEN** 分别识别端口类型和泛型参数

### Requirement: TLM connect 调用识别
`UvmTlmAnalyzer` SHALL 扫描 `method_call` 节点，识别 `.connect(target)` 调用模式。提取：源端口名（连接发起方）、目标端口名（连接接收方）、连接所在的 class 上下文。

#### Scenario: 简单 connect 调用
- **WHEN** 源码中有 `drv.put_port.connect(seqr.get_export);`
- **THEN** 识别连接 `drv.put_port → seqr.get_export`

#### Scenario: 跨组件 connect
- **WHEN** 源码中有 `monitor.ap.connect(scoreboard.analysis_export);`
- **THEN** 识别连接 `monitor.ap → scoreboard.analysis_export`

### Requirement: TLM 连接图构建
`UvmTlmAnalyzer` SHALL 基于端口声明和 connect 调用，构建 TLM 连接图。图中节点为（组件实例路径 + 端口名），边为 connect 关系，含方向（port→export→imp）。

#### Scenario: Agent 内 TLM 连接
- **WHEN** agent 内 `sequencer.seq_item_port.connect(driver.seq_item_export)` 和 `monitor.ap.connect(scoreboard.analysis_export)`
- **THEN** 构建两条连接边，分别标注端口类型和方向

### Requirement: TLM 连接 MCP 工具
`rtl_uvm_tlm_connections` MCP 工具 SHALL 接受 `component_path` 参数（可选），返回指定组件及其子组件的 TLM 连接图。若未指定，返回整个环境的 TLM 连接。

#### Scenario: 查询 agent 内 TLM 连接
- **WHEN** 调用 `rtl_uvm_tlm_connections(component_path="env.my_agent")`
- **THEN** 返回该 agent 内所有 TLM 端口声明和 connect 关系

#### Scenario: 查询全局 TLM 连接
- **WHEN** 调用 `rtl_uvm_tlm_connections()`
- **THEN** 返回整个 UVM 环境的所有 TLM 连接
