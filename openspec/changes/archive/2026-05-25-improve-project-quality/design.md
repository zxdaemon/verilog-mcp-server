## Context

当前项目 5288 行 Python，无测试、无标准打包、无序列化复用。改进涉及 6 个 capability，分布在前端（tools/）、中间层（analysis/）和基础设施（database/、indexer/、项目根）三个区域。关键约束：所有 MCP tool 接口和 indexer 提取器接口保持向后兼容。

## Goals / Non-Goals

**Goals:**
- 建立 Python 项目标准骨架（pyproject.toml、.gitignore）
- 消除 `to_dict()`/`from_dict()` 的 19 处重复实现
- 让所有 tool 业务逻辑可脱离 MCP 框架单独测试
- 统一分析引擎生命周期管理
- 用结构化异常替代裸 `except Exception`
- 将 dataflow.py 从 733 行拆到 <500 行

**Non-Goals:**
- 不修改任何 MCP tool 的名称、参数签名、返回值格式
- 不修改 indexer 提取器的公开接口
- 不添加新功能（增量索引、缓存隔离等 P3 项目留待后续）
- 不改变对外依赖（仍使用 tree-sitter-language-pack + FastMCP + PyYAML）
- 不追求 100% 测试覆盖率，聚焦核心提取器和工具函数

## Decisions

### D1: SerializableModel 使用 `__init_subclass__` 自动生成序列化方法

**选择**: 在 `database/models.py` 定义 `SerializableModel` 基类，通过 `__init_subclass__` 自动收集 dataclass fields，生成通用的 `to_dict()` 和 `from_dict()` 方法。

**备选方案**:
- ❌ `asdict()` 直接返回 `dataclasses.asdict()`：不能处理嵌套对象（如 `list[PortDef]`）
- ❌ 每个 class 保留独立 `to_dict()`：继续重复
- ✅ `__init_subclass__` 自动收集 fields + field metadata 标注嵌套类型

**实现要点**:
```python
from dataclasses import dataclass, field, fields

class SerializableModel:
    @classmethod
    def from_dict(cls, d: dict) -> "SerializableModel":
        """递归反序列化，通过 field metadata 识别嵌套类型"""
        ...

    def to_dict(self) -> dict:
        """递归序列化，field 值为 SerializableModel/list 时自动展开"""
        ...
```

对含嵌套列表的 field（如 `list[PortDef]`），通过 `field(metadata={"elem_type": PortDef})` 标注元素类型。对于基础类型（str、int、bool），自动处理不需要额外标注。

### D2: 三层分离 —— do / format / tool

**选择**: 将当前 `register_tools` 中的内联逻辑拆为三层：

```
┌──────────────────────────────┐
│ @mcp.tool()                  │  ← Level: tool 装饰（在 register_tools 中）
│ def rtl_search_module(...)   │
│   → 调用 _do_search_module() │
│   → 返回 _fmt_ 结果          │
└──────────────────────────────┘
          │
┌──────────────────────────────┐
│ _do_search_module(...)       │  ← Level: 业务逻辑（独立函数，可单测）
│   → IndexStore 查询          │
│   → 返回 list[ModuleDef]     │
└──────────────────────────────┘
          │
┌──────────────────────────────┐
│ _fmt_module_summary(...)     │  ← Level: 格式化（纯函数）
│   → 输入数据对象             │
│   → 返回 Markdown 字符串     │
└──────────────────────────────┘
```

每个 `tools/level*.py` 模块按此模式重构：
- `_do_*()` 函数：纯业务逻辑，接收 IndexStore + 参数，返回数据对象或抛出 DomainError
- `_fmt_*()` 函数：纯格式化，接收数据对象，返回 str
- `register_tools()`：仅创建引擎实例 + 定义 tool 装饰器 + 调用 `_do_*`/`_fmt_*`

`_do_*` 和 `_fmt_*` 作为模块级函数（不加下划线前缀时暴露给测试，实际导出由 `__all__` 控制）。

### D3: 引擎实例在 register_tools 闭包中创建一次

**选择**: 将 Level 3 的分析引擎创建从 tool 函数内部移到 `register_tools` 级别（与 Level 2 已使用的模式一致）：

```python
def register_tools(mcp, index_store):
    # 引擎实例 — 只创建一次
    fsm_detector = FSMDetector(index_store)
    clock_analyzer = ClockAnalyzer(index_store)
    always_classifier = AlwaysClassifier(index_store)

    @mcp.tool()
    def rtl_detect_fsm(module_name: str) -> str:
        result = fsm_detector.detect_fsms(module_name)
        return FSMDetector.format_result(result)
```

`FSMDetector`、`ClockAnalyzer`、`AlwaysClassifier` 本身是无状态的（仅持有 index_store 引用），创建一次复用是安全的。

### D4: DomainError 层次

**选择**: 在 `database/errors.py` 定义三层异常结构：

```
DomainError (基类)
├── ModuleNotFoundError       — 模块不存在（提示模糊搜索结果）
├── SignalNotFoundError       — 信号不存在
├── IndexNotBuiltError        — 索引未构建
└── AnalysisError             — 分析引擎内部错误（保留原始 message）
```

Tool 函数中只捕获 `DomainError`（而非 `except Exception`），将 message 返回给用户。未知异常仍会向上抛出（MCP 框架会记录并返回通用错误信息）。

```python
# Before
except Exception as e:
    return f"❌ 追踪失败: {e}"

# After
except DomainError as e:
    return f"❌ {e}"
```

### D5: dataflow.py 拆分为 fan_in.py + fan_out.py

**选择**:
- `analysis/fan_in.py`：`_trace_fan_in()` 逻辑 + `DataflowTracer.trace_signal()` 入口方法（direction="fan_in"）
- `analysis/fan_out.py`：`_trace_fan_out()` 逻辑 + 共享的 `DataflowTracer.trace_signal()` 入口方法（direction="fan_out"）
- `analysis/dataflow.py` 保留为重新导出模块，从两个子模块 import 并重新导出 `DataflowTracer`，保证现有 import 路径不失效
- 拆分后的子模块都不超过 500 行（fan_in 约 380 行，fan_out 约 250 行，dataflow.py 只剩 30 行重导出）

### D6: pyproject.toml 结构

使用 `setuptools` 作为 build-backend，声明纯 Python 项目（无编译步骤）：

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "verilog-mcp-server"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "tree-sitter-language-pack>=0.12.0",
    "pyyaml>=6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

`requirements.txt` 保留不删除，仅添加注释指向 pyproject.toml。

## Risks / Trade-offs

- **[低] SerializableModel 自动序列化可能遗漏边界情况**: 嵌套 dict、Optional 类型等 → 在 `_do_*` 函数的单元测试中验证序列化往返，确保 `from_dict(to_dict(obj)) == obj`
- **[低] dataflow.py 拆分导致 git blame 断裂**: 通过 `analysis/__init__.py` 和 `dataflow.py` 重新导出保持向后兼容，不影响外部 import
- **[低] `except DomainError` 如覆盖不全会有未捕获异常**: 只替换现有 `except Exception` 位置，而非在新增位置添加异常处理
