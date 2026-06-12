## ADDED Requirements

### Requirement: 识别 defparam 语句

`indexer/instance_extractor.py` SHALL 识别模块体中的 `defparam` 语句并提取覆盖信息。

#### Scenario: 简单 defparam

- **WHEN** 源文件包含 `defparam inst.param_a = 8;`
- **THEN** 提取 `DefparamOverride(hierarchical_path="inst.param_a", value="8")`

#### Scenario: 多级路径 defparam

- **WHEN** 源文件包含 `defparam top.sub.inst.WIDTH = 16;`
- **THEN** 提取 `DefparamOverride(hierarchical_path="top.sub.inst.WIDTH", value="16")`

### Requirement: 合并 defparam 到例化参数

`indexer/instance_extractor.py` SHALL 在提取完例化后，将 defparam 覆盖值合并到对应 `InstanceDef.params`。

#### Scenario: defparam 覆盖模块默认参数

- **WHEN** 模块 `sub` 有 `parameter WIDTH = 8`，且存在 `defparam inst.WIDTH = 16`
- **THEN** `InstanceDef(name="inst", params={"WIDTH": "16"})` — defparam 值优先

#### Scenario: defparam 与例化参数列表共存

- **WHEN** 例化 `sub #(.WIDTH(4)) inst(...)` 且存在 `defparam inst.WIDTH = 16`
- **THEN** defparam 值（16）覆盖例化参数列表值（4）

### Requirement: Defparam 警告

`indexer/instance_extractor.py` SHALL 对无法解析的 defparam 生成警告。

#### Scenario: 跨模块 defparam 路径

- **WHEN** defparam 路径包含多级层次（`top.sub.param`）且当前模块无法解析
- **THEN** 记录 warning 日志，不执行覆盖
