## ADDED Requirements

### Requirement: ElaboratedInstanceDef 数据模型
`ElaboratedInstanceDef` dataclass SHALL 包含字段：`hierarchical_path`（展开后完整路径，如 `top.genblk[0].u_cpu`）、`module_type`（原始模块名）、`parent_path`（父实例路径）、`parameter_values`（`dict[str, str]`，实例特定的参数求值后值）、`generate_condition`（如有，原始条件表达式）、`is_generated`（`bool`）。支持 `to_dict()`/`from_dict()` 序列化。

#### Scenario: ElaboratedInstanceDef 序列化
- **WHEN** 创建 `ElaboratedInstanceDef(hierarchical_path="top.genblk[0].u_cpu", module_type="cpu", parameter_values={"WIDTH": "64"})` 并调用 `to_dict()`
- **THEN** 返回的字典包含所有字段

### Requirement: ResolvedSignalDef 数据模型
`ResolvedSignalDef` dataclass SHALL 包含字段：`name`、`module_name`、`original_width`（tree-sitter 提取的原始文本，如 `"[WIDTH-1:0]"`）、`resolved_width`（pyslang 求值后的文本，如 `"[31:0]"`）、`signal_type`（`wire`/`reg`/`logic` 等）、`elaborated_path`（信号在层次树中的完整路径）。支持 `to_dict()`/`from_dict()` 序列化。

#### Scenario: ResolvedSignalDef 序列化
- **WHEN** 创建 `ResolvedSignalDef(name="data", original_width="[WIDTH-1:0]", resolved_width="[31:0]")` 并调用 `to_dict()`
- **THEN** 返回的字典包含原始位宽和求值后位宽

### Requirement: MacroExpansionInfo 数据模型
`MacroExpansionInfo` dataclass SHALL 包含字段：`macro_name`、`definition_file`、`definition_line`、`expansion_sites`（`list[dict]`，含文件路径、行号、展开后文本）。支持 `to_dict()`/`from_dict()` 序列化。

#### Scenario: MacroExpansionInfo 序列化
- **WHEN** 创建 `MacroExpansionInfo(macro_name="ADD", expansion_sites=[{...}])` 并调用 `to_dict()`
- **THEN** 返回的字典包含所有展开位置

### Requirement: ElaborationReport 数据模型
`ElaborationReport` dataclass SHALL 包含项目的 elaboration 全局信息：`timestamp`、`pyslang_version`、`total_modules`（tree-sitter 计数）、`elaborated_modules`（pyslang 计数）、`generate_blocks`、`elaborated_instances`、`parameterized_modules`、`macro_definitions`、`diagnostics`（pyslang 错误/警告列表）。支持 `to_dict()`/`from_dict()` 序列化。

#### Scenario: ElaborationReport 生成
- **WHEN** pyslang elaboration 完成后
- **THEN** 生成 `ElaborationReport`，含 tree-sitter 和 pyslang 的模块数量对比
