## Why

当前 MCP 服务器已覆盖 Verilog/SystemVerilog 的核心特性（模块、端口、信号、例化、always 块、generate 块、interface、parameter、typedef），但仍缺少对以下常用 HDL 特性的支持：

- **package / import**：大型 SV 项目普遍使用 package 组织共享类型和常量，当前索引完全忽略 package 声明和 import 语句
- **SVA 断言**：形式验证和仿真验证中大量使用 `assert property`、`sequence`、`property`，当前无法提取这些验证结构
- **function / task**：可综合的 function/task 是常用抽象手段，当前无提取能力
- **defparam**：遗留代码中常见参数重写方式，当前例化提取不处理 defparam 覆盖
- **门级原语**：综合后网表使用 `and`/`or`/`buf` 等原语例化，当前例化提取器仅识别命名模块
- **generate 循环展开**：当前已识别 generate 块结构但不展开 genvar 循环，无法索引循环内生成的信号/例化
- **参数常量传播**：parameter 在模块层次中传递时当前不跟踪实际值，限制了位宽推断和条件分析
- **增量索引**：文件修改后必须全量重建索引，大型项目（>100 模块）体验差
- **并行解析**：tree-sitter 解析为 CPU 密集型，当前单线程串行处理所有文件

## What Changes

- 提取 package 声明、import 语句、package 内部的类型/常量/函数
- 提取 SVA property、sequence、assert 语句及其引用关系
- 提取 function / task 声明、端口、调用关系
- 识别 defparam 参数重写，在例化时合并参数值
- 识别门级原语例化（`and`/`or`/`not`/`buf` 等），纳入例化索引
- 展开 generate for 循环，将循环内信号/例化展开为具名实例
- 实现参数常量传播，在索引中记录参数实际值（支持简单算术表达式求值）
- 实现增量索引：检测文件变更，仅重新解析变更文件并更新索引
- 实现并行解析：使用 `concurrent.futures.ProcessPoolExecutor` 并行调用 tree-sitter

## Capabilities

### New Capabilities

- `package-import`: 提取 package 声明、import 语句、package 内类型/常量/函数，建立 package→module 引用关系
- `sva-assertion`: 提取 SVA property/sequence/assert 语句，支持时序逻辑表达式解析
- `function-task`: 提取 function/task 声明（端口、返回类型、局部变量），建立调用图
- `defparam-override`: 识别 defparam 语句，在例化时合并参数覆盖值
- `gate-level-primitive`: 识别门级原语例化，纳入例化索引和信号连接分析
- `generate-loop-expansion`: 展开 generate for 循环，将 genvar 替换为具体值生成具名信号/例化
- `parameter-propagation`: 在模块层次中传播参数实际值，支持简单算术表达式求值
- `incremental-index`: 检测文件变更（mtime + hash），仅重新解析变更文件并更新索引
- `parallel-parse`: 使用多进程并行调用 tree-sitter 解析文件，加速大型项目索引构建

### Modified Capabilities

- `generate-block-expansion`: 在现有 generate 块遍历基础上增加 genvar 循环展开能力

## Impact

- `database/models.py` 新增 `PackageDef`、`ImportDef`、`SVADef`、`FunctionDef`、`TaskDef`、`PrimitiveDef` 数据类
- `database/index_store.py` 新增对应索引字典和查询方法
- `indexer/` 新增 `package_extractor.py`、`sva_extractor.py`、`function_task_extractor.py`、`primitive_extractor.py`
- `indexer/builder.py` 扩展构建流程，集成新提取器
- `indexer/instance_extractor.py` 扩展门级原语识别和 defparam 处理
- `indexer/verilog_parser.py` 扩展 generate 循环展开逻辑
- `analysis/` 新增 `param_propagator.py` 参数传播引擎
- `server.py` 新增 `rtl_build_index` 的 `incremental` 参数和并行解析支持
- 新增 MCP 工具：`rtl_search_package`、`rtl_search_function`、`rtl_search_task`、`rtl_sva_properties`
- 所有现有 MCP 工具接口保持向后兼容
