## 1. FilelistParser: 提取 `+define+`

- [x] 1.1 `filelist_parser.py` — `+define+` 指令解析：提取 `KEY=VALUE` 或 `KEY`，存入 `result["defines"]` (dict)
- [x] 1.2 `_parse_file()` 返回值增加 `"defines": {}` 键
- [x] 1.3 递归 `-f` 子文件时合并 defines

## 2. ProjectScanner: 返回 filelist 元数据

- [x] 2.1 `scan()` 返回类型改为 `tuple[list[Path], list[str], dict[str,str]]`（files, incdirs, defines）
- [x] 2.2 `_expand_filelist()` 返回 `(files, incdirs, defines)` 三元组
- [x] 2.3 多个 `.f` 文件的 incdirs/defines 去重合并
- [x] 2.4 非 `.f` 路径（目录扫描）不产生 incdirs/defines

## 3. IndexBuilder: 合并 filelist 元数据到 pyslang

- [x] 3.1 `_run_pyslang_elaboration()` 接收 scanner 返回的 incdirs/defines
- [x] 3.2 合并逻辑：config `include_dirs` + filelist `incdirs`（config 优先）
- [x] 3.3 合并逻辑：config `defines` + filelist `defines`（config 优先）
- [x] 3.4 传递合并后的 include_dirs/defines 给 PyslangParser

## 4. CLI: `--filelist` 和 `--top`

- [x] 4.1 `server.py` 新增 `--filelist` / `-f` 参数（nargs="+"，支持多个 .f 文件）
- [x] 4.2 `server.py` 新增 `--top` / `-t` 参数（单个模块名）
- [x] 4.3 `--filelist` 中的文件路径覆盖到 `config["index"]["paths"]`
- [x] 4.4 `--top` 覆盖 `config["pyslang"]["top_module"]`

## 5. MCP Tool: `rtl_build_index` 支持 filelist/top

- [x] 5.1 `rtl_build_index` tool 参数增加 `filelist` 和 `top_module`
- [x] 5.2 builder 接口支持运行时传入 filelist 和 top_module

## 6. 测试

- [x] 6.1 测试 `+incdir+` 自动传递到 PyslangParser
- [x] 6.2 测试 `+define+` 提取和传递
- [x] 6.3 测试 CLI `--filelist` 和 `--top`
- [x] 6.4 测试 config include_dirs 优先级高于 filelist incdirs
