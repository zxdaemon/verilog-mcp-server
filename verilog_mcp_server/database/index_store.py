"""
索引存储 — SQLite 后端 + 懒加载内存缓存
"""

from __future__ import annotations
import bisect
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .models import (
    ModuleDef, PortDef, TypeDef,
    PackageDef, FunctionDef,
    ElaboratedInstanceDef, ResolvedSignalDef,
    MacroExpansionInfo, ElaborationReport,
)
from .sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)


class IndexStore:
    """模块索引存储，SQLite 持久化 + 懒加载缓存

    启动时仅加载轻量元数据（名称、文件路径、行号范围、端口名），
    完整模块详情（信号、例化、always 块等）在首次访问时从 SQLite 加载。
    """

    def __init__(self, cache_path: Optional[str] = None, db_path: Optional[str] = None):
        # db_path 优先，否则从 cache_path 推导
        resolved_db = db_path or (cache_path if cache_path and cache_path.endswith(".db") else None)
        self._db: Optional[SQLiteBackend] = None
        if resolved_db:
            self._db = SQLiteBackend(resolved_db)
            self.cache_path = resolved_db
        else:
            self.cache_path = cache_path

        # 内存缓存 — 完整模块对象
        self._cache: dict[str, ModuleDef] = {}
        # 轻量元数据 — 启动时加载: {name: (file_path, line_start, line_end)}
        self._meta: dict[str, tuple[str, int, int]] = {}
        # 文件 → 模块名列表
        self._files: dict[str, list[str]] = {}
        # 文件行号 → 模块映射：{file_path: [(line_start, line_end, module_name), ...]}
        self._module_ranges: dict[str, list[tuple[int, int, str]]] = {}
        self._range_keys: dict[str, list[int]] = {}
        # 信号索引（端口名 + 信号名）
        self._signal_index: dict[str, list[tuple[str, str]]] = {}
        self._types: dict[str, TypeDef] = {}
        self._packages: dict[str, PackageDef] = {}
        self._functions: dict[str, FunctionDef] = {}
        # 已加载完整数据的模块名集合
        self._loaded: set[str] = set()
        # Elaboration 数据内存缓存
        self._elab_cache: dict[str, Any] = {}

        # 如果有 SQLite，从 DB 加载轻量元数据
        if self._db:
            self._load_metadata()

    def _load_metadata(self) -> None:
        """从 SQLite 加载轻量元数据（不加载 JSON 字段）"""
        cur = self._db._conn.execute(
            "SELECT name, file_path, line_start, line_end, ports_json FROM modules"
        )
        for row in cur.fetchall():
            name, file_path, line_start, line_end, ports_json = row
            self._meta[name] = (file_path, line_start, line_end)

            # 文件映射
            self._files.setdefault(file_path, [])
            if name not in self._files[file_path]:
                self._files[file_path].append(name)

            # 行号范围索引
            self._module_ranges.setdefault(file_path, [])
            self._range_keys.setdefault(file_path, [])
            entry = (line_start, line_end, name)
            idx = bisect.bisect_left(self._range_keys[file_path], line_start)
            self._module_ranges[file_path].insert(idx, entry)
            self._range_keys[file_path].insert(idx, line_start)

            # 端口名索引（从 ports_json 提取，不解析完整模块）
            if ports_json:
                try:
                    ports = json.loads(ports_json)
                    for p in ports:
                        pname = p.get("name", "")
                        if pname:
                            self._signal_index.setdefault(pname, [])
                            entry = (name, pname)
                            if entry not in self._signal_index[pname]:
                                self._signal_index[pname].append(entry)
                except (json.JSONDecodeError, TypeError):
                    pass

        # 加载类型
        for td in self._db.load_all_types():
            self._types[td.name] = td

        # 加载 package 和 function
        for pkg in self._db.load_all_packages():
            self._packages[pkg.name] = pkg
        for func in self._db.load_all_functions():
            self._functions[func.name] = func

        logger.info(
            f"已从 SQLite 加载 {len(self._meta)} 个模块元数据, "
            f"{len(self._packages)} 个 package, {len(self._functions)} 个 function"
        )

    def _ensure_loaded(self, name: str) -> Optional[ModuleDef]:
        """确保模块完整数据已加载，返回模块对象"""
        if name in self._cache:
            return self._cache[name]
        if not self._db:
            return None
        mod = self._db.load_module(name)
        if mod:
            self._cache[name] = mod
            self._loaded.add(name)
            # 补充信号索引（仅端口已在 _load_metadata 中加载）
            for sig in mod.signals:
                self._signal_index.setdefault(sig.name, [])
                entry = (mod.name, sig.name)
                if entry not in self._signal_index[sig.name]:
                    self._signal_index[sig.name].append(entry)
        return mod

    def _add_to_cache(self, module: ModuleDef) -> None:
        """将模块添加到内存缓存（不写 DB）"""
        self._cache[module.name] = module
        self._loaded.add(module.name)

        # 更新元数据
        self._meta[module.name] = (module.file_path, module.line_start, module.line_end)

        self._files.setdefault(module.file_path, [])
        if module.name not in self._files[module.file_path]:
            self._files[module.file_path].append(module.name)

        # 行号范围索引
        fp = module.file_path
        self._module_ranges.setdefault(fp, [])
        self._range_keys.setdefault(fp, [])
        entry = (module.line_start, module.line_end, module.name)
        idx = bisect.bisect_left(self._range_keys[fp], module.line_start)
        self._module_ranges[fp].insert(idx, entry)
        self._range_keys[fp].insert(idx, module.line_start)

        # 信号索引
        for sig in module.signals:
            self._signal_index.setdefault(sig.name, [])
            entry = (module.name, sig.name)
            if entry not in self._signal_index[sig.name]:
                self._signal_index[sig.name].append(entry)
        for port in module.ports:
            self._signal_index.setdefault(port.name, [])
            entry = (module.name, port.name)
            if entry not in self._signal_index[port.name]:
                self._signal_index[port.name].append(entry)

    def _remove_from_cache(self, module_name: str) -> None:
        """从内存缓存中移除模块"""
        mod = self._cache.pop(module_name, None)
        self._loaded.discard(module_name)
        meta = self._meta.pop(module_name, None)
        if not mod and not meta:
            return
        file_path = mod.file_path if mod else (meta[0] if meta else None)
        if file_path and file_path in self._files:
            self._files[file_path] = [
                n for n in self._files[file_path] if n != module_name
            ]
            if not self._files[file_path]:
                del self._files[file_path]
        # 从范围索引中移除
        if file_path and file_path in self._module_ranges:
            self._module_ranges[file_path] = [
                (s, e, n) for s, e, n in self._module_ranges[file_path] if n != module_name
            ]
            self._range_keys[file_path] = [s for s, e, n in self._module_ranges[file_path]]
        for sig_name, entries in list(self._signal_index.items()):
            self._signal_index[sig_name] = [
                e for e in entries if e[0] != module_name
            ]
            if not self._signal_index[sig_name]:
                del self._signal_index[sig_name]

    # ── Module Operations ──

    def add_module(self, module: ModuleDef) -> None:
        """添加或更新模块定义（写入 SQLite + 缓存）"""
        self._remove_from_cache(module.name)
        if self._db:
            self._db.save_module(module)
        self._add_to_cache(module)

    def get_module(self, name: str) -> Optional[ModuleDef]:
        """按名称获取模块（懒加载）"""
        return self._ensure_loaded(name)

    def get_all_modules(self) -> list[ModuleDef]:
        """获取所有模块（批量加载，避免 N+1 查询）"""
        if self._db:
            all_mods = self._db.load_all_modules()
            for mod in all_mods:
                self._add_to_cache(mod)
        return list(self._cache.values())

    def get_module_names(self) -> list[str]:
        """获取所有模块名（不触发全量加载）"""
        return list(self._meta.keys())

    def find_instantiators(self, module_name: str) -> list[str]:
        """查找例化了指定模块的所有父模块名（大小写不敏感）"""
        name_lower = module_name.lower()
        results = []
        for mod_name, meta in self._meta.items():
            mod = self._ensure_loaded(mod_name)
            if mod:
                for inst in mod.instances:
                    if inst.module_type.lower() == name_lower:
                        results.append(mod.name)
                        break
        return results

    def get_modules_for_file(self, file_path: str) -> list[ModuleDef]:
        """获取某个文件中的所有模块（懒加载）"""
        names = self._files.get(file_path, [])
        result = []
        for n in names:
            mod = self._ensure_loaded(n)
            if mod:
                result.append(mod)
        return result

    def has_module(self, name: str) -> bool:
        return name in self._meta

    @property
    def module_count(self) -> int:
        return len(self._meta)

    # ── Search Operations ──

    def search_modules(self, pattern: str) -> list[ModuleDef]:
        """模糊搜索模块名（大小写不敏感，不触发全量加载）"""
        if self._db:
            return self._db.search_modules(pattern.lower())
        pattern_lower = pattern.lower()
        results = []
        for name in self._meta:
            if pattern_lower in name.lower():
                mod = self._ensure_loaded(name)
                if mod:
                    results.append(mod)
        results.sort(key=lambda m: (m.name.lower() != pattern_lower, m.name))
        return results

    def search_signals(self, signal_name: str, module_name: Optional[str] = None) -> list[tuple[ModuleDef, str]]:
        """按信号名搜索，可选限定模块范围"""
        results = []
        if self._db:
            # 精确匹配
            entries = self._db.search_signal_index(signal_name, module_name)
            for mod_name, sig_name in entries:
                mod = self._ensure_loaded(mod_name)
                if mod:
                    results.append((mod, sig_name))
            # 模糊匹配
            if not results:
                entries = self._db.search_signal_index_fuzzy(signal_name.lower(), module_name)
                for mod_name, sig_name in entries:
                    mod = self._ensure_loaded(mod_name)
                    if mod:
                        results.append((mod, sig_name))
        else:
            sig_lower = signal_name.lower()
            for mod_name, sig_name in self._signal_index.get(signal_name, []):
                if module_name and mod_name != module_name:
                    continue
                mod = self._ensure_loaded(mod_name)
                if mod:
                    results.append((mod, sig_name))
            if not results:
                for sname, entries in self._signal_index.items():
                    if sig_lower in sname.lower():
                        for mod_name, sig_name in entries:
                            if module_name and mod_name != module_name:
                                continue
                            mod = self._ensure_loaded(mod_name)
                            if mod:
                                results.append((mod, sig_name))
        return results

    def get_module_for_line(self, file_path: str, line: int) -> Optional[ModuleDef]:
        """根据文件路径和行号查找包含该行的模块（二分查找）"""
        ranges = self._module_ranges.get(file_path)
        if not ranges:
            return None
        keys = self._range_keys.get(file_path, [])
        idx = bisect.bisect_right(keys, line) - 1
        if idx < 0:
            return None
        start, end, name = ranges[idx]
        if start <= line <= end:
            return self._ensure_loaded(name)
        return None

    # ── Persistence ──

    def save(self, path: Optional[str] = None) -> None:
        """保存索引（SQLite 自动持久化，此方法为兼容接口）"""
        if self._db:
            logger.info(f"SQLite 索引已持久化 ({len(self._meta)} 个模块)")
            return
        # 无 SQLite 时 fallback 到 JSON
        save_path = path or self.cache_path
        if not save_path:
            return
        # 确保所有模块已加载
        self.get_all_modules()
        data = {
            "modules": {name: mod.to_dict() for name, mod in self._cache.items()},
            "files": self._files,
        }
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"索引已保存到 {save_path} ({len(self._cache)} 个模块)")

    def load(self, path: Optional[str] = None) -> bool:
        """加载索引（SQLite 自动加载，此方法为兼容接口）"""
        if self._db:
            self._load_metadata()
            return bool(self._meta)
        # 无 SQLite 时 fallback 到 JSON
        load_path = path or self.cache_path
        if not load_path or not Path(load_path).exists():
            return False
        with open(load_path) as f:
            data = json.load(f)
        self._cache = {}
        for name, mod_dict in data.get("modules", {}).items():
            self._add_to_cache(ModuleDef.from_dict(mod_dict))
        self._files = data.get("files", {})
        logger.info(f"已从 {load_path} 加载索引 ({len(self._cache)} 个模块)")
        return True

    # ── Incremental Update ──

    def remove_file(self, file_path: str) -> None:
        """删除某文件的所有模块和索引"""
        if self._db:
            self._db.delete_modules_by_file(file_path)
        names = list(self._files.get(file_path, []))
        for name in names:
            self._remove_from_cache(name)

    # ── JSON Migration ──

    def migrate_from_json(self, json_path: str) -> bool:
        """从旧版 JSON 缓存迁移到 SQLite"""
        if not self._db:
            logger.warning("无 SQLite 后端，无法迁移")
            return False
        if not Path(json_path).exists():
            return False
        with open(json_path) as f:
            data = json.load(f)
        count = 0
        for name, mod_dict in data.get("modules", {}).items():
            mod = ModuleDef.from_dict(mod_dict)
            self._db.save_module(mod)
            self._add_to_cache(mod)
            count += 1
        logger.info(f"已从 JSON 迁移 {count} 个模块到 SQLite")
        return True

    def save_json(self, path: str) -> None:
        """导出为 JSON（调试用）"""
        self.get_all_modules()
        data = {
            "modules": {name: mod.to_dict() for name, mod in self._cache.items()},
            "files": self._files,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_json(self, path: str) -> bool:
        """从 JSON 加载（调试用）"""
        if not Path(path).exists():
            return False
        with open(path) as f:
            data = json.load(f)
        self._cache = {}
        for name, mod_dict in data.get("modules", {}).items():
            self._add_to_cache(ModuleDef.from_dict(mod_dict))
        self._files = data.get("files", {})
        return True

    # ── Type Operations ──

    def add_type(self, type_def: TypeDef) -> None:
        self._types[type_def.name] = type_def
        if self._db:
            self._db.save_type(type_def)

    def get_type(self, name: str) -> TypeDef | None:
        if name in self._types:
            return self._types[name]
        if self._db:
            td = self._db.load_type(name)
            if td:
                self._types[name] = td
            return td
        return None

    def get_all_types(self) -> list[TypeDef]:
        if self._db and not self._types:
            return self._db.load_all_types()
        return list(self._types.values())

    # ── Package Operations ──

    def add_package(self, package: PackageDef) -> None:
        self._packages[package.name] = package
        if self._db:
            self._db.save_package(package)

    def get_package(self, name: str) -> Optional[PackageDef]:
        return self._packages.get(name)

    def get_all_packages(self) -> list[PackageDef]:
        return list(self._packages.values())

    def search_packages(self, pattern: str) -> list[PackageDef]:
        """模糊搜索 package 名（大小写不敏感）"""
        pattern_lower = pattern.lower()
        results = [pkg for pkg in self._packages.values() if pattern_lower in pkg.name.lower()]
        results.sort(key=lambda p: (p.name.lower() != pattern_lower, p.name))
        return results

    # ── Function Operations ──

    def add_function(self, func: FunctionDef) -> None:
        self._functions[func.name] = func
        if self._db:
            self._db.save_function(func)

    def get_function(self, name: str) -> Optional[FunctionDef]:
        return self._functions.get(name)

    def get_all_functions(self) -> list[FunctionDef]:
        return list(self._functions.values())

    def search_functions(self, pattern: str) -> list[FunctionDef]:
        """模糊搜索 function/task 名（大小写不敏感）"""
        pattern_lower = pattern.lower()
        results = [func for func in self._functions.values() if pattern_lower in func.name.lower()]
        results.sort(key=lambda f: (f.name.lower() != pattern_lower, f.name))
        return results

    def clear(self) -> None:
        """清除所有索引"""
        self._cache.clear()
        self._meta.clear()
        self._files.clear()
        self._module_ranges.clear()
        self._range_keys.clear()
        self._signal_index.clear()
        self._types.clear()
        self._packages.clear()
        self._functions.clear()
        self._loaded.clear()
        self._elab_cache: dict[str, Any] = {}
        if self._db:
            self._db.clear_all()
        logger.info("索引已清除")

    # ── Elaboration Data Operations ──

    def save_elab_instances(self, instances: list[ElaboratedInstanceDef]) -> None:
        """批量保存 elaborated 实例"""
        if not self._db:
            return
        self._db.clear_elaborated_instances()
        for inst in instances:
            self._db.save_elaborated_instance(inst)
        logger.info(f"已保存 {len(instances)} 个 elaborated 实例")

    def get_elab_instances(self, module_type: str | None = None) -> list[ElaboratedInstanceDef]:
        """获取 elaborated 实例"""
        if not self._db:
            return []
        if module_type:
            return self._db.get_elaborated_instances_by_module(module_type)
        return self._db.get_all_elaborated_instances()

    def save_resolved_signals(self, signals: list[ResolvedSignalDef]) -> None:
        """批量保存参数求值后的信号"""
        if not self._db:
            return
        self._db.clear_resolved_signals()
        for sig in signals:
            self._db.save_resolved_signal(sig)
        logger.info(f"已保存 {len(signals)} 个 resolved 信号")

    def get_resolved_signals(self, module_name: str | None = None) -> list[ResolvedSignalDef]:
        """获取参数求值后的信号"""
        if not self._db:
            return []
        if module_name:
            return self._db.get_resolved_signals_by_module(module_name)
        return self._db.get_all_resolved_signals()

    def save_elab_report(self, report: ElaborationReport) -> int:
        """保存 elaboration 报告"""
        if not self._db:
            return 0
        report_id = self._db.save_elaboration_report(report)
        self._elab_cache["latest_report"] = report
        logger.info(f"已保存 elaboration 报告 (id={report_id})")
        return report_id

    def get_elab_report(self) -> ElaborationReport | None:
        """获取最新 elaboration 报告"""
        if "latest_report" in getattr(self, "_elab_cache", {}):
            return self._elab_cache["latest_report"]
        if not self._db:
            return None
        return self._db.get_latest_elaboration_report()

    def clear_elab_data(self) -> None:
        """清除所有 elaboration 数据"""
        if not self._db:
            return
        self._db.clear_elaborated_instances()
        self._db.clear_resolved_signals()
        self._db.clear_macro_expansions()
        self._db.clear_elaboration_reports()
        if hasattr(self, "_elab_cache"):
            self._elab_cache.clear()
        logger.info("elaboration 数据已清除")

    # ── Yosys Data Operations ──

    def add_yosys_fsm(self, fsm) -> None:
        """添加 Yosys FSM 检测结果"""
        if self._db:
            self._db.save_yosys_fsm(fsm)

    def get_yosys_fsms(self, module_name: Optional[str] = None) -> list:
        """查询 Yosys FSM 列表"""
        if not self._db:
            return []
        return self._db.get_yosys_fsms(module_name)

    def add_yosys_comb_loop(self, loop) -> None:
        """添加 Yosys 组合逻辑环检测结果"""
        if self._db:
            self._db.save_yosys_comb_loop(loop)

    def get_yosys_comb_loops(self) -> list:
        """查询 Yosys 组合逻辑环列表"""
        if not self._db:
            return []
        return self._db.get_yosys_comb_loops()

    def add_yosys_gated_clock(self, clock) -> None:
        """添加 Yosys 门控时钟检测结果"""
        if self._db:
            self._db.save_yosys_gated_clock(clock)

    def get_yosys_gated_clocks(self, module_name: Optional[str] = None) -> list:
        """查询 Yosys 门控时钟列表"""
        if not self._db:
            return []
        return self._db.get_yosys_gated_clocks(module_name)

    def add_yosys_stat(self, stat) -> None:
        """添加 Yosys 资源统计"""
        if self._db:
            self._db.save_yosys_stat(stat)

    def get_yosys_stats(self, module_name: Optional[str] = None) -> list:
        """查询 Yosys 资源统计列表"""
        if not self._db:
            return []
        return self._db.get_yosys_stats(module_name)

    def clear_yosys_data(self) -> None:
        """清除所有 Yosys 数据"""
        if not self._db:
            return
        self._db.clear_yosys_fsms()
        self._db.clear_yosys_comb_loops()
        self._db.clear_yosys_gated_clocks()
        self._db.clear_yosys_stats()
        logger.info("Yosys 数据已清除")
