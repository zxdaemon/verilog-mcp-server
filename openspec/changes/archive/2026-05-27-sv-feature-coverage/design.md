## Context

当前索引层覆盖了 Verilog/SystemVerilog 基础子集：module 声明、ANSI 端口、wire/reg/logic 声明、连续赋值、always 块、命名端口连接的例化。上一轮 `analysis-engine-precision` 已改进分析引擎精度和 always_comb/ff/latch 支持。本轮聚焦索引层对 SystemVerilog 关键特性的覆盖缺失。

## Goals / Non-Goals

**Goals:**
- generate/for-generate/if-generate 块内的例化和信号声明被正确索引
- interface 端口（含 modport）被识别并记录 interface 类型名
- parameter/localparam 的 name、type、default value 被提取
- 位置端口连接被按位置映射到子模块的形式端口名
- struct/enum/typedef 定义被提取为 `TypeDef` 记录

**Non-Goals:**
- generate 块形参求值（如 `genvar i` 的展开）—— 只做文本级别索引，不展开循环
- interface 内部信号的跨模块追踪
- parameter 常量传播/求值（属于后续 Phase）
- package/import 解析（属于后续 Phase）
- SVA 断言提取（属于后续 Phase）

## Decisions

### D1: generate 块 — 递归遍历，不展开循环

**选择：** 在 `instance_extractor.py` 和 `signal_extractor.py` 的 AST 遍历函数中，当遇到 `generate_construct`、`loop_generate_construct`、`if_generate_construct`、`case_generate_construct` 节点时，递归遍历其内部子节点，提取 `module_instantiation`、`net_declaration`、`data_declaration` 等。不尝试展开 `genvar` 循环，索引中记录的例化名是 generate block 的标签名（如 `gen_blk[0].u_ff` 在源码中不会出现，我们记录的是 block 标签 `gen_blk`）。

**替代方案：** 展开 genvar 循环 → 放弃。需要实现完整的编译期常量求值和循环展开，复杂度远超索引器范畴。

**为什么这是对的：** 至少能发现 generate 块*内部存在*例化和信号，而非完全丢失。块标签作为索引 key 足以支持层次树和时钟树构建。

### D2: interface 端口 — 记录 interface 类型名

**选择：** 在 `port_extractor.py` 的 `_extract_ansi_port` 中，当遇到 `interface_port` 或 `modport` 子节点时，提取 interface 类型名（如 `axis_if`）和 modport 名（如有），存入 `PortDef.description` 字段（格式为 `"interface:axis_if"` 或 `"interface:axis_if.slave"`）。

**替代方案：** 新增 `PortDef.interface_type` 字段 → 可行但侵入数据模型。`PortDef` 已序列化到缓存 JSON，新增字段需要迁移。

**为什么这是对的：** 不修改数据模型，`description` 字段原本就是为此类扩展信息预留的。下游工具可通过解析 description 获取 interface 信息。

### D3: 位置端口连接 — 按端口序号匹配

**选择：** 在 `instance_extractor.py` 中，对 `list_of_port_connections` 中 `positional_port_connection` (即 unnamed `expression` 节点) 类型的连接，查找子模块的形式端口列表（按声明顺序），将位置 `i` 的连接映射到子模块第 `i` 个端口名。

```
// u_mod 的类型是 my_mod，my_mod 端口依次为: clk, rst_n, din, dout
my_mod u_mod (clk, rst_n, data_in, data_out);
// → {"clk": "clk", "rst_n": "rst_n", "din": "data_in", "dout": "data_out"}
```

**限制：** 仅当子模块已在索引中时才工作。如果子模块未索引（外部 IP），位置连接无法映射端口名，存储为 `f"__pos_{i}"` 占位名。

**为什么这是对的：** 大多数设计中，顶层及关键子模块都会被索引到，覆盖率足够。外部 IP 的端口连接通常不参与深入分析。

### D4: parameter 提取 — 文本级存储

**选择：** `module_extractor.py` 在提取模块骨架时，从 `module_ansi_header` 或 `module_nonansi_header` 中查找 `parameter_port_list`（`#(parameter W=32, ...)`），解析 parameter 名、类型和默认值文本，存入 `ParamDef` 列表。`ParamDef` 模型已存在于 `database/models.py` 但从未被填充。

**限制：** 仅存储文本值，不做常量求值。如 `parameter DEPTH = 2**ADDR_W` 中 `ADDR_W` 不会被替换为实际值。

**为什么这是对的：** 文本存储足以支撑"此模块有哪些参数"的查询需求。常量传播属于后续分析层功能。

### D5: 类型提取 — 统一 TypeDef 模型

**选择：** 新增 `indexer/type_extractor.py`，遍历 `data_declaration` 和 `typedef_declaration` 节点，提取 struct/enum/typedef 定义。新增 `database/models.py` 中 `TypeDef` 数据类：

```python
@dataclass
class TypeDef(SerializableModel):
    name: str
    kind: str          # struct / enum / typedef / union
    members: list[str]  # struct 成员名 / enum 值名
    source_text: str    # 原始声明文本
    file_path: str
    line: int
```

**为什么这是对的：** `TypeDef` 是独立数据类，不影响现有模型。FSM 检测器可通过 enum 成员列表提升状态识别精度。

## Risks / Trade-offs

- **Risk:** generate 块递归遍历可能产生重复例化（同一模块在 generate 循环中例化多次，但索引中只记录一次块标签） → **Mitigation:** 通过 `instance_path` 维度区分（generate 块标签等价于一层层次），在层次树构建时以标签名作为子模块引用
- **Risk:** 位置端口连接按序号匹配依赖子模块端口顺序与索引一致，非标准端口顺序可能错位 → **Mitigation:** 记录警告日志，分析工具在读端口连接时检查信号名与声明是否可能有漂移
- **Trade-off:** 参数值不做常量传播，下游工具无法直接使用 `parameter W=32` 中的 `32` 做宽度计算 → 下一轮实现 `analysis/param_eval.py`
