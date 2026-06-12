## 1. 数据模型扩展

- [ ] 1.1 在 `database/models.py` 中新增 `PackageDef`、`ImportDef` 数据类
- [ ] 1.2 在 `database/models.py` 中新增 `SVAPropertyDef`、`SVASquenceDef`、`SVAAssertDef` 数据类
- [ ] 1.3 在 `database/models.py` 中新增 `FunctionDef`、`FunctionCallInfo` 数据类
- [ ] 1.4 在 `database/models.py` 中新增 `DefparamOverride`、`PrimitiveDef` 数据类
- [ ] 1.5 在 `database/index_store.py` 中新增所有新数据类型的索引字典和查询方法
- [ ] 1.6 编写 `tests/test_new_models.py`，验证新数据类的序列化往返

## 2. Package / Import 提取

- [ ] 2.1 创建 `indexer/package_extractor.py`，实现 `extract_packages()` 从 `package_declaration` 节点提取 `PackageDef`
- [ ] 2.2 实现 `extract_imports()` 从 `package_import_declaration` 节点提取 `ImportDef`
- [ ] 2.3 提取 package 内部的 typedef、parameter、function
- [ ] 2.4 在 `indexer/builder.py` 中集成 package 提取到构建流程
- [ ] 2.5 在 `tools/level1_search.py` 中新增 `rtl_search_package` 工具
- [ ] 2.6 编写 `tests/test_package_extractor.py`

## 3. SVA 断言提取

- [ ] 3.1 创建 `indexer/sva_extractor.py`，实现从 `property_declaration` 节点提取 `SVAPropertyDef`
- [ ] 3.2 实现从 `sequence_declaration` 节点提取 `SVASquenceDef`
- [ ] 3.3 实现从 `concurrent_assertion_item` 节点提取 `SVAAssertDef`（assert/assume/cover）
- [ ] 3.4 在 `indexer/builder.py` 中集成 SVA 提取到构建流程
- [ ] 3.5 在 `tools/level3_analysis.py` 中新增 `rtl_sva_properties` 工具
- [ ] 3.6 编写 `tests/test_sva_extractor.py`

## 4. Function / Task 提取

- [ ] 4.1 创建 `indexer/function_task_extractor.py`，实现从 `function_declaration` 节点提取 `FunctionDef`
- [ ] 4.2 实现从 `task_declaration` 节点提取 `FunctionDef`（kind="task"）
- [ ] 4.3 提取 function/task 的端口声明
- [ ] 4.4 在 `indexer/builder.py` 中集成 function/task 提取到构建流程
- [ ] 4.5 在 `tools/level1_search.py` 中新增 `rtl_search_function` 工具
- [ ] 4.6 编写 `tests/test_function_task_extractor.py`

## 5. Defparam 参数重写

- [ ] 5.1 在 `indexer/instance_extractor.py` 中增加 `defparam` 语句识别
- [ ] 5.2 解析 `defparam hierarchical_path = value` 格式
- [ ] 5.3 在例化提取完成后合并 defparam 覆盖值到 `InstanceDef.params`
- [ ] 5.4 对无法解析的跨模块 defparam 记录 warning
- [ ] 5.5 编写 `tests/test_defparam.py`

## 6. 门级原语识别

- [ ] 6.1 在 `indexer/instance_extractor.py` 中增加 `gate_instantiation` 节点识别
- [ ] 6.2 支持 and/or/not/buf/nand/nor/xor/xnor/bufif0/bufif1/notif0/notif1 原语
- [ ] 6.3 提取门级原语的位置端口连接
- [ ] 6.4 在 `InstanceDef` 中增加 `is_primitive` 标记
- [ ] 6.5 编写 `tests/test_gate_primitive.py`

## 7. Generate 循环展开

- [ ] 7.1 在 `indexer/verilog_parser.py` 中实现 `expand_generate_for()` 函数
- [ ] 7.2 解析 for-generate 的 genvar 初始值、条件、步进
- [ ] 7.3 实现循环体克隆和 genvar 替换
- [ ] 7.4 设置展开上限（默认 256），超出时保留原始结构
- [ ] 7.5 在 `iter_module_body_deep` 中集成展开逻辑
- [ ] 7.6 编写 `tests/test_generate_expansion.py`

## 8. 参数常量传播

- [ ] 8.1 创建 `analysis/param_propagator.py`，实现 `ParamPropagator` 类
- [ ] 8.2 实现从顶层模块 BFS 遍历例化树的参数传播
- [ ] 8.3 实现简单算术表达式求值（加减乘除、常量折叠）
- [ ] 8.4 集成 defparam 覆盖（优先级：defparam > 例化参数 > 默认值）
- [ ] 8.5 对无法求值的参数标记为 "unresolved"
- [ ] 8.6 在 `tools/level3_analysis.py` 中新增 `rtl_parameter_values` 工具
- [ ] 8.7 编写 `tests/test_param_propagator.py`

## 9. 增量索引

- [ ] 9.1 在 `indexer/builder.py` 中实现 `build_incremental()` 方法
- [ ] 9.2 实现文件变更检测（mtime + SHA256）
- [ ] 9.3 实现缓存格式扩展（`_file_hashes`、`_cache_version` 字段）
- [ ] 9.4 处理新增文件和删除文件的索引更新
- [ ] 9.5 在 `server.py` 的 `rtl_build_index` 工具中增加 `incremental` 参数
- [ ] 9.6 编写 `tests/test_incremental_build.py`

## 10. 并行解析

- [ ] 10.1 在 `indexer/verilog_parser.py` 中实现 `parse_single_file()` 顶层函数
- [ ] 10.2 在 `indexer/builder.py` 中实现 `ProcessPoolExecutor` 并行解析
- [ ] 10.3 实现并行阈值（<10 文件串行，>=10 文件并行）
- [ ] 10.4 支持 `max_workers` 配置参数
- [ ] 10.5 编写 `tests/test_parallel_parse.py`

## 11. MCP 工具与集成

- [ ] 11.1 在 `tools/level1_search.py` 中注册 `rtl_search_package`、`rtl_search_function`
- [ ] 11.2 在 `tools/level3_analysis.py` 中注册 `rtl_sva_properties`、`rtl_parameter_values`
- [ ] 11.3 更新 `server.py` 中的 `rtl_build_index` 支持 incremental 和 max_workers 参数
- [ ] 11.4 确认所有现有 MCP 工具接口不变

## 12. 最终验证

- [ ] 12.1 运行 `uv run pytest tests/ -v`，确认所有测试通过
- [ ] 12.2 用包含 package/SVA/function 的测试文件执行 `rtl_build_index`，验证新提取器工作正常
- [ ] 12.3 验证增量构建：修改单文件后仅重新解析该文件
- [ ] 12.4 验证并行解析：大型项目索引构建时间有明显缩短
- [ ] 12.5 确认无 import 错误：`uv run python -c "from server import create_app; print('OK')"`
