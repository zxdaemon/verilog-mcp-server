## 数据流变更

### 当前（broken）

```
.f file
  ├─ files ──────→ ProjectScanner.scan() ──→ IndexBuilder ──→ PyslangParser
  ├─ incdirs ────→ [丢弃]
  └─ defines ────→ [丢弃]

config.yaml
  └─ include_dirs ─→ PyslangParser (唯一来源)
```

### 目标（fixed）

```
.f file
  ├─ files ──────→ ProjectScanner.scan() ──→ IndexBuilder ──→ PyslangParser
  ├─ incdirs ────→ ProjectScanner ──→ IndexBuilder ──→ merge ──→ PyslangParser
  └─ defines ────→ ProjectScanner ──→ IndexBuilder ──→ merge ──→ PyslangParser

config.yaml
  └─ include_dirs ─→ merge (优先级更高) ──→ PyslangParser

CLI
  ├─ --filelist ──→ ProjectScanner (指定 .f 文件)
  └─ --top ───────→ config override ──→ PyslangParser
```

## 关键接口变更

### ProjectScanner.scan()

```python
# Before
def scan(self) -> list[Path]: ...

# After
def scan(self) -> tuple[list[Path], list[str], dict[str, str]]:
    """返回 (文件列表, incdirs, defines)"""
```

### IndexBuilder._run_pyslang_elaboration()

```python
# 合并逻辑
all_incdirs = config_incdirs + [d for d in filelist_incdirs if d not in config_incdirs]
all_defines = {**filelist_defines, **config_defines}  # config 覆盖 filelist
```

### CLI

```
verilog-mcp-server -f project.f --top soc --build
```

`-f` 指定 filelist 文件路径，`-t` 指定顶层模块。两者均可通过 config.yaml 配置，CLI 参数优先。
