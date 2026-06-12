## 1. 依赖与基础配置

- [x] 1.1 在 `pyproject.toml` 的 `dependencies` 中添加 `pyslang>=11.0.0,<12.0.0`
- [x] 1.2 验证 `pip install -e .` 能正确安装 pyslang
- [x] 1.3 在 `config.yaml` 中新增 `pyslang` 配置段（启用开关、include_dirs、defines）
- [x] 1.4 在 `server.py` 中加载 `pyslang` 配置并传入 `IndexBuilder`
- [x] 1.5 验证 `import pyslang` 在项目中可用，不可用时回退到纯 tree-sitter 模式

## 2. pyslang 解析器封装

- [x] 2.1 新建 `indexer/pyslang_parser.py`，实现 `PyslangParser` 类
- [x] 2.2 实现 `parse_files(file_paths, include_dirs, defines) -> Compilation` 方法
- [x] 2.3 实现 `elaborate(compilation, top_module) -> DesignRoot` 方法
- [x] 2.4 实现 `get_diagnostics(compilation) -> list[dict]` 方法（提取错误/警告）
- [x] 2.5 支持 `.f` 文件列表解析（复用现有 `FilelistParser`）
- [x] 2.6 实现 pyslang 异常捕获（语法错误不阻塞 tree-sitter 索引）
- [x] 2.7 为 `PyslangParser` 编写单元测试（单文件、多文件、含错误文件）

## 3. pyslang 提取器

- [x] 3.1 新建 `indexer/pyslang_extractor.py`，实现 `PyslangExtractor` 类
- [x] 3.2 实现 `extract_elaborated_instances(design_root)` 方法（generate 展开实例）
- [x] 3.3 实现 `extract_resolved_signals(design_root)` 方法（参数求值后位宽）
- [x] 3.4 实现 `extract_macro_expansions(design_root)` 方法（宏定义与展开位置）
- [x] 3.5 实现 `extract_hierarchy(design_root)` 方法（完整层次树）
- [x] 3.6 为 `PyslangExtractor` 编写单元测试（generate 展开、参数求值、宏展开）

## 4. 数据模型扩展

- [x] 4.1 在 `database/models.py` 中新增 `ElaboratedInstanceDef` dataclass
- [x] 4.2 在 `database/models.py` 中新增 `ResolvedSignalDef` dataclass
- [x] 4.3 在 `database/models.py` 中新增 `MacroExpansionInfo` dataclass
- [x] 4.4 在 `database/models.py` 中新增 `ElaborationReport` dataclass
- [x] 4.5 为新增数据模型编写序列化/反序列化单元测试

## 5. SQLite 扩展

- [x] 5.1 在 `database/sqlite_backend.py` 的 `_SCHEMA_SQL` 中新增 `elaborated_instances`、`resolved_signals`、`macro_expansions`、`elaboration_reports` 四张表
- [x] 5.2 实现 `save_elaborated_instance`、`get_elaborated_instances_by_module`、`get_all_elaborated_instances`
- [x] 5.3 实现 `save_resolved_signal`、`get_resolved_signals_by_module`
- [x] 5.4 实现 `save_macro_expansion`、`get_macro_expansions`
- [x] 5.5 实现 `save_elaboration_report`、`get_latest_elaboration_report`
- [x] 5.6 在 `database/index_store.py` 中暴露 elaboration 查询接口（含内存缓存）
- [x] 5.7 为 SQLite 扩展编写单元测试

## 6. 索引构建集成

- [x] 6.1 修改 `indexer/builder.py`，在 `build()` 方法中增加 pyslang elaboration 步骤
- [x] 6.2 实现 pyslang elaboration 变更检测（参数/generate/实例化/宏变更触发重跑）
- [x] 6.3 实现 pyslang `Compilation` 缓存机制（序列化到 `.verilog_mcp/pyslang_cache/`）
- [x] 6.4 修改 `build_incremental()`，在增量构建时根据变更类型决定是否触发 pyslang
- [x] 6.5 实现 tree-sitter + pyslang 数据融合（`ModuleDef` 增强字段填充）
- [x] 6.6 验证首次构建（全量）和增量构建的流程正确性

## 7. MCP 工具增强

- [x] 7.1 修改 `tools/level1_search.py` 的 `rtl_get_module`，返回 pyslang 增强数据（`resolved_width`、`resolved_value`）
- [x] 7.2 修改 `tools/level1_search.py` 的 `rtl_hierarchy`，返回含 generate 展开实例的层次树
- [x] 7.3 新建 `tools/elab_tools.py`，实现 `rtl_elab_report` 工具
- [x] 7.4 `rtl_elab_report` 返回 elaboration 摘要（generate 数量、展开实例数、宏数量、模块数量差异）
- [x] 7.5 修改 `analysis/visualizer.py`，层次图支持 generate 实例的特殊样式
- [x] 7.6 修改 `tools/__init__.py` 导出新增工具
- [x] 7.7 为增强工具编写单元测试

## 8. 全量验证

- [x] 8.1 运行完整测试套件：`pytest tests/ -v`，确保 100% 通过
- [x] 8.2 验证现有 RTL 测试无回归（tree-sitter 索引不受影响）
- [x] 8.3 验证 pyslang 不可用时系统正常工作（降级到纯 tree-sitter）
- [x] 8.4 验证增量构建时 pyslang 变更检测正确（参数变更触发、assign 变更不触发）
- [x] 8.5 验证 `rtl_elab_report` 输出正确
- [x] 8.6 更新 README，添加 pyslang 集成说明
