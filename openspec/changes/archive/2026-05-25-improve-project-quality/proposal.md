## Why

项目处于早期开发阶段，工程基础设施缺失（无 pyproject.toml、无测试、无 .gitignore），工具函数与 MCP 装饰器强耦合无法单独测试，分析引擎中 `to_dict()`/`from_dict()` 序列化逻辑重复 19 处，裸 `except Exception` 覆盖 22 处导致异常被静默吞掉。现在修复成本最低，在功能继续增长前建立正确的基础。

## What Changes

- 添加 `pyproject.toml` 标准化项目元数据、依赖声明和 pytest 配置
- 添加 `.gitignore` 排除 `__pycache__/` 等生成目录
- 为核心提取器（module、port、signal、instance）编写单元测试
- 将 tool 的业务逻辑从 `register_tools` 闭包中提取为独立可测试函数
- 统一 dataclass 的 `to_dict()`/`from_dict()` 序列化为可复用基类
- Level 3 分析引擎初始化提升到 `register_tools` 级别，与 Level 2 保持一致
- 用具体异常类型替代裸 `except Exception`
- 拆分 `dataflow.py`（733 行）为 `fan_in.py` + `fan_out.py`

## Capabilities

### New Capabilities

- `project-packaging`: 标准化项目打包和依赖管理（pyproject.toml、.gitignore）
- `serializable-model`: 统一的 dataclass 序列化基类，消除重复的 to_dict/from_dict
- `testable-tools`: 工具函数从 MCP 闭包中分离，可独立测试
- `engine-lifecycle`: 分析引擎统一在 register_tools 时创建一次，不在每次 tool 调用时重新实例化
- `specific-exceptions`: 用具体异常类型替代裸 except Exception，增加 DomainError 层次
- `file-size-limit`: 大文件拆分标准（>500 行必须拆分，dataflow.py 作为首批目标）

### Modified Capabilities

<!-- 无现有 capability 需要修改 -->

## Impact

- 所有 `indexer/` 提取器的公开接口不变，行为不变
- 所有 MCP tool 接口不变（名称、参数、返回值格式不变）
- `database/models.py` 新增 `SerializableModel` 基类，现有 dataclass 改为继承它
- `analysis/dataflow.py` 拆分为 `analysis/fan_in.py` + `analysis/fan_out.py`（向后兼容重新导出）
- `tools/level*.py` 中将提取独立 `_do_*()` 函数，`register_tools` 仅负责装饰和注册
