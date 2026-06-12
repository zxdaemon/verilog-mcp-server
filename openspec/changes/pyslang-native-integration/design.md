## Context

当前 Verilog MCP Server 使用 tree-sitter 作为唯一解析器。tree-sitter 是纯语法解析器，其 AST 反映源码文本结构，不做任何语义分析。这意味着：
- `ifdef/`ifndef 条件编译分支全部保留，不做选择
- `define 宏定义不被展开，宏调用保持原样
- parameter 值不被求值（`[WIDTH-1:0]` 保持文本形式）
- generate for/if/case 只遍历不展开
- 无法区分参数化模块的不同实例类型

pyslang 是 slang（业界公认最完整的开源 SystemVerilog 编译器前端）的官方 Python 绑定，可直接 `pip install`。它提供完整的 elaboration 能力：预处理（宏展开、条件编译选择）、参数求值、generate 展开、类型检查。与 tree-sitter 不同，pyslang 的输出是"elaborated design"——一个已经求值、展开后的完整设计视图。

## Goals / Non-Goals

**Goals:**
- 将 `pyslang` 作为核心 Python 依赖集成（用户 `pip install` 时自动获得）
- 封装 pyslang API，提供与现有 `verilog_parser.py` 风格一致的解析接口
- 从 pyslang elaboration 结果提取 generate 展开实例、参数求值后的信号位宽、完整层次树
- 将 pyslang 增强数据与现有 tree-sitter 索引融合存储
- `rtl_get_module` 和 `rtl_hierarchy` 等工具返回 pyslang 增强数据
- 保持 tree-sitter 索引完全不变（向后兼容）

**Non-Goals:**
- 不替换 tree-sitter（当前 change 只添加 pyslang 作为增强层）
- 不使用 pyslang 替代现有提取器（保持现有提取器不变）
- 不引入其他 EDA 工具（Yosys/DC/PT 等在后续 change 中实现）
- 不要求 pyslang 解析 UVM class（UVM 在独立 change 中规划）

## Decisions

### 1. pyslang 作为增强层，tree-sitter 保持主解析器

**选择**: pyslang 不负责替换 tree-sitter，而是作为"语义增强解析器"并行运行。索引构建流程：
1. tree-sitter 解析所有文件 → 提取 module/port/signal/instance（现有流程，不变）
2. pyslang 对整个设计做 elaboration → 提取 generate 展开、参数求值、完整层次树
3. 两者结果融合存入 SQLite

**替代方案**: 用 pyslang 完全替代 tree-sitter → 拒绝，pyslang 的 AST 结构与 tree-sitter 完全不同，替换需要重写所有提取器，工作量和风险过高。

### 2. pyslang 解析粒度：设计级而非文件级

**选择**: pyslang 的 `Compilation` 对象接受整个设计的文件列表，内部自动处理跨文件引用（`include、import、实例化）。调用方式为：
```python
compilation = pyslang.Compilation(syntax_trees)
# 从 compilation 获取 elaborated design
top_instances = compilation.getRoot().topInstances
```

这与 tree-sitter 的"逐文件解析"不同。`PyslangParser` 在 `build()` 时收集所有文件路径，一次性传给 pyslang。

**替代方案**: 逐文件调用 pyslang → 拒绝，pyslang 的 `Compilation` 需要完整设计上下文才能正确 elaboration（处理跨模块引用、参数传递）。

### 3. 增量构建策略：pyslang 变更检测

**选择**: pyslang elaboration 的增量检测比 tree-sitter 更复杂。因为 pyslang 是设计级解析，单个文件的变更可能影响整个设计的 elaboration 结果（如修改一个 parameter 可能影响所有实例化该模块的地方）。

增量策略：
- **轻量变更**（assign 语句改值、内部逻辑改表达式）：不触发 pyslang 重跑
- **接口变更**（端口增删、parameter 值变化）：触发 pyslang 重跑
- **结构变更**（generate 条件、模块例化增删）：触发 pyslang 重跑
- 检测方式：比较变更文件的 tree-sitter AST 变更类型

**替代方案**: 每次增量都重跑 pyslang → 拒绝，pyslang elaboration 对大型设计可能需要 10-30 秒，每次重跑太慢。

### 4. 数据模型：增强字段而非新模型

**选择**: 不在数据库中创建完全独立的表，而是在现有模型上增加可选的增强字段：
- `ModuleDef.elaborated_info: dict | None` — pyslang 提供的 elaboration 元数据
- `InstanceDef.elaborated_path: str` — generate 展开后的完整路径（如 `top.genblk1[0].u_cpu`）
- `SignalDef.resolved_width: str | None` — 参数求值后的实际位宽
- 新增 `ElaborationReport` 模型存储 elaboration 级全局信息

**替代方案**: 创建完全独立的数据表 → 拒绝，增加查询复杂度。增强字段与现有数据自然关联。

### 5. pyslang 版本约束

**选择**: `pyproject.toml` 中约束 `pyslang>=11.0.0,<12.0.0`。v11 是稳定版本，API 较成熟。pyslang 发展快，大版本可能有 API 变化，约束上限避免未来 breakage。

**替代方案**: 不约束上限 `pyslang>=11.0.0` → 拒绝，pyslang v12 可能有 API 变化，导致代码失效。

## Risks / Trade-offs

- **pyslang 构建时间**：pyslang 包含 C++ 扩展，首次 `pip install` 可能需要编译（约 1-3 分钟），或下载预编译 wheel（如果平台支持）→ 在 `pyproject.toml` 中标记 `pyslang` 为可选依赖？不，用户明确要求内置。接受安装时间。
- **内存占用**：pyslang `Compilation` 对象对大型设计（>5000 模块）可能占用大量内存 → 使用后显式释放（`del compilation`），或在子进程中运行 pyslang elaboration
- **pyslang 与 tree-sitter 结果不一致**：同一设计在两种解析器中的表示可能不同（如 pyslang 展开 generate 后模块数量多于 tree-sitter）→ 在 `ElaborationReport` 中记录差异，MCP 工具说明数据来源
- **pyslang 对语法错误的处理**：pyslang 遇到语法错误时可能停止 elaboration（不像 tree-sitter 的容错解析）→ 捕获 pyslang 异常，记录错误但不阻塞 tree-sitter 索引
- **跨平台支持**：pyslang 的预编译 wheel 可能不支持所有平台（如 ARM Linux）→ 在文档中说明，不支持平台回退到纯 tree-sitter 模式

## Open Questions

1. 是否应该在子进程中运行 pyslang elaboration（避免 C++ 扩展的内存泄漏风险）？
2. pyslang 是否支持解析 `include 路径和 `define 宏定义（通过 filelist 传入）？
3. 对于含 UVM 代码的项目，pyslang elaboration 是否会报错（UVM class 不被 elaboration）？
