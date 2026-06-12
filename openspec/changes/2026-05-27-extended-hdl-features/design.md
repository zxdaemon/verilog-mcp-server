## Context

当前项目已实现 17 个 capability，覆盖了 Verilog/SystemVerilog 的核心语义分析功能。索引层使用 tree-sitter 解析，分析引擎基于索引数据运行。项目约 8000 行 Python，MCP 工具分三级（搜索/关系/分析）。

本次扩展涉及 9 个新 capability + 1 个修改，覆盖剩余未实现的 HDL 特性。关键约束：
- 所有现有 MCP 工具接口保持向后兼容
- 索引数据模型扩展需兼容现有 JSON 缓存格式（通过 `from_dict`/`to_dict` 自动处理）
- 增量索引和并行解析为基础设施改进，不影响分析结果的正确性

## Goals / Non-Goals

**Goals:**
- 覆盖 package/import、SVA、function/task、defparam、门级原语、generate 循环展开、参数传播 7 个语义特性
- 实现增量索引，文件修改后仅重新解析变更文件
- 实现并行解析，加速大型项目索引构建
- 新增 MCP 工具暴露新提取的语义信息
- 保持所有现有工具接口不变

**Non-Goals:**
- 不实现完整的 SVA 语义求值（仅提取结构，不验证断言真伪）
- 不实现参数传播的完整算术求值器（仅支持加减乘除和常量折叠）
- 不实现跨 package 的类型解析（仅提取声明，不建立类型解析链）
- 不实现 generate 循环的条件展开（仅展开固定次数的 for 循环）
- 不实现分布式并行（仅单机多进程）

## Decisions

### D1: Package 提取模型

**选择**: 在 `database/models.py` 新增 `PackageDef` dataclass：

```python
@dataclass
class PackageDef(SerializableModel):
    name: str
    file_path: str
    line: int
    imports: list[str]          # import pkg::*
    typedefs: list[TypeDef]     # package 内 typedef
    params: list[ParamDef]      # package 内 parameter/localparam
    functions: list[FunctionDef] # package 内 function
```

`ImportDef` 记录 import 语句：
```python
@dataclass
class ImportDef(SerializableModel):
    module_name: str     # 使用 import 的模块名
    package_name: str    # 被导入的包名
    items: list[str]     # 导入的具体项（"*" 表示全部）
    file_path: str
    line: int
```

**备选方案**:
- ❌ 将 package 视为特殊 module：语义不同（package 无端口、无例化）
- ✅ 独立数据模型，与 ModuleDef 平级存入 IndexStore

### D2: SVA 提取范围

**选择**: 提取 SVA 的结构信息，不做语义求值：

```python
@dataclass
class SVAPropertyDef(SerializableModel):
    name: str
    module_name: str
    clocking: str          # @(posedge clk) 等
    disable_iff: str       # disable iff 条件
    body: str              # 原始属性体文本
    file_path: str
    line: int

@dataclass
class SVASquenceDef(SerializableModel):
    name: str
    module_name: str
    body: str
    file_path: str
    line: int

@dataclass
class SVAAssertDef(SerializableModel):
    module_name: str
    label: str             # 可选标签
    property_name: str     # 引用的属性名
    kind: str              # "assert" | "assume" | "cover"
    file_path: str
    line: int
```

**备选方案**:
- ❌ 完整解析 SVA 时序表达式（`##1`, `[*3]`, `[->1]` 等）：复杂度高，当前需求不足
- ✅ 提取结构（名称、时钟、禁用条件、原始文本），留给后续迭代

### D3: Function / Task 提取

**选择**: 在 `indexer/` 新增 `function_task_extractor.py`：

```python
@dataclass
class FunctionDef(SerializableModel):
    name: str
    kind: str              # "function" | "task"
    return_type: str       # function 返回类型，task 为空
    ports: list[PortDef]   # 端口列表
    module_name: str       # 所属模块（或 package）
    file_path: str
    line: int

@dataclass
class FunctionCallInfo(SerializableModel):
    caller: str            # 调用者（模块名或函数名）
    callee: str            # 被调用函数/任务名
    file_path: str
    line: int
```

tree-sitter 节点类型：
- `function_declaration` → function
- `task_declaration` → task
- `function_body_declaration` / `task_body_declaration` → 内部结构

### D4: Defparam 识别与合并

**选择**: 在 `indexer/instance_extractor.py` 中增加 defparam 处理：

1. 扫描模块体中的 `defparam` 语句
2. 解析 `defparam hierarchical_path = value;`
3. 在例化提取完成后，将 defparam 覆盖值合并到对应 `InstanceDef.params`

```python
@dataclass
class DefparamOverride(SerializableModel):
    hierarchical_path: str   # "inst.param_name"
    value: str
    module_name: str         # defparam 所在模块
    file_path: str
    line: int
```

**实现要点**:
- defparam 的 hierarchical_path 可能包含多级（`top.sub.inst.param`）
- 合并时 defparam 值覆盖模块参数默认值
- 存入 IndexStore 供参数传播使用

### D5: 门级原语识别

**选择**: 在 `instance_extractor.py` 中扩展例化识别：

当前仅识别 `module_name instance_name (...)` 模式。门级原语语法：
```verilog
and a1 (out, in1, in2);   // 隐式名称
or  (out, a, b);          // 无名实例
buf b1 [3:0] (out, in);   // 带位宽
```

需要识别的原语关键字：`and`, `or`, `not`, `buf`, `nand`, `nor`, `xor`, `xnor`, `bufif0`, `bufif1`, `notif0`, `notif1`

**实现要点**:
- tree-sitter 将门级原语解析为 `gate_instantiation` 节点
- 原语例化的端口连接为位置连接（无名称）
- 在 `InstanceDef` 中增加 `is_primitive: bool` 标记

### D6: Generate 循环展开

**选择**: 在 `verilog_parser.py` 的 `iter_module_body_deep` 中增加 for-generate 展开：

```python
def expand_generate_for(node, module_text) -> list[dict]:
    """展开 for-generate，返回展开后的虚拟节点列表"""
    # 1. 提取 genvar 初始值、条件、步进
    # 2. 计算循环次数（常量折叠）
    # 3. 对每次迭代，克隆循环体并将 genvar 替换为具体值
    # 4. 返回展开结果
```

**约束**:
- 仅展开循环次数可静态计算的 for-generate（`for(genvar i=0; i<4; i++)`）
- 不展开 while-generate 或条件 generate
- 展开后的信号名格式：`genblk{i}_{signal_name}`
- 展开后的例化名格式：`genblk{i}_{instance_name}`

**备选方案**:
- ❌ 符号化展开（保持 genvar 符号）：下游分析引擎无法处理符号表达式
- ✅ 常量展开，生成具名实体

### D7: 参数常量传播

**选择**: 在 `analysis/` 新增 `param_propagator.py`：

```python
class ParamPropagator:
    def __init__(self, index_store):
        self.index_store = index_store

    def propagate(self, top_module: str) -> dict[str, dict[str, str]]:
        """从顶层模块向下传播参数，返回 {module_path: {param_name: actual_value}}"""
```

**实现要点**:
- 从顶层模块开始，BFS 遍历例化树
- 对每个例化，合并参数来源：模块默认值 < 参数列表值 < defparam 覆盖值
- 支持简单算术表达式求值（`WIDTH * 2`, `DEPTH - 1`）
- 不支持条件表达式（`parameter X = COND ? A : B`）

### D8: 增量索引

**选择**: 在 `indexer/builder.py` 中增加增量构建模式：

```python
class IndexBuilder:
    def build_incremental(self, project_path: str) -> BuildStats:
        """增量构建：仅重新解析 mtime 变更的文件"""
        cached = self._load_cache()
        current_files = self._scan_files(project_path)
        changed = self._detect_changes(cached, current_files)
        # 仅重新解析 changed 文件
        # 合并到现有索引
```

**变更检测策略**:
- 一级：文件 mtime 比较（快速）
- 二级：文件 SHA256 比较（防误判）
- 删除文件：从索引中移除对应模块

**缓存格式扩展**:
- 在 JSON 缓存中增加 `_file_hashes` 字段
- 增加 `_cache_version` 字段用于格式升级检测

### D9: 并行解析

**选择**: 使用 `concurrent.futures.ProcessPoolExecutor`：

```python
from concurrent.futures import ProcessPoolExecutor

def parse_files_parallel(file_paths: list[str], max_workers: int = None) -> list[dict]:
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(parse_single_file, file_paths))
    return results
```

**约束**:
- tree-sitter 对象不可跨进程序列化，每个进程独立初始化 parser
- `parse_single_file` 为顶层函数（可 pickle）
- 默认 `max_workers = min(cpu_count, 8)`
- 小项目（<10 文件）不使用并行（进程启动开销）

### D10: 新增 MCP 工具

在 `tools/` 中新增工具：

```python
# Level 1 — 搜索
@mcp.tool()
def rtl_search_package(pattern: str) -> str:
    """搜索 package 声明"""

@mcp.tool()
def rtl_search_function(pattern: str, module_name: str = None) -> str:
    """搜索 function/task 声明"""

@mcp.tool()
def rtl_sva_properties(module_name: str) -> str:
    """列出模块的 SVA 属性和断言"""
```

```python
# Level 3 — 分析
@mcp.tool()
def rtl_parameter_values(top_module: str) -> str:
    """展示参数在层次结构中的传播值"""
```

## Risks / Trade-offs

- **[中] Generate 循环展开可能生成大量虚拟实例**: `for(i=0; i<1024; i++)` 会生成 1024 个展开实例 → 添加展开上限（默认 256），超出时保留原始 generate 结构
- **[中] 增量索引的缓存一致性**: mtime 可能不变（如 `touch` 未修改内容）→ 二级 SHA256 检测兜底
- **[低] 并行解析的进程开销**: 小项目可能更慢 → 设置阈值（<10 文件串行）
- **[低] 参数传播不支持复杂表达式**: `parameter X = COND ? A : B` 无法求值 → 保留原始文本，标记为 "unresolved"
- **[低] defparam hierarchical_path 解析复杂**: 多级路径可能跨模块边界 → 仅处理当前模块内的 defparam，跨模块 defparam 标记为 warning
