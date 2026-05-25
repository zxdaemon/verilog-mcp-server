## ADDED Requirements

### Requirement: DomainError 异常层次

`database/errors.py` SHALL 定义以下异常层次：

```
DomainError(RuntimeError)
├── ModuleNotFoundError
├── SignalNotFoundError
├── IndexNotBuiltError
└── AnalysisError
```

所有 `DomainError` 子类 SHALL 接受 message 字符串作为第一个位置参数。

#### Scenario: ModuleNotFoundError 被 tool 捕获

- **WHEN** `_do_get_module(index_store, "nonexistent")` 抛出 `ModuleNotFoundError("模块 'nonexistent' 不存在")`
- **THEN** tool 函数捕获 `DomainError` 并返回 `"❌ 模块 'nonexistent' 不存在"`

#### Scenario: 非 DomainError 异常向上传播

- **WHEN** tool 函数中发生 `KeyError` 或 `AttributeError` 等非 DomainError
- **THEN** 异常不被捕获，由 MCP 框架处理并记录

### Requirement: 替换裸 except Exception

所有 `tools/level*.py` 中的 `except Exception as e` SHALL 替换为 `except DomainError as e`。`analysis/` 层的分析引擎 SHALL 在遇到预期错误时抛出 `DomainError` 子类而非返回 None 或空结果。

#### Scenario: 已知错误返回友好消息

- **WHEN** 用户搜索不存在的模块 `rtl_get_module("foo")`
- **THEN** 返回 `"❌ 模块 'foo' 不存在"`（由 `DomainError` 消息生成）

#### Scenario: 索引未构建时给出提示

- **WHEN** `rtl_get_module("top")` 被调用但索引为空
- **THEN** 返回包含"请先运行 rtl_build_index"的消息
