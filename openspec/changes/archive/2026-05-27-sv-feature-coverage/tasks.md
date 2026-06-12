## 1. Generate 块展开

- [x] 1.1 在 `instance_extractor.py` 的 `extract_from_module_body()` 中递归遍历 `generate_construct`、`loop_generate_construct`、`if_generate_construct`、`case_generate_construct` 子节点
- [x] 1.2 从 generate 块内部提取 `module_instantiation` 节点，生成 `InstanceDef` 记录
- [x] 1.3 在 `signal_extractor.py` 的 `extract_signals()` 中递归遍历 generate 块，提取 `net_declaration` 和 `data_declaration`
- [x] 1.4 在 `signal_extractor.py` 的 `extract_assignments()` 中递归遍历 generate 块，提取 `continuous_assign`
- [x] 1.5 在 `signal_extractor.py` 的 `extract_always_blocks()` 和 `extract_drivers_and_loads()` 中递归遍历 generate 块

## 2. Interface 端口识别

- [x] 2.1 在 `port_extractor.py` 的 `_extract_ansi_port()` 中新增对 `interface_port` 子节点的识别
- [x] 2.2 提取 interface 类型名和可选的 modport 名，存入 `PortDef.description`（格式 `"interface:<type>"` 或 `"interface:<type>.<modport>"`）
- [x] 2.3 确保 interface 端口不影响现有 wire/reg/logic 端口提取逻辑

## 3. Parameter 提取

- [x] 3.1 在 `module_extractor.py` 中新增 `_extract_parameters(module_node, source_text) -> list[ParamDef]` 方法
- [x] 3.2 从 `module_ansi_header` 的 `parameter_port_list` 中解析 parameter 名、类型、默认值
- [x] 3.3 从 module body 中提取 `parameter_declaration` 和 `localparam_declaration` 节点
- [x] 3.4 在 `IndexBuilder.build()` 中集成：提取模块后填充 `mod.parameters`
- [x] 3.5 参数值以文本形式存储，不做常量求值

## 4. 位置端口连接

- [x] 4.1 在 `instance_extractor.py` 的 `_extract_hierarchical_instance()` 中新增对位置端口连接的处理
- [x] 4.2 对每个 unnamed expression 按位置序号匹配子模块端口（从 IndexStore 查找子模块的端口声明顺序）
- [x] 4.3 子模块未索引时使用占位名 `__pos_N`
- [x] 4.4 支持命名连接与位置连接的混合使用

## 5. 类型提取

- [x] 5.1 在 `database/models.py` 中新增 `TypeDef` dataclass（name, kind, members, source_text, file_path, line）
- [x] 5.2 创建 `indexer/type_extractor.py`，实现 `extract_types(module_body_node, source_text, file_path) -> list[TypeDef]`
- [x] 5.3 提取 `typedef_declaration` + `enum_declaration` → `TypeDef(kind="enum")`
- [x] 5.4 提取 `typedef_declaration` + `struct_declaration` → `TypeDef(kind="struct")`
- [x] 5.5 提取不带 typedef 的 `enum_declaration` 和 `struct_declaration`
- [x] 5.6 在 `database/index_store.py` 中新增 `add_type()`、`get_type()`、`get_all_types()` 方法和类型索引
- [x] 5.7 在 `IndexBuilder.build()` 中集成：提取类型并添加到 index_store

## 6. 测试与验证

- [x] 6.1 为 generate 块提取编写测试：for-generate 内例化、if-generate 内例化、generate 内信号
- [x] 6.2 为 interface 端口提取编写测试：简单 interface、带 modport、混合传统端口
- [x] 6.3 为 parameter 提取编写测试：有默认值、无默认值、localparam
- [x] 6.4 为位置端口连接编写测试：全位置、子模块未索引、混合连接
- [x] 6.5 为类型提取编写测试：typedef enum、typedef struct、enum 定义
- [x] 6.6 运行全量测试套件确认无回归：`uv run pytest tests/ -v`
