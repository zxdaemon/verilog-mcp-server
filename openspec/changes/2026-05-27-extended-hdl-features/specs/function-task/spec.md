## ADDED Requirements

### Requirement: 提取 function 声明

`indexer/function_task_extractor.py` SHALL 从 `function_declaration` 节点中提取函数定义。

#### Scenario: 带返回类型的 function

- **WHEN** 源文件包含 `function automatic logic [7:0] calc(input logic [7:0] a, b);`
- **THEN** 提取 `FunctionDef(name="calc", kind="function", return_type="logic [7:0]", ports=[...])`

#### Scenario: void function

- **WHEN** 源文件包含 `function void reset();`
- **THEN** 提取 `FunctionDef(name="reset", kind="function", return_type="void")`

### Requirement: 提取 task 声明

`indexer/function_task_extractor.py` SHALL 从 `task_declaration` 节点中提取任务定义。

#### Scenario: 基本 task

- **WHEN** 源文件包含 `task automatic send(input logic [7:0] data, output logic ready);`
- **THEN** 提取 `FunctionDef(name="send", kind="task", ports=[...])`

### Requirement: 提取 function/task 端口

`indexer/function_task_extractor.py` SHALL 提取 function/task 的端口声明。

#### Scenario: 带方向的端口

- **WHEN** function 包含 `input logic [7:0] a, output logic [7:0] result`
- **THEN** 提取端口列表，每个端口包含方向、类型、名称

### Requirement: Function/Task 索引查询

`database/index_store.py` SHALL 提供 function/task 查询方法。

#### Scenario: 按名称查询 function

- **WHEN** 调用 `index_store.get_function("calc")`
- **THEN** 返回对应的 `FunctionDef` 对象

#### Scenario: 按模块查询 function 列表

- **WHEN** 调用 `index_store.get_functions_by_module("my_module")`
- **THEN** 返回该模块内的所有 `FunctionDef` 列表
