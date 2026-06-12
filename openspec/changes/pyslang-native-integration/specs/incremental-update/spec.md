## MODIFIED Requirements

### Requirement: 增量构建检测变更文件
`IndexBuilder.build_incremental()` SHALL 通过 mtime + SHA256 检测变更文件，仅重新解析变更文件。

#### Scenario: 无文件变更跳过构建
- **WHEN** 调用 `build_incremental()` 且无文件变更
- **THEN** 返回已有 `IndexStore`，不重新解析任何文件

#### Scenario: 变更文件重新解析
- **WHEN** `cpu.v` 修改后调用 `build_incremental()`
- **THEN** 仅重新解析 `cpu.v`，其他文件不受影响

## ADDED Requirements

### Requirement: pyslang elaboration 变更检测
`IndexBuilder` SHALL 检测变更文件是否涉及 elaboration 相关变更。如果变更涉及以下 AST 节点类型，触发 pyslang 重跑：
- `parameter_declaration` — 参数值变化影响所有实例
- `localparam_declaration` — 本地参数变化
- `generate_construct` / `generate_region` / `conditional_generate_construct` / `loop_generate_construct` — generate 结构变化
- `module_instantiation` — 模块例化增删
- `macro_definition` — 宏定义变化

#### Scenario: 参数变更触发 pyslang 重跑
- **WHEN** `cpu.v` 中 `parameter WIDTH = 32` 改为 `parameter WIDTH = 64`
- **THEN** tree-sitter 增量解析 `cpu.v`，同时触发 pyslang 对整个设计的 elaboration 重跑

#### Scenario: assign 变更不触发 pyslang 重跑
- **WHEN** `cpu.v` 中 `assign a = b + 1` 改为 `assign a = b + 2`
- **THEN** tree-sitter 增量解析 `cpu.v`，pyslang 不重跑（内部逻辑变更不影响 elaboration）

### Requirement: pyslang 增量 elaboration
当仅少量文件变更时，`PyslangParser` SHALL 尝试增量 elaboration：只重新 elaboration 变更文件及其依赖的模块。若 pyslang 不支持真正的增量 elaboration，则回退到全量 elaboration。

#### Scenario: 单文件变更的增量 elaboration
- **WHEN** 仅 `alu.v` 变更（不影响其他模块的参数和接口）
- **THEN** pyslang 只重新 elaboration `alu.v` 及其直接依赖

### Requirement: pyslang 缓存机制
`IndexBuilder` SHALL 缓存 pyslang `Compilation` 对象（序列化到 `.verilog_mcp/pyslang_cache/`）。当文件未变更时，从缓存恢复 `Compilation`，避免重新解析所有文件。

#### Scenario: pyslang 缓存命中
- **WHEN** 无文件变更时调用 `build_incremental()`
- **THEN** 从缓存恢复 pyslang `Compilation`，不重新解析任何文件
