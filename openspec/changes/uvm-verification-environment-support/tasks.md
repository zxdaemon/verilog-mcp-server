## 1. 数据模型与 SQLite 扩展

- [ ] 1.1 在 `database/models.py` 中新增 `ClassDef` dataclass（含 name, extends, type_params, members, methods, is_uvm_component, uvm_base_class 字段）
- [ ] 1.2 在 `database/models.py` 中新增 `MethodDef` dataclass（含 name, method_type, return_type, parameters, modifiers, is_uvm_phase, uvm_phase_name, parent_class, parent_package 字段）
- [ ] 1.3 在 `database/models.py` 中新增 `UvmComponentDef` dataclass（含 type, instance_name, parent_id, children_ids, file_path, line 字段）
- [ ] 1.4 在 `database/models.py` 中新增 `UvmTlmPortDef` 和 `UvmConfigEntry` dataclass
- [ ] 1.5 在 `database/sqlite_backend.py` 的 `_SCHEMA_SQL` 中新增 `classes`、`methods`、`uvm_components`、`uvm_tlm_ports`、`uvm_config_entries` 五张表
- [ ] 1.6 在 `database/sqlite_backend.py` 中新增 `save_class`、`get_class`、`get_classes_by_file` 方法
- [ ] 1.7 在 `database/sqlite_backend.py` 中新增 `save_method`、`get_methods_by_class`、`get_methods_by_package` 方法
- [ ] 1.8 在 `database/sqlite_backend.py` 中新增 `save_uvm_component`、`get_uvm_hierarchy` 方法
- [ ] 1.9 在 `database/index_store.py` 中新增 class/method/uvm 的内存缓存和查询接口（`get_class`、`search_classes`、`get_methods_by_class`、`get_uvm_hierarchy`）
- [ ] 1.10 为新增数据模型编写序列化/反序列化单元测试

## 2. Class 提取器

- [ ] 2.1 新建 `indexer/class_extractor.py`，实现 `ClassExtractor` 类
- [ ] 2.2 实现从 `source_file` AST 遍历 `class_declaration` 节点的提取逻辑
- [ ] 2.3 实现 extends 继承链解析（含参数化类型提取）
- [ ] 2.4 实现 class 成员变量提取（data_declaration 节点，含类型、位宽、rand/local/protected 修饰符）
- [ ] 2.5 实现 UVM 组件识别（匹配 `uvm_component` / `uvm_env` / `uvm_agent` / `uvm_driver` / `uvm_monitor` / `uvm_sequencer` / `uvm_scoreboard` / `uvm_test` 基类）
- [ ] 2.6 实现多层继承基类推导（构建 class 继承映射表，二次遍历推导 `uvm_base_class`）
- [ ] 2.7 为 ClassExtractor 编写单元测试（简单 class、继承 class、参数化 class、UVM 组件识别）

## 3. Function/Task 提取器

- [ ] 3.1 新建 `indexer/function_extractor.py`，实现 `FunctionExtractor` 类
- [ ] 3.2 实现从 `class_declaration` 节点提取 `function_declaration` 和 `task_declaration`
- [ ] 3.3 实现方法名、返回类型、参数列表、修饰符（virtual/pure virtual/static/automatic）提取
- [ ] 3.4 实现 UVM phase 方法识别（build_phase、connect_phase、run_phase 等）
- [ ] 3.5 实现从 `package_declaration` 节点提取 function/task（记录所属 package）
- [ ] 3.6 为 FunctionExtractor 编写单元测试（function、task、virtual task、pure virtual function、phase 方法）

## 4. UVM 组件层次提取器

- [ ] 4.1 新建 `indexer/uvm_extractor.py`，实现 `UvmExtractor` 类
- [ ] 4.2 实现 `type_id::create(...)` 调用模式识别（提取组件类型、实例名、父组件引用）
- [ ] 4.3 实现 `new(...)` 调用模式识别（作为 create 的 fallback）
- [ ] 4.4 实现父组件引用解析（`this`、简单成员变量、复杂表达式标记为 unknown）
- [ ] 4.5 新建 `analysis/uvm_hierarchy.py`，实现 `UvmHierarchyBuilder` 类
- [ ] 4.6 实现基于 UvmExtractor 结果和 ClassExtractor 继承信息构建组件树
- [ ] 4.7 实现 `uvm_test` 子类作为根节点的识别
- [ ] 4.8 为 UVM 组件层次构建编写单元测试（单 test、多 agent、多层继承）

## 5. UVM TLM 连接分析器

- [ ] 5.1 新建 `analysis/uvm_tlm.py`，实现 `UvmTlmAnalyzer` 类
- [ ] 5.2 实现 TLM 端口类型识别（analysis_port、blocking_put_port、nonblocking_get_port、export、imp 等）
- [ ] 5.3 实现 `.connect(target)` 调用模式识别
- [ ] 5.4 实现 TLM 连接图构建（节点 = 组件路径 + 端口名，边 = connect 关系）
- [ ] 5.5 为 TLM 连接分析编写单元测试（analysis_port connect、put_port connect、多组件连接）

## 6. UVM Config DB 追踪器

- [ ] 6.1 新建 `analysis/uvm_config_db.py`，实现 `UvmConfigDbTracer` 类
- [ ] 6.2 实现 `uvm_config_db#(type)::set(scope, field_name, value)` 调用识别
- [ ] 6.3 实现 `uvm_config_db#(type)::get(scope, field_name, variable)` 调用识别
- [ ] 6.4 实现 config_db 传播路径追踪（set → get 映射）
- [ ] 6.5 实现未匹配检测（有 set 无 get、有 get 无 set）
- [ ] 6.6 为 Config DB 追踪编写单元测试（标准 set/get、跨层级传播、未匹配检测）

## 7. 索引集成与项目扫描

- [ ] 7.1 修改 `indexer/builder.py`，在索引构建流程中调用 `ClassExtractor`、`FunctionExtractor`、`UvmExtractor`
- [ ] 7.2 修改 `indexer/project_scanner.py`，确保 UVM 验证文件不被默认排除规则排除
- [ ] 7.3 修改 `indexer/__init__.py`，导出新的提取器类
- [ ] 7.4 验证增量更新（`rtl_update_index`）对 class/method 变更文件的正确处理

## 8. UVM MCP 工具

- [ ] 8.1 新建 `tools/uvm_tools.py`，实现 `rtl_uvm_hierarchy` 工具
- [ ] 8.2 实现 `rtl_uvm_hierarchy` 支持 JSON 和 Mermaid 双输出格式
- [ ] 8.3 实现 `rtl_uvm_tlm_connections` 工具
- [ ] 8.4 实现 `rtl_uvm_config_trace` 工具
- [ ] 8.5 实现 `rtl_uvm_component_detail` 工具
- [ ] 8.6 修改 `tools/__init__.py`，导出 UVM 工具注册函数
- [ ] 8.7 修改 `server.py`，注册 UVM MCP 工具
- [ ] 8.8 为 4 个 UVM MCP 工具编写单元测试

## 9. 全量验证

- [ ] 9.1 运行完整测试套件：`pytest tests/ -v`，确保 100% 通过（含新增 UVM 测试）
- [ ] 9.2 验证现有 RTL 测试无回归（module/interface/package 提取不受影响）
- [ ] 9.3 验证索引增量更新对 UVM 文件正常工作
- [ ] 9.4 验证 README 已更新，包含 UVM 工具说明
