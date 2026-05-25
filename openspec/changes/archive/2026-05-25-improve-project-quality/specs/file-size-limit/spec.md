## ADDED Requirements

### Requirement: 源文件不超过 500 行

项目中每个 `.py` 文件 SHALL 不超过 500 行。超过此阈值 SHALL 按职责拆分为多个模块，通过 `__init__.py` 重新导出保持向后兼容。

#### Scenario: dataflow.py 拆分后每个子模块 < 500 行

- **WHEN** 拆分完成
- **THEN** `analysis/fan_in.py` 行数 < 500
- **AND** `analysis/fan_out.py` 行数 < 500
- **AND** `analysis/dataflow.py` 行数 < 50（仅重新导出）

### Requirement: dataflow.py 拆分为 fan_in.py + fan_out.py

`analysis/dataflow.py` SHALL 拆分为两个模块：

- `analysis/fan_in.py`：包含 `_trace_fan_in()` 方法逻辑和 `DataflowTracer` 类定义
- `analysis/fan_out.py`：包含 `_trace_fan_out()` 方法逻辑
- `analysis/dataflow.py`：从两个子模块 import `DataflowTracer` 并重新导出

`DataflowTracer` 的公开接口（`trace_signal()`、`trace_port_to_internal()`、`format_trace_result()`）SHALL 保持不变。

#### Scenario: 现有 import 路径不失效

- **WHEN** 任何模块执行 `from analysis.dataflow import DataflowTracer`
- **THEN** 成功导入 `DataflowTracer` 类，行为与拆分前一致

#### Scenario: 直接 import 子模块也可用

- **WHEN** 执行 `from analysis.fan_in import DataflowTracer`
- **THEN** 成功导入，与通过 `analysis.dataflow` 导入的类相同
