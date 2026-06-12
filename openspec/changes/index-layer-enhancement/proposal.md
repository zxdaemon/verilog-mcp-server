## Why

代码库分析报告 (`reports/missing-features-2026-06-04.md`) 识别出 31 项功能缺失，其中索引层 8 项是最基础的解析能力缺口 — 它们导致大量 RTL 信息在解析阶段就丢失了。当前索引器遗漏了非 ANSI 端口位宽、package/import 依赖、SVA 断言、宏定义、EDA 文件列表解析等关键信息。补齐这些地基能力后，上层分析引擎才能产出准确结果。

## What Changes

- **Non-ANSI 端口增强**: 从旧式 Verilog 端口声明中提取位宽和类型（当前只取 name+dir，丢弃了位宽信息）
- **Package/import 解析**: 新增 `package_extractor.py`，解析 package 定义和 import 声明，建立跨文件类型引用
- **SVA 断言提取**: 提取 `assert`/`assume`/`cover`/`property`/`sequence` 等并发断言结构
- **`define` 宏提取**: 提取宏定义名、参数、值文本，支持简单条件编译分支识别
- **EDA 文件列表解析**: 解析 `.f` 文件列表，自动提取 `+incdir+`、`-v`、`-y` 等文件路径
- **Testbench/非综合代码识别**: 区分设计模块和验证模块，标记 `#delay`/`$monitor`/`force`/`release` 等仿真结构

## Capabilities

### New Capabilities

- `non-ansi-port-extraction`: 从旧式 Verilog 端口声明中提取位宽、类型、signed 属性，与 ANSI 路径输出一致的数据结构
- `package-import-parsing`: 解析 package 定义（类型、函数声明）和 import 声明，存储到 `ModuleDef.package_imports`
- `sva-assertion-extraction`: 提取 immediate/concurrent assertion 及 property/sequence 定义，存储到 `ModuleDef.assertions`
- `macro-extraction`: 提取 `define 宏定义（名、参数、值文本），存储到 `FileMeta.defines`，支持 `ifdef/ifndef/elsif/else/endif` 分支结构记录
- `filelist-parsing`: 解析 `.f` 文件列表格式，自动展开 `+incdir+`/`-v`/`-y`/`-f` 等指令，产出文件路径列表
- `testbench-detection`: 识别验证结构（`initial`/`fork`/`$display`/`$monitor`/`force`/`release`/`#delay`），标记模块为 `is_testbench` 或 `has_non_synth`

### Modified Capabilities

- `serializable-model`: 扩展 `ModuleDef`/`SignalDef`/`FileMeta` 数据类，新增 `package_imports`/`assertions`/`defines`/`is_testbench` 字段

## Impact

- **新增文件**: `indexer/package_extractor.py`、`indexer/sva_extractor.py`、`indexer/macro_extractor.py`、`indexer/filelist_parser.py`、`analysis/testbench_detector.py`
- **修改文件**: `indexer/builder.py`（集成新提取器）、`database/models.py`（新增 dataclass 字段）、`indexer/port_extractor.py`（非 ANSI 增强）、`indexer/project_scanner.py`（.f 文件支持）
- **测试**: 每个新提取器需配套单元测试
- **无 breaking changes**: 所有新增字段带默认值，向后兼容
