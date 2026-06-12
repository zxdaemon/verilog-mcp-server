## Context

基于已有的 `ClockAnalyzer`（单模块时钟检测）和 `HierarchyBuilder`（层次树遍历），构建跨模块的时钟域追踪引擎。核心挑战：不同层次模块中对同一时钟的命名可能不同（如顶层 `cpuclk` → 子模块 `clk`），需要通过 `InstanceDef.port_connections` 做信号名穿透映射。

## Goals / Non-Goals

**Goals:**
- 从顶层模块出发，遍历所有子模块，收集时钟域信息
- 通过 `port_connections` 将子模块本地时钟名逐级映射为顶层信号名
- 按根时钟名分组，每组内的模块按层次树结构组织
- 输出 ASCII 树状图和 Mermaid flowchart 两种格式
- 通过模块名模式识别门控时钟单元

**Non-Goals:**
- 不分析时钟频率、相位关系
- 不自动推断时钟派生关系（仅通过命名/门控单元识别）
- 不修改现有 `ClockAnalyzer` 或 `HierarchyBuilder` 的接口

## Decisions

### D1: 时钟名追踪 = 沿 instance_path 向上查 port_connections

给定子模块本地时钟名（如 `alu` 中的 `clk`），向上追溯到父模块的实际信号名：

```python
def _trace_clock_to_root(instance_path, local_clock, hierarchy_root):
    parts = instance_path.split(".")
    clock_name = local_clock
    for i in range(len(parts)-1, 0, -1):
        parent_path = ".".join(parts[:i])
        inst_name = parts[i]
        parent_node = find_node(parent_path, hierarchy_root)
        inst = find_instance(parent_node, inst_name)
        if inst:
            clock_name = inst.port_connections.get(clock_name, clock_name)
    return clock_name
```

备选方案: 直接比较所有实例的时钟信号名字符串（不可靠，容易因命名差异导致误分组）。

### D2: 门控时钟检测 = 可配置的模块名模式

默认模式列表 `["gated_clk_cell", "icg", "CLKGATE", "clock_gate"]`，用户可通过 tool 参数覆盖。只有模块类型名匹配模式时才标记为 `is_gated_cell`。

备选方案: 分析门控单元的逻辑结构（AND/OR + 时钟）→ 过于复杂，留待后续。

### D3: 输出格式选择 Mermaid 而非 SVG

- Mermaid 是纯文本，适配 MCP tool 的 `str` 返回类型
- Gitee/GitHub Markdown 原生渲染 Mermaid，无需外部工具
- SVG 需引入 graphviz 依赖，输出 XML 文本不可读

备选方案: 同时支持 Mermaid 和 Graphviz DOT → DOT 没有渲染优势，增加维护成本。

### D4: 按时钟域分组后，每组内按层次树重建

`_build_module_tree_for_domain()` 用 instance_path 分隔重建树结构：`soc.u_cpu.u_alu` → 父节点 `soc.u_cpu`。这种重建复用 `HierarchyNode` 概念但只包含同一时钟域的节点。

## Risks / Trade-offs

- **[低] 端口名穿透可能不完整**: 如果 `port_connections` 是位置连接（无 `.name(sig)` 显式映射）→ 会保留原始信号名，可能产生重复时钟域。可通过后续添加位置端口映射解决。
- **[低] 大量模块可能导致输出过长**: 每个时钟域最多展示 3 层深度，超过时显示 "└─ ... 还有 N 个模块"。
