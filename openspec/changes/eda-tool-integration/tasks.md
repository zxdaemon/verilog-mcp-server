## 1. 基础架构与配置

- [ ] 1.1 新建 `verilog_mcp_server/eda/` 目录结构
- [ ] 1.2 在 `eda/` 中创建 `__init__.py` 导出公共接口
- [ ] 1.3 实现 `BaseEdaAdapter` 抽象基类（`check_available()`、`run()`、`parse_output()`）
- [ ] 1.4 实现 `EdaToolOrchestrator` 类（配置加载、适配器管理、缓存检查、异步执行）
- [ ] 1.5 实现 EDA 输出缓存机制（输入文件 hash 计算、缓存目录管理、缓存命中检测）
- [ ] 1.6 在 `config.yaml` 中新增 `eda_integration` 配置段（含各工具启用开关、路径、额外参数）
- [ ] 1.7 修改 `server.py` 加载 `eda_integration` 配置并传入 `EdaToolOrchestrator`
- [ ] 1.8 修改 `ProjectScanner` 默认排除 `.verilog_mcp/eda_outputs/` 目录
- [ ] 1.9 为编排器和缓存机制编写单元测试

## 2. SQLite 与图存储扩展

- [ ] 2.1 在 `database/models.py` 中新增 `EdaOutputMeta`、`GraphNode`、`GraphEdge` dataclass
- [ ] 2.2 在 `database/sqlite_backend.py` 的 `_SCHEMA_SQL` 中新增 `eda_outputs`、`graph_nodes`、`graph_edges` 三张表
- [ ] 2.3 在 `database/sqlite_backend.py` 中实现 `save_eda_output`、`get_eda_output` 方法
- [ ] 2.4 在 `database/sqlite_backend.py` 中实现 `save_graph_node`、`save_graph_edge`、`load_all_graph_nodes`、`load_all_graph_edges` 方法
- [ ] 2.5 在 `database/index_store.py` 中新增图数据查询接口
- [ ] 2.6 新建 `analysis/graph_query.py`，实现 `GraphStore` 类（networkx DiGraph 构建、多跳查询、环检测）
- [ ] 2.7 实现 `GraphStore` 的 `find_paths`、`find_ancestors`、`find_descendants`、`find_cycles` 方法
- [ ] 2.8 实现 networkx 不可用时降级到纯 Python 字典实现
- [ ] 2.9 为 SQLite 扩展和 GraphStore 编写单元测试

## 3. 开源 EDA 工具集成

### 3.1 slang 适配器
- [ ] 3.1.1 新建 `eda/slang_adapter.py`，实现 `SlangAdapter` 类
- [ ] 3.1.2 实现 slang 命令行生成（`--json`、`--top`、`--f` 等参数）
- [ ] 3.1.3 实现 slang JSON 输出的流式解析（处理大文件，不一次性加载内存）
- [ ] 3.1.4 提取 generate 展开后的层次树（含数组例化实例名）
- [ ] 3.1.5 提取参数求值后的信号位宽
- [ ] 3.1.6 提取宏展开信息
- [ ] 3.1.7 为 SlangAdapter 编写单元测试（含 mock 输出解析）

### 3.2 Yosys 适配器
- [ ] 3.2.1 新建 `eda/yosys_adapter.py`，实现 `YosysAdapter` 类
- [ ] 3.2.2 实现 Yosys Tcl 脚本模板生成（`read_verilog -sv` → `hierarchy` → `fsm_detect` → `check` → `write_json`）
- [ ] 3.2.3 解析 Yosys JSON 网表提取 FSM 列表（状态数、编码方式）
- [ ] 3.2.4 解析 Yosys `check` 输出提取组合逻辑环告警
- [ ] 3.2.5 解析 Yosys 输出提取 LUT/FF/Memory 资源统计
- [ ] 3.2.6 解析 Yosys 输出提取门控时钟信号
- [ ] 3.2.7 为 YosysAdapter 编写单元测试

### 3.3 Verilator 适配器
- [ ] 3.3.1 新建 `eda/verilator_adapter.py`，实现 `VerilatorAdapter` 类
- [ ] 3.3.2 实现 `verilator --lint-only` 命令调用
- [ ] 3.3.3 解析 lint 报告提取 warning/error（文件路径、行号、类别、描述）
- [ ] 3.3.4 为 VerilatorAdapter 编写单元测试

## 4. 商业 EDA 工具集成

### 4.1 Design Compiler 适配器
- [ ] 4.1.1 新建 `eda/dc_adapter.py`，实现 `DcAdapter` 类
- [ ] 4.1.2 实现 DC Tcl 脚本模板生成（`analyze` → `elaborate` → `compile` → 报告生成）
- [ ] 4.1.3 实现 Tcl 脚本路径安全转义（`shlex.quote`）
- [ ] 4.1.4 解析 `report_hierarchy` 提取综合后层次树
- [ ] 4.1.5 解析 `report_area` 提取资源统计
- [ ] 4.1.6 解析 `report_clock` 提取时钟域信息
- [ ] 4.1.7 为 DcAdapter 编写单元测试（含 mock 报告解析）

### 4.2 PrimeTime 适配器
- [ ] 4.2.1 新建 `eda/pt_adapter.py`，实现 `PtAdapter` 类
- [ ] 4.2.2 实现 PrimeTime Tcl 脚本模板生成（`read_verilog` → `read_lib` → `read_sdc` → `update_timing` → `report_timing`）
- [ ] 4.2.3 解析 `report_timing` 提取关键路径（起点、终点、延迟、slack）
- [ ] 4.2.4 解析 `report_clock_timing -type skew` 提取时钟偏斜
- [ ] 4.2.5 为 PtAdapter 编写单元测试

### 4.3 VCS 适配器
- [ ] 4.3.1 新建 `eda/vcs_adapter.py`，实现 `VcsAdapter` 类
- [ ] 4.3.2 实现 VCS 编译日志解析（`vlogan`/`vcs` 输出）
- [ ] 4.3.3 实现 UCLI 脚本生成（`scope`、`show` 命令）
- [ ] 4.3.4 解析设计结构信息（模块层次、信号列表、端口方向）
- [ ] 4.3.5 为 VcsAdapter 编写单元测试

### 4.4 Lint 适配器
- [ ] 4.4.1 新建 `eda/lint_adapter.py`，实现 `LintAdapter` 类
- [ ] 4.4.2 实现 SpyGlass XML/JSON 报告解析
- [ ] 4.4.3 实现 VC Lint 结构化报告解析
- [ ] 4.4.4 提取 lint/CDC/RDC 问题（规则名、严重度、文件、行号、描述）
- [ ] 4.4.5 为 LintAdapter 编写单元测试

## 5. 知识图谱融合引擎

- [ ] 5.1 新建 `eda/fusion_engine.py`，实现 `FusionEngine` 类
- [ ] 5.2 定义统一节点类型枚举（module、instance、signal、port、clock_domain、fsm_state 等）
- [ ] 5.3 定义统一边类型枚举（contains、instantiates、drives、clocks、transitions_to 等）
- [ ] 5.4 实现数据来源标记（`source` 字段）和置信度评分
- [ ] 5.5 实现冲突消解策略（优先级：yosys/dc/pt > vcs > slang > tree-sitter）
- [ ] 5.6 实现多源数据合并（tree-sitter + slang + Yosys + DC 数据融合）
- [ ] 5.7 实现增量融合（仅变更文件相关的节点和边重建）
- [ ] 5.8 将融合结果写入 `GraphStore` 和 SQLite
- [ ] 5.9 为 FusionEngine 编写单元测试

## 6. EDA MCP 工具

- [ ] 6.1 新建 `tools/eda_tools.py`，注册 `rtl_eda_status` 工具
- [ ] 6.2 实现 `rtl_synthesis_report` 工具（返回层次树、资源、时钟域、FSM、组合环）
- [ ] 6.3 实现 `rtl_timing_paths` 工具（接受 clock_domain 和 max_paths 参数）
- [ ] 6.4 实现 `rtl_clock_tree_advanced` 工具（返回时钟源、分频器、门控时钟、偏斜）
- [ ] 6.5 实现 `rtl_cdc_advanced` 工具（返回 CDC 信号、同步器类型、风险等级）
- [ ] 6.6 实现 `rtl_graph_query` 工具（通用图查询：路径、邻居、环）
- [ ] 6.7 所有工具返回结果标注数据来源
- [ ] 6.8 修改 `tools/__init__.py` 导出 EDA 工具注册函数
- [ ] 6.9 修改 `server.py` 注册 EDA MCP 工具
- [ ] 6.10 为 6 个 EDA MCP 工具编写单元测试

## 7. 全量验证与文档

- [ ] 7.1 运行完整测试套件：`pytest tests/ -v`，确保 100% 通过
- [ ] 7.2 验证现有 RTL 测试无回归（tree-sitter 索引不受影响）
- [ ] 7.3 验证无 EDA 工具时系统正常工作（降级模式）
- [ ] 7.4 验证有 EDA 工具时增强数据正确融合
- [ ] 7.5 验证 config.yaml 的 `eda_integration.enabled: false` 正确禁用所有 EDA 调用
- [ ] 7.6 更新 README，添加 EDA 工具集成说明和配置示例
- [ ] 7.7 更新 CLAUDE.md，添加 EDA 架构说明
