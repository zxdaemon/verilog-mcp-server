## ADDED Requirements

### Requirement: 提取 SVA property 声明

`indexer/sva_extractor.py` SHALL 从 `property_declaration` 节点中提取属性定义。

#### Scenario: 带时钟的 property

- **WHEN** 源文件包含 `property p_req_ack; @(posedge clk) req |-> ##1 ack; endproperty`
- **THEN** 提取 `SVAPropertyDef(name="p_req_ack", clocking="@(posedge clk)", body="req |-> ##1 ack")`

#### Scenario: 带 disable iff 的 property

- **WHEN** property 包含 `disable iff (!rst_n)`
- **THEN** 提取 `disable_iff="!rst_n"`

### Requirement: 提取 SVA sequence 声明

`indexer/sva_extractor.py` SHALL 从 `sequence_declaration` 节点中提取序列定义。

#### Scenario: 基本 sequence

- **WHEN** 源文件包含 `sequence s_req; req ##1 gnt; endsequence`
- **THEN** 提取 `SVASquenceDef(name="s_req", body="req ##1 gnt")`

### Requirement: 提取 assert/assume/cover 语句

`indexer/sva_extractor.py` SHALL 从 `concurrent_assertion_item` 节点中提取断言语句。

#### Scenario: 带标签的 assert property

- **WHEN** 源文件包含 `a_req_ack: assert property(p_req_ack);`
- **THEN** 提取 `SVAAssertDef(label="a_req_ack", property_name="p_req_ack", kind="assert")`

#### Scenario: cover property

- **WHEN** 源文件包含 `cover property(p_req_ack);`
- **THEN** 提取 `SVAAssertDef(kind="cover", property_name="p_req_ack")`

### Requirement: SVA 索引查询

`database/index_store.py` SHALL 提供 SVA 相关查询方法。

#### Scenario: 查询模块的 SVA 属性

- **WHEN** 调用 `index_store.get_sva_properties("my_module")`
- **THEN** 返回该模块的所有 `SVAPropertyDef` 列表

#### Scenario: 查询模块的断言

- **WHEN** 调用 `index_store.get_sva_assertions("my_module")`
- **THEN** 返回该模块的所有 `SVAAssertDef` 列表
