## ADDED Requirements

### Requirement: interface 端口识别
`indexer/port_extractor.py` 的 `_extract_ansi_port()` SHALL 识别 `ansi_port_declaration` 中的 `interface_port` 子节点，提取 interface 类型名和可选的 modport 名，存入 `PortDef.description` 字段。

#### Scenario: 简单 interface 端口
- **WHEN** 源文件包含 `module consumer (axis_if rx);` 且 `axis_if` 是已定义 interface
- **THEN** 生成 `PortDef(name="rx", direction="inout", description="interface:axis_if")`

#### Scenario: 带 modport 的 interface 端口
- **WHEN** 源文件包含 `module consumer (axis_if.slave rx);`
- **THEN** 生成 `PortDef(name="rx", direction="inout", description="interface:axis_if.slave")`

### Requirement: interface 端口不影响传统端口提取
interface 端口识别 SHALL 不影响现有 wire/reg/logic 端口的提取逻辑。传统端口和 interface 端口可以共存于同一模块。

#### Scenario: 混合端口
- **WHEN** 源文件包含 `module m (input clk, axis_if.slave rx);`
- **THEN** 系统正确提取 `clk`（传统 input 端口）和 `rx`（interface 端口），两者均在端口列表中
