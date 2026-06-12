## ADDED Requirements

### Requirement: 提取 package 声明

`indexer/package_extractor.py` SHALL 从 `package_declaration` 节点中提取 package 名称和位置信息。

#### Scenario: 标准 package 声明

- **WHEN** 源文件包含 `package my_pkg; ... endpackage`
- **THEN** 提取 `PackageDef(name="my_pkg", file_path=..., line=...)` 并存入 IndexStore

#### Scenario: 带参数的 package

- **WHEN** 源文件包含 `package my_pkg #(parameter WIDTH = 8); ... endpackage`
- **THEN** 提取 package 的 parameter 列表，存入 `PackageDef.params`

### Requirement: 提取 import 语句

`indexer/package_extractor.py` SHALL 从 `package_import_declaration` 节点中提取 import 信息。

#### Scenario: 单项导入

- **WHEN** 源文件包含 `import my_pkg::DATA_WIDTH;`
- **THEN** 提取 `ImportDef(module_name=当前模块, package_name="my_pkg", items=["DATA_WIDTH"])`

#### Scenario: 通配符导入

- **WHEN** 源文件包含 `import my_pkg::*;`
- **THEN** 提取 `ImportDef(module_name=当前模块, package_name="my_pkg", items=["*"])`

### Requirement: 提取 package 内部声明

`indexer/package_extractor.py` SHALL 提取 package 内部的 typedef、parameter、function。

#### Scenario: package 包含 typedef

- **WHEN** package 内包含 `typedef enum logic [1:0] {S0, S1} state_t;`
- **THEN** 提取 `TypeDef` 并关联到 `PackageDef.typedefs`

### Requirement: Package 索引查询

`database/index_store.py` SHALL 提供 package 查询方法。

#### Scenario: 按名称查询 package

- **WHEN** 调用 `index_store.get_package("my_pkg")`
- **THEN** 返回对应的 `PackageDef` 对象

#### Scenario: 按模块查询其 imports

- **WHEN** 调用 `index_store.get_imports("my_module")`
- **THEN** 返回该模块的所有 `ImportDef` 列表
