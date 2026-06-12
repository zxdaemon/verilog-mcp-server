## Context

当前索引器（`indexer/`）基于 tree-sitter 解析 RTL，已处理 ANSI 端口、信号、例化、类型。但非 ANSI 端口位宽、package/import、SVA 断言、宏定义、仿真结构检测等能力空缺。这些是分析引擎的"地基"——缺失它们会导致上层分析（时钟域、FSM、数据流）信息不完整。

本项目使用 spec-driven schema，所有新能力需要独立的 spec 文件。

## Goals / Non-Goals

**Goals:**
- 补齐非 ANSI 端口声明的位宽/类型/属性提取
- 解析 package 定义和 import 声明，建立模块级依赖关系
- 提取 SVA 断言（immediate + concurrent），支持 property/sequence
- 提取 `define 宏定义，记录 `ifdef/`ifndef 条件编译分支
- 解析 EDA 文件列表（`.f`），自动展开文件路径
- 标记仿真专用结构和 testbench 模块

**Non-Goals:**
- 宏表达式求值/展开（太复杂，需要完整的预处理器）
- generate 块内的参数常量折叠
- 形式验证级别的 SVA 语义分析
- 增量构建中的宏变更检测
- Lint 规则、时序分析、CDC 详情等 Section 2-5 的项目（后续 change）

## Decisions

### 1. 非 ANSI 端口：在 port_extractor 内增强，不新建提取器

非 ANSI 端口声明语法：`output [7:0] data;` 在模块体内声明，位宽信息在 `output_declaration`/`input_declaration`/`inout_declaration` AST 节点中。当前 `port_extractor.py` 的非 ANSI 路径只取 name+dir。

**方案**: 对非 ANSI 模块头，先收集端口名→方向映射，再扫描 `module_item` 中的 wire/reg 声明匹配端口名，从中提取类型和位宽。不用单独的提取器。

### 2. Package/Import：独立提取器，按文件存储

Package 定义是全局的（一个 package 可被多个文件 import）。Import 声明是模块级的。

**方案**: 新建 `package_extractor.py`。Package 定义存储到 `FileMeta.package_defs`（按文件）。Import 声明存储到 `ModuleDef.package_imports`（按模块）。跨文件类型引用通过 `IndexStore` 查询。

### 3. SVA 断言：独立提取器，存储到 ModuleDef

SVA 包含 immediate assertion（`assert(...)` 在过程块中）和 concurrent assertion（`assert property(...)` 在模块级别）。AST 节点 `assertion_item`/`property_declaration`/`sequence_declaration`。

**方案**: 新建 `sva_extractor.py`。提取断言类型、表达式文本、pass/fail 动作语句。存储到 `ModuleDef.assertions: list[SvaDef]`。

### 4. 宏提取：文件级独立提取器

`define 宏是文件级的，影响后续解析。`ifdef/`ifndef 条件编译分支需要记录但不求值（无完整预处理器）。

**方案**: 新建 `macro_extractor.py`。从 `text_macro_definition`/`text_macro_usage` AST 节点提取（tree-sitter 在 preprocessor 模式下）。存储到 `FileMeta.defines: list[MacroDef]` 和 `FileMeta.conditionals: list[ConditionalBranch]`。

### 5. 文件列表解析：ProjectScanner 集成

`.f` 文件是业界常用的文件列表格式，包含 `+incdir+`、`-v`、`-y`、`-f` 等指令。

**方案**: 新建 `filelist_parser.py`。`ProjectScanner.scan()` 检测 `.f` 文件并自动展开。`+incdir+` 路径加入 include 搜索列表（供宏提取使用）。

### 6. Testbench 检测：轻量级标记

不需要完整的验证框架识别，只需标记包含仿真/验证结构的模块。

**方案**: 在 `signal_extractor.py` 中扩展：遍历 `module_body` 时检测 `initial_construct`/`fork_block`/`system_tf_call`（$display/$monitor）/`force_statement`/`release_statement`/`delay_control`（#delay）。设置 `ModuleDef.is_testbench: bool` 和 `ModuleDef.has_non_synth_constructs: bool`。

## Risks / Trade-offs

- **宏不求值**：不展开宏意味着条件编译分支的实际选择未知，影响下游分析的完整性。但实现完整预处理器远超本次范围，记录分支结构已是最佳折中
- **非 ANSI 端口匹配**：通过变量名匹配端口名可能漏掉声明位于其他位置的极端情况，但覆盖了 95%+ 的实际用法
- **Package 跨文件引用**：当前无完整的类型解析链，package 内的类型定义仅在文本层面提取，不解析类型表达式
