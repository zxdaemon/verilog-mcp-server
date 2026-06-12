## Why

当前 `.f` 文件（filelist）中的 `+incdir+` 路径被 `ProjectScanner` 解析后直接丢弃，未传递给 `PyslangParser`，导致 pyslang 预处理器无法解析 `` `include `` 指令。同时缺少 CLI 参数来指定 filelist 文件和顶层模块，用户只能通过 config.yaml 配置。

## What Changes

### 1. `+incdir+` 自动传递
- `ProjectScanner.scan()` 返回值扩展：除了文件列表外，还返回 `.f` 文件中收集的 `incdirs` 和 `defines`
- `IndexBuilder._run_pyslang_elaboration()` 将 `.f` 文件的 `incdirs` 合并到 `include_dirs` 配置
- 合并优先级：config 中的 `include_dirs` > `.f` 文件中的 `+incdir+`

### 2. `+define+` 自动传递
- `FilelistParser` 当前忽略 `+define+`，改为提取并返回
- 合并到 `PyslangParser.defines`

### 3. CLI 支持 `--filelist` 和 `--top`
- 新增 `--filelist` / `-f` 参数：指定 `.f` 文件路径
- 新增 `--top` / `-t` 参数：指定顶层模块名
- `--filelist` 解析结果中的文件和 incdirs 合并到索引配置

## Capabilities

### New Capabilities

- `filelist-integration`: `.f` 文件的 `+incdir+`、`+define+` 自动传递给 pyslang 预处理器
- `cli-filelist`: `--filelist` CLI 参数指定 `.f` 文件
- `cli-top-module`: `--top` CLI 参数指定顶层模块

### Modified Capabilities

- `pyslang-elaboration`: 增加从 `.f` 文件收集的 include 路径和宏定义

## Impact

- 修改: `indexer/project_scanner.py` — scan() 返回 incdirs/defines
- 修改: `indexer/builder.py` — 合并 `.f` 的 incdirs/defines 到 pyslang 配置
- 修改: `indexer/filelist_parser.py` — `+define+` 提取
- 修改: `server.py` — 新增 `--filelist`、`--top` CLI 参数
- 修改: `config.yaml` — 文档注释更新
- 修改: `tools/level1_search.py` — `rtl_build_index` tool 支持 filelist/top 参数
- 所有现有接口向后兼容，无破坏性变更
