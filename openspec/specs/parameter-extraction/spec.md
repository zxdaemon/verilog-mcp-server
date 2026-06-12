## ADDED Requirements

### Requirement: parameter 声明提取
`indexer/module_extractor.py` SHALL 在提取模块时，从 `module_ansi_header` 或 `module_nonansi_header` 中查找 `parameter_port_list` 节点，解析其中的 `parameter_declaration` 子节点，提取 parameter 名、类型和默认值，存入 `ModuleDef.parameters` 列表（`ParamDef` 类型）。

#### Scenario: 含默认值的 parameter
- **WHEN** 源文件包含 `module fifo #(parameter WIDTH=32, parameter DEPTH=8) (...);`
- **THEN** 系统提取 `[ParamDef(name="WIDTH", type="parameter", default_value="32"), ParamDef(name="DEPTH", type="parameter", default_value="8")]`

#### Scenario: 无默认值的 parameter
- **WHEN** 源文件包含 `module m #(parameter WIDTH) (...);`
- **THEN** 系统提取 `ParamDef(name="WIDTH", type="parameter", default_value=None)`

#### Scenario: localparam 提取
- **WHEN** 源文件在模块体包含 `localparam OFFSET = 8'h10;`
- **THEN** 系统提取 `ParamDef(name="OFFSET", type="localparam", default_value="8'h10")`

### Requirement: parameter 值以文本形式存储
parameter 默认值 SHALL 以源码文本形式存储，不做常量求值或传播。

#### Scenario: 复杂表达式默认值
- **WHEN** 源文件包含 `parameter ADDR_W = $clog2(DEPTH);`
- **THEN** 系统存储 `default_value="$clog2(DEPTH)"` 作为原始文本
