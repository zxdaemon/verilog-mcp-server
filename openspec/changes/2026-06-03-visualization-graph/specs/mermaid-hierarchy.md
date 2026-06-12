## ADDED Requirements

### Requirement: HierarchyBuilder 提供 Mermaid 格式输出

`analysis/hierarchy.py` 的 `HierarchyBuilder` 类 SHALL 提供 `format_mermaid(top_module, max_depth) -> str` 方法，输出 Mermaid flowchart 语法的模块层次图。

Mermaid 输出 SHALL 以 `flowchart TD` 开头，包含：
- 每个模块实例为一个节点，标签格式为 `instance_name: module_name`
- 父子例化关系为有向边（`-->`）
- 循环引用为虚线边（`-.->`）并标注 `cycle`
- 根节点特殊样式（`:::root` classDef）

#### Scenario: 基本层次树 Mermaid 输出

- **WHEN** 调用 `format_mermaid("top", max_depth=5)`，其中 top 例化了 cpu 和 uart
- **THEN** 返回以 `flowchart TD` 开头的字符串
- **AND** 包含 `top`、`cpu`、`uart` 相关节点
- **AND** 包含 `top` 到 `cpu`、`top` 到 `uart` 的有向边

#### Scenario: 循环引用标记

- **WHEN** 模块 A 例化模块 B，模块 B 例化模块 A（循环）
- **THEN** 循环引用的边使用 `-.->` 虚线语法
- **AND** 边标签包含 `cycle`

#### Scenario: 名称特殊字符转义

- **WHEN** 模块名包含 `[`、`]`、`(`、`)` 等 Mermaid 语法字符
- **THEN** 节点 ID 中的特殊字符被替换为 `_`
- **AND** 节点标签用 `["..."]` 包裹，保留原始名称

#### Scenario: 节点数量上限

- **WHEN** 层次树节点数超过 200
- **THEN** 截断输出并在末尾添加警告注释
