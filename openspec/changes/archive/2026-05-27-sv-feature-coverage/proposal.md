## Why

当前索引层仅覆盖 Verilog/SystemVerilog 基础语法子集。`generate` 块中的例化和信号声明完全丢失（影响含大量 `for-generate` 的设计如 crossbar/寄存器堆），`interface` 端口被跳过（复杂 SoC 设计的核心连接机制），`parameter` 值未被提取（无法回答"此例化中 WIDTH 是多少位"），位置端口连接不被支持。同时 `struct`/`enum`/`typedef` 等 SystemVerilog 高级类型被忽略，影响 FSM 检测和类型分析。上一轮（`analysis-engine-precision`）已修复分析引擎精度，本轮聚焦索引层 SV 特性覆盖。

## What Changes

- **新增** generate 块遍历：在 `instance_extractor.py` 和 `signal_extractor.py` 中递归遍历 `generate_construct` / `loop_generate_construct`，提取内部例化和信号声明
- **新增** interface 端口识别：在 `port_extractor.py` 中识别 `ansi_port_declaration` 内的 `interface_port` 节点，记录 interface 类型名
- **新增** parameter 值提取：在 `module_extractor.py` 或独立 extractor 中提取 `parameter_declaration` 的 name/type/default value
- **新增** 位置端口连接支持：在 `instance_extractor.py` 中按位置序号将 unnamed port connections 映射到子模块的形式端口名
- **新增** struct/enum/typedef 提取：新增 `indexer/type_extractor.py`，从 `data_declaration` / `typedef_declaration` 中提取用户自定义类型
- **新增** `database/models.py` 中 `TypeDef` 和 `ParamDef` 数据模型完善（ParamDef 已有但未被填充）

## Capabilities

### New Capabilities
- `generate-block-expansion`: 索引阶段遍历 generate/for-generate/if-generate 块，提取内部的所有例化和信号声明
- `interface-port-recognition`: 端口提取器识别 interface 端口（含 modport），记录 interface 类型名
- `parameter-extraction`: 提取模块 parameter/localparam 的 name、type、default value
- `positional-port-connections`: 支持位置端口连接（`u_mod(a, b, c)` 风格），按位置匹配子模块形式端口名
- `sv-type-extraction`: 提取 struct/enum/typedef 定义，为 FSM 检测和类型分析提供数据

### Modified Capabilities
<!-- None — all changes are new capabilities -->

## Impact

- Affected code:
  - `indexer/instance_extractor.py` — generate 块遍历、位置端口连接
  - `indexer/signal_extractor.py` — generate 块内信号声明提取
  - `indexer/port_extractor.py` — interface 端口识别
  - `indexer/module_extractor.py` — parameter 声明提取
  - `indexer/type_extractor.py` — 新文件，struct/enum/typedef 提取
  - `database/models.py` — 新增 `TypeDef` 数据类
  - `database/index_store.py` — 新增 type/path 索引
  - `analysis/fsm_detector.py` — 可感知 enum 状态定义（收益）
- No breaking changes to MCP tool interfaces
- Existing tests will need additions for new extraction capabilities
