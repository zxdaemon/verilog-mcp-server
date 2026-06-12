## ADDED Requirements

### Requirement: FunctionExtractor 提取 class 内 function/task
`FunctionExtractor` SHALL 从 `class_declaration` 节点中提取 `function_declaration` 和 `task_declaration`，返回 `MethodDef` 列表。每个 `MethodDef` 包含方法名、类型（`function`/`task`）、返回类型、参数列表、修饰符（`virtual`/`pure virtual`/`static`/`automatic`）。

#### Scenario: 提取 class 内 function
- **WHEN** class 体内声明 `function void drive_item(my_item item); ... endfunction`
- **THEN** 提取方法名 `drive_item`，类型 `function`，返回类型 `void`，参数列表包含 `my_item item`

#### Scenario: 提取 virtual task
- **WHEN** class 体内声明 `virtual task run_phase(uvm_phase phase); ... endtask`
- **THEN** 提取方法名 `run_phase`，类型 `task`，修饰符 `virtual`，参数 `uvm_phase phase`

#### Scenario: 提取 pure virtual function
- **WHEN** class 体内声明 `pure virtual function bit do_compare(uvm_object rhs, uvm_comparer comparer);`
- **THEN** 提取方法名 `do_compare`，类型 `function`，修饰符 `pure virtual`，返回类型 `bit`

### Requirement: 提取 package 内 function/task
`FunctionExtractor` SHALL 同时支持从 `package_declaration` 节点中提取 function/task 声明，记录所属 package 名。

#### Scenario: Package 内 function
- **WHEN** package `my_pkg` 内声明 `function int add(int a, int b); ... endfunction`
- **THEN** 提取方法名 `add`，所属 package `my_pkg`，返回类型 `int`

### Requirement: UVM phase 方法识别
`FunctionExtractor` SHALL 识别 UVM 标准 phase 方法名：`build_phase`、`connect_phase`、`end_of_elaboration_phase`、`start_of_simulation_phase`、`run_phase`、`report_phase`。识别结果记录在 `MethodDef.is_uvm_phase` 字段。

#### Scenario: UVM phase 方法标记
- **WHEN** 提取到方法 `build_phase(uvm_phase phase)`
- **THEN** `is_uvm_phase` 为 `True`，`uvm_phase_name` 为 `"build_phase"`

### Requirement: MethodDef 数据模型
`MethodDef` dataclass SHALL 包含字段：`name`、`method_type`（`function`/`task`）、`return_type`、`parameters`（`list[ParamDef]`）、`modifiers`（`list[str]`）、`is_uvm_phase`、`uvm_phase_name`、`parent_class`、`parent_package`。支持 `to_dict()`/`from_dict()` 序列化。

#### Scenario: MethodDef 完整字段
- **WHEN** 创建 `MethodDef(name="drive", method_type="task", return_type="void", ...)`
- **THEN** 所有字段正确序列化和反序列化
