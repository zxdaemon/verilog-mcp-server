## Context

当前 Verilog MCP Server 的架构为四层分层：indexer（tree-sitter AST 解析）→ database（SQLite + 内存缓存）→ analysis（Python 分析引擎）→ tools（MCP 工具）。所有分析基于 tree-sitter 的语法级 AST，不做预处理、不求值参数、不展开 generate。

tree-sitter 解析器的核心局限：
- `ifdef/`ifndef 条件编译分支全部保留，不做选择
- `define 宏定义不被展开
- parameter 值不被求值（`[WIDTH-1:0]` 保持文本形式）
- generate for/if/case 只遍历不展开
- 无时序信息（setup/hold、clock skew、关键路径）
- 无综合后网表信息（无法识别组合逻辑环、门控时钟、实际 FSM 编码）

EDA 工具能够提供互补的精确视图：
- **slang**：完整 SV 前端，输出参数求值后的 AST、generate 展开后的层次树
- **Yosys**：综合工具，输出 FSM 提取、组合环检测、门控时钟识别
- **Verilator**：仿真器，输出 lint 报告和信号依赖图
- **Design Compiler**：商业综合工具，输出综合后层次树、资源报告、时钟域报告
- **VCS**：商业仿真器，输出设计结构数据库和覆盖率
- **PrimeTime**：商业 STA 工具，输出时序路径报告
- **SpyGlass/VC Lint**：lint 工具，输出 CDC/RDC 结构化报告

## Goals / Non-Goals

**Goals:**
- 建立 EDA 工具编排层，支持配置化调用开源和商业 EDA 工具
- 解析 slang JSON AST，提取 generate 展开、参数求值、宏展开信息
- 解析 Yosys 输出，提取 FSM、组合环、门控时钟、资源统计
- 通过 Tcl 调用 Design Compiler，提取综合报告
- 通过 Tcl/UCLI 调用 VCS，提取设计结构信息
- 解析 PrimeTime 时序报告，提取关键路径和时钟偏斜
- 解析 SpyGlass/VC Lint 报告，提取 lint/CDC/RDC 问题
- 构建多源融合知识图谱，统一 tree-sitter/slang/Yosys/商业 EDA 数据
- 升级存储层支持图查询（多跳关系、路径搜索、环检测）

**Non-Goals:**
- 不将 EDA 工具作为 Python 依赖（通过系统 PATH 调用）
- 不实现 EDA 工具内部算法（只做输出解析和数据融合）
- 不支持 EDA 工具的交互式 GUI 功能
- 不替代现有 tree-sitter 索引（EDA 为增强层，tree-sitter 保持为主索引）
- 不要求用户必须安装任何 EDA 工具（所有集成为可选）

## Decisions

### 1. 适配器模式：每个 EDA 工具一个 Adapter

**选择**: 每个 EDA 工具实现独立的 Adapter 类（`SlangAdapter`、`YosysAdapter`、`DcAdapter`、`VcsAdapter`、`PtAdapter`、`LintAdapter`），统一继承 `BaseEdaAdapter` 接口（`check_available()`、`run()`、`parse_output()`）。`EdaToolOrchestrator` 通过配置加载启用的 adapter 列表。

**替代方案**: 统一的 EDA 调用器 → 拒绝，各工具的调用方式差异大（slang 是命令行直接调用，DC/PT/VCS 需要 Tcl 脚本中间层），统一抽象会导致过度复杂。

### 2. Tcl 脚本模板引擎

**选择**: 商业 EDA 工具（DC、PT、VCS）通过生成 Tcl 脚本文件，再调用工具执行。Tcl 脚本使用 Python string.Template 模板化，adapter 填充项目路径、顶层模块名等变量。脚本执行后解析生成的文本/JSON 报告。

**替代方案**: 使用工具的 Python API（如 PyVCS）→ 拒绝，商业工具的 Python API 通常不完整或需要额外 license，Tcl 是所有工具的通用接口。

### 3. 输出缓存策略

**选择**: EDA 工具运行开销大，结果需要缓存。在 `.verilog_mcp/eda_outputs/` 目录下按工具名和输入文件 hash 存储输出文件。`EdaToolOrchestrator` 在调用前检查缓存：若源文件未变更且缓存存在，直接解析缓存文件。

**替代方案**: 存入 SQLite → 拒绝，EDA 输出文件通常较大（MB 级 JSON/XML），文件系统更适合，SQLite 只存元数据（工具名、输入 hash、输出路径、时间戳）。

### 4. 知识图谱融合策略：source 标签 + 置信度

**选择**: 融合层为每个节点/边标记数据来源（`source: tree-sitter | slang | yosys | dc | pt | vcs | lint`）和置信度（`confidence: high | medium | low`）。当多源数据冲突时，优先级：综合后数据 > 仿真数据 > 语法分析数据（`yosys/dc/pt > vcs > slang > tree-sitter`）。冲突时保留高优先级数据，低优先级数据存入 `alternatives` 字段。

**替代方案**: 简单覆盖（后者覆盖前者）→ 拒绝，会丢失有价值的多视角信息。保留冲突对调试很有用。

### 5. 图存储：networkx 内存图 + SQLite 持久化

**选择**: 使用 `networkx.DiGraph` 构建内存中的有向知识图谱，支持多跳查询、最短路径、环检测。图数据在 `IndexStore` 加载时从 SQLite 构建（节点和边从各数据表加载）。图修改写回 SQLite 持久化。networkx 为可选依赖，不可用时回退到现有递归遍历。

**替代方案**: 使用图数据库（Neo4j/ArangoDB）→ 拒绝，引入外部服务与项目轻量级定位冲突。使用 `igraph` → networkx 更易用且 Python 生态更成熟。

### 6. 商业工具适配优先级

**选择**: 按 ROI 和通用性排序实现：
1. Design Compiler（综合报告，信息最丰富，Tcl 接口稳定）
2. SpyGlass/VC Lint（结构化报告解析最简单，lint/CDC/RDC 直接可用）
3. PrimeTime（时序报告格式标准，价值高）
4. VCS（UCLI 接口较复杂，优先级略低）

**替代方案**: 全部并行实现 → 拒绝，商业工具 adapter 开发需要实际环境验证，分阶段降低风险。

## Risks / Trade-offs

- **商业工具 license 依赖**：用户环境可能没有 DC/PT/VCS license → 所有商业工具集成为可选，无工具时系统正常工作
- **Tcl 脚本安全性**：生成的 Tcl 脚本可能包含用户项目路径 → 路径通过 `shlex.quote` 处理，不直接拼接用户输入到 Tcl
- **EDA 工具版本差异**：DC/PT 不同版本报告格式可能有差异 → adapter 使用宽松的解析策略，对未知字段 warn 而非 crash
- **性能影响**：调用 EDA 工具可能耗时数分钟 → 异步执行 + 缓存机制，MCP 工具返回"正在分析"状态，结果通过轮询或回调获取
- **输出文件大小**：slang JSON 输出可能达数百 MB → 流式解析（`ijson` 或自定义流式 JSON 解析器），不一次性加载到内存
- **networkx 内存占用**：大型设计（>10K 模块）的图可能占用大量内存 → 支持图的延迟加载（按需构建子图）和节点聚合（与现有可视化聚合机制复用）

## Migration Plan

1. **Phase 1**（无 EDA）：系统保持现有行为，tree-sitter 索引正常工作
2. **Phase 2**（启用 slang）：用户配置 `eda_integration.slang.enabled: true`，首次构建索引时自动调用 slang，生成增强数据
3. **Phase 3**（启用 Yosys）：配置 `yosys.enabled: true`，综合项目生成网表报告
4. **Phase 4**（启用商业工具）：配置 DC/PT/VCS/Lint 路径，按需生成报告
5. **Rollback**：关闭 `eda_integration.enabled: false`，系统回退到 tree-sitter 模式，已有 EDA 缓存数据保留但不使用

## Open Questions

1. 是否需要支持 Vivado（FPGA 设计）的集成？
2. 是否需要支持自定义 EDA 工具 adapter（插件机制）？
3. EDA 工具调用失败时的重试策略（几次重试、指数退避）？
4. 多源数据冲突时，是否提供 MCP 工具让用户选择使用哪个来源？
