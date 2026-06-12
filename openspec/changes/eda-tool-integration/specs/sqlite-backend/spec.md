## ADDED Requirements

### Requirement: SQLite 数据库初始化扩展 EDA 表
`database/sqlite_backend.py` 的 `_SCHEMA_SQL` SHALL 在初始化时创建 `eda_outputs`、`graph_nodes`、`graph_edges` 三张表。
- `eda_outputs` 表：存储 EDA 工具输出的元数据（tool_name、input_hash、output_path、timestamp、status）
- `graph_nodes` 表：存储知识图谱节点（node_id、node_type、properties_json、sources_json）
- `graph_edges` 表：存储知识图谱边（from_id、to_id、edge_type、properties_json、sources_json）

#### Scenario: 首次创建数据库含 EDA 表
- **WHEN** `IndexStore("/tmp/cache.db")` 且文件不存在
- **THEN** 创建全部表，含新增的 `eda_outputs`、`graph_nodes`、`graph_edges`

#### Scenario: 兼容已有数据库升级
- **WHEN** `IndexStore` 打开已有数据库（不含 EDA 表）
- **THEN** 自动执行 `CREATE TABLE IF NOT EXISTS` 添加新表

### Requirement: EDA 输出元数据写入 SQLite
`SQLiteBackend` SHALL 提供 `save_eda_output(tool_name, input_hash, output_path, status)` 和 `get_eda_output(tool_name, input_hash)` 方法，在 `eda_outputs` 表中存取 EDA 输出元数据。

#### Scenario: 存储 EDA 输出元数据
- **WHEN** Yosys 运行完成后
- **THEN** 调用 `save_eda_output("yosys", "abc123", ".verilog_mcp/eda_outputs/yosys/abc123/netlist.json", "success")`

#### Scenario: 查询 EDA 输出缓存
- **WHEN** 调用 `get_eda_output("yosys", "abc123")`
- **THEN** 返回缓存的元数据，含输出路径和时间戳

### Requirement: 图节点和边写入 SQLite
`SQLiteBackend` SHALL 提供 `save_graph_node(node_id, node_type, properties, sources)` 和 `save_graph_edge(from_id, to_id, edge_type, properties, sources)` 方法，在 `graph_nodes` 和 `graph_edges` 表中存取图数据。

#### Scenario: 存储图节点
- **WHEN** 融合引擎生成节点 `top.clk`（类型 `signal`）
- **THEN** 调用 `save_graph_node("top.clk", "signal", '{"width": "[0:0]"}', '["tree-sitter", "slang"]')`

#### Scenario: 存储图边
- **WHEN** 融合引擎生成边 `top.clk --clocks--> cpu.reg.C`
- **THEN** 调用 `save_graph_edge("top.clk", "cpu.reg.C", "clocks", '{"skew": "0.15ns"}', '["pt"]')`

### Requirement: 图数据批量加载
`SQLiteBackend` SHALL 提供 `load_all_graph_nodes()` 和 `load_all_graph_edges()` 方法，单次 SELECT 查询批量加载所有图数据，用于 `GraphStore` 初始化。

#### Scenario: 批量加载图数据
- **WHEN** `GraphStore` 初始化时调用 `load_all_graph_nodes()` 和 `load_all_graph_edges()`
- **THEN** 分别执行单次 `SELECT * FROM graph_nodes` 和 `SELECT * FROM graph_edges`
