## ADDED Requirements

### Requirement: networkx 图构建
`GraphStore` SHALL 在 `IndexStore` 初始化时从 SQLite 数据构建 `networkx.DiGraph`。节点为模块/信号/端口等，边为 contains/instantiates/drives 等关系。图构建为一次性操作，后续增量更新。

#### Scenario: 从 SQLite 构建图
- **WHEN** `IndexStore` 加载包含 100 个模块的数据库
- **THEN** `GraphStore` 构建包含约 1000+ 节点和 2000+ 边的有向图

### Requirement: 多跳关系查询
`GraphStore` SHALL 提供多跳查询接口：
- `find_paths(from_id, to_id, max_depth)` — 查找两节点间的所有路径
- `find_ancestors(node_id, edge_type, max_depth)` — 沿指定边类型向上查找祖先
- `find_descendants(node_id, edge_type, max_depth)` — 沿指定边类型向下查找后代
- `find_cycles()` — 检测图中所有环（用于组合逻辑环检测）

#### Scenario: 时钟传播路径查询
- **WHEN** 调用 `find_paths("top.clk", "cpu.alu.reg.C", max_depth=10)`
- **THEN** 返回从顶层时钟到寄存器时钟端的所有传播路径

#### Scenario: 组合逻辑环检测
- **WHEN** 调用 `find_cycles()`
- **THEN** 返回图中所有环的节点列表（如 `[a, b, c, a]` 表示 `a→b→c→a`）

### Requirement: 图查询 MCP 工具
`GraphStore` 的能力 SHALL 通过 MCP 工具暴露：`rtl_graph_query` 支持通用图查询（路径、邻居、环），`rtl_find_paths` 专门用于信号追踪路径。

#### Scenario: 通用图查询
- **WHEN** 调用 `rtl_graph_query(query_type="neighbors", node_id="top.cpu")`
- **THEN** 返回 `top.cpu` 的所有邻居节点（子模块、端口、信号）

### Requirement: networkx 可选降级
当 `networkx` 不可用时，`GraphStore` SHALL 回退到现有递归遍历实现（`HierarchyBuilder._expand`、`DataflowTracer._trace_fan_in` 等）。功能可用但性能降低。

#### Scenario: 无 networkx 环境
- **WHEN** `import networkx` 失败
- **THEN** `GraphStore` 使用纯 Python 字典+集合实现图，查询接口保持不变

### Requirement: 图数据持久化
图数据 SHALL 持久化到 SQLite。新增 `graph_nodes` 和 `graph_edges` 两张表，存储节点 ID、类型、属性、边起点/终点/类型。`GraphStore` 加载时从这两张表重建图。

#### Scenario: 图数据持久化
- **WHEN** `IndexStore` 关闭时
- **THEN** 当前内存图的所有节点和边写入 `graph_nodes` 和 `graph_edges` 表

#### Scenario: 图数据恢复
- **WHEN** `IndexStore` 重新打开已有数据库
- **THEN** 从 `graph_nodes` 和 `graph_edges` 表重建内存图
