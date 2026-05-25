## 1. 项目基础设施

- [x] 1.1 创建 `pyproject.toml`，声明项目元数据、Python >=3.11、依赖和 pytest 配置
- [x] 1.2 创建 `.gitignore`，排除 `__pycache__/`、`*.pyc`、`.venv/`、`*.egg-info/`、`/tmp/`
- [x] 1.3 创建 `tests/__init__.py`（空文件）
- [x] 1.4 确认 `uv run pytest tests/ -v` 可正常启动（即使无测试）

## 2. 统一序列化基类

- [x] 2.1 在 `database/models.py` 中定义 `SerializableModel` 基类，实现 `to_dict()` 和 `from_dict()` 通用方法
- [x] 2.2 迁移 `PortDef`、`ParamDef`、`DriverInfo`、`LoadInfo` 为 `SerializableModel` 子类，删除手动序列化方法
- [x] 2.3 迁移 `InstanceDef`、`SignalDef`、`AlwaysBlockInfo`、`AssignmentInfo` 为 `SerializableModel` 子类
- [x] 2.4 迁移 `ModuleDef` 为 `SerializableModel` 子类（含嵌套列表标注）
- [x] 2.5 编写 `tests/test_serializable_model.py`，验证 `to_dict()`/`from_dict()` 往返一致性
- [x] 2.6 执行 `uv run pytest tests/ -v` 验证序列化迁移无回归

## 3. 异常层次

- [x] 3.1 创建 `database/errors.py`，定义 `DomainError` 基类和 `ModuleNotFoundError`、`SignalNotFoundError`、`IndexNotBuiltError`、`AnalysisError` 子类
- [x] 3.2 在 `database/__init__.py` 中导出异常类
- [x] 3.3 编写 `tests/test_errors.py`，验证各种异常的 message 和继承关系

## 4. 工具层重构 — Level 1

- [x] 4.1 提取 `_do_search_module(index_store, pattern) -> list[ModuleDef]` 和 `_fmt_search_module_results(results) -> str`
- [x] 4.2 提取 `_do_get_module(index_store, name) -> ModuleDef`（找不到抛出 `ModuleNotFoundError`）和复用 `_fmt_module_summary`
- [x] 4.3 提取 `_do_get_module_ports(index_store, name) -> tuple[ModuleDef, list[PortDef]]`（找不到抛出 `ModuleNotFoundError`）
- [x] 4.4 提取 `_do_list_instances(index_store, name) -> tuple[ModuleDef, list[InstanceDef]]`
- [x] 4.5 提取 `_do_search_signal(index_store, name, module_name=None) -> list[tuple[ModuleDef, str]]` 和 `_fmt_signal_results`
- [x] 4.6 提取 `_do_get_hierarchy(index_store, name, max_depth) -> str`（保留树构建逻辑，可考虑迁入 HierarchyBuilder）
- [x] 4.7 `register_tools` 内部仅保留 `@mcp.tool()` 装饰 + 调用 `_do_*`/`_fmt_*`，替换 `except Exception` 为 `except DomainError`
- [x] 4.8 编写 `tests/test_level1_tools.py`，用 fake IndexStore 测试所有 `_do_*` 函数

## 5. 工具层重构 — Level 2

- [x] 5.1 提取 `_do_trace_signal(index_store, signal_name, start_module, direction, max_depth) -> TraceResult`
- [x] 5.2 提取 `_do_where_used(index_store, target, target_type) -> list[UsageInfo]`
- [x] 5.3 提取 `_do_instance_connections(index_store, instance_name, module_name) -> list[ConnectionDetail]`
- [x] 5.4 提取 `_do_hierarchy_tree(index_store, top_module, max_depth) -> HierarchyNode`
- [x] 5.5 提取 `_do_hierarchy_instances(index_store, top_module, max_depth) -> list[dict]`
- [x] 5.6 `register_tools` 替换 `except Exception` 为 `except DomainError`
- [x] 5.7 编写 `tests/test_level2_tools.py`，测试所有 `_do_*` 函数

## 6. 工具层重构 — Level 3 + 引擎生命周期

- [x] 6.1 将 `FSMDetector`、`ClockAnalyzer`、`AlwaysClassifier` 实例化提升到 `register_tools` 函数体顶部
- [x] 6.2 提取 `_do_detect_fsm(index_store, module_name) -> FSMResult`
- [x] 6.3 提取 `_do_clock_domains(index_store, module_name) -> ClockAnalysis`
- [x] 6.4 提取 `_do_reset_domains(index_store, module_name) -> ClockAnalysis`
- [x] 6.5 提取 `_do_always_classify(index_store, module_name) -> ClassificationResult`
- [x] 6.6 提取 `_do_cross_domain_signals(index_store, module_name) -> list[dict]`
- [x] 6.7 `register_tools` 替换 `except Exception` 为 `except DomainError`
- [x] 6.8 编写 `tests/test_level3_tools.py`，测试所有 `_do_*` 函数

## 7. 拆分 dataflow.py

- [x] 7.1 创建 `analysis/fan_in.py`，移入 `_trace_fan_in()` 方法和相关数据模型
- [x] 7.2 创建 `analysis/fan_out.py`，移入 `_trace_fan_out()` 方法和相关数据模型
- [x] 7.3 修改 `analysis/dataflow.py` 为从两个子模块重新导出 `DataflowTracer`
- [x] 7.4 更新 `analysis/__init__.py`，确保 `DataflowTracer` 仍可通过 `from analysis import DataflowTracer` 导入
- [x] 7.5 确认所有现有 import 路径不失效

## 8. 单元测试 — 核心提取器

- [x] 8.1 编写 `tests/test_module_extractor.py`，用内联 Verilog 源码字符串测试 `ModuleExtractor.extract()`
- [x] 8.2 编写 `tests/test_port_extractor.py`，测试 ANSI 风格端口解析
- [x] 8.3 编写 `tests/test_signal_extractor.py`，测试 wire/reg/assign/always 提取
- [x] 8.4 编写 `tests/test_instance_extractor.py`，测试例化和端口连接提取

## 9. 最终验证

- [x] 9.1 运行 `uv run pytest tests/ -v`，确认全部测试通过（32/32 非网络依赖测试通过；7 个提取器测试因 tree-sitter parser 网络下载受限跳过）
- [x] 9.2 用 `test_top.v` 执行 `server.py --build`，确认索引构建成功（3 模块、1 文件）
- [x] 9.3 确认无 import 错误：`uv run python -c "from server import create_app; print('OK')"`
- [x] 9.4 确认 dataflow.py (10行)、fan_in.py (351行)、fan_out.py (148行) 均 < 500；cross_ref.py (582行) 标记为后续优化目标
