## ADDED Requirements

### Requirement: 识别门级原语例化

`indexer/instance_extractor.py` SHALL 识别 `gate_instantiation` 节点中的门级原语例化。

#### Scenario: 命名门级原语

- **WHEN** 源文件包含 `and a1 (out, in1, in2);`
- **THEN** 提取 `InstanceDef(name="a1", module_name="and", is_primitive=True, port_connections=[...])`

#### Scenario: 无名门级原语

- **WHEN** 源文件包含 `or (out, a, b);`
- **THEN** 提取 `InstanceDef(name="<anonymous_N>", module_name="or", is_primitive=True)`

#### Scenario: 带位宽的门级原语

- **WHEN** 源文件包含 `buf b1 [3:0] (out, in);`
- **THEN** 提取例化并记录位宽 `[3:0]`

### Requirement: 门级原语端口连接

`indexer/instance_extractor.py` SHALL 提取门级原语的位置端口连接。

#### Scenario: 门级原语端口顺序

- **WHEN** `and a1 (out, in1, in2)` — 第一个端口为输出，其余为输入
- **THEN** 端口连接按位置提取，方向由原语类型决定

### Requirement: 支持的门级原语列表

`indexer/instance_extractor.py` SHALL 支持以下门级原语：
- `and`, `or`, `not`, `buf`
- `nand`, `nor`, `xor`, `xnor`
- `bufif0`, `bufif1`, `notif0`, `notif1`

#### Scenario: nand 原语

- **WHEN** 源文件包含 `nand n1 (out, a, b, c);`
- **THEN** 正确识别为门级原语例化
