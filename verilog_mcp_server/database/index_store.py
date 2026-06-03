"""
索引存储 — SQLite 后端 + 内存缓存
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from .models import ModuleDef, TypeDef
from .sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)


class IndexStore:
    """模块索引存储，SQLite 持久化 + 内存缓存"""

    def __init__(self, cache_path: Optional[str] = None, db_path: Optional[str] = None):
        # db_path 优先，否则从 cache_path 推导
        resolved_db = db_path or (cache_path if cache_path and cache_path.endswith(".db") else None)
        self._db: Optional[SQLiteBackend] = None
        if resolved_db:
            self._db = SQLiteBackend(resolved_db)
            self.cache_path = resolved_db
        else:
            self.cache_path = cache_path

        # 内存缓存 — 加速热路径查询
        self._cache: dict[str, ModuleDef] = {}
        self._files: dict[str, list[str]] = {}
        self._module_by_file_line: dict[str, dict[int, str]] = {}
        self._signal_index: dict[str, list[tuple[str, str]]] = {}
        self._types: dict[str, TypeDef] = {}

        # 如果有 SQLite，从 DB 加载到缓存
        if self._db:
            self._load_from_db()

    def _load_from_db(self) -> None:
        """从 SQLite 加载所有数据到内存缓存"""
        for mod in self._db.load_all_modules():
            self._add_to_cache(mod)
        for td in self._db.load_all_types():
            self._types[td.name] = td
        logger.info(f"已从 SQLite 加载 {len(self._cache)} 个模块")

    def _add_to_cache(self, module: ModuleDef) -> None:
        """将模块添加到内存缓存（不写 DB）"""
        self._cache[module.name] = module

        self._files.setdefault(module.file_path, [])
        if module.name not in self._files[module.file_path]:
            self._files[module.file_path].append(module.name)

        self._module_by_file_line.setdefault(module.file_path, {})
        for line in range(module.line_start, module.line_end + 1):
            self._module_by_file_line[module.file_path][line] = module.name

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
        if not mod:
            return
        if mod.file_path in self._files:
            self._files[mod.file_path] = [
                n for n in self._files[mod.file_path] if n != module_name
            ]
            if not self._files[mod.file_path]:
                del self._files[mod.file_path]
        if mod.file_path in self._module_by_file_line:
            for line in range(mod.line_start, mod.line_end + 1):
                self._module_by_file_line[mod.file_path].pop(line, None)
        for sig_name, entries in list(self._signal_index.items()):
            self._signal_index[sig_name] = [
                e for e in entries if e[0] != module_name
            ]
            if not self._signal_index[sig_name]:
                del self._signal_index[sig_name]

    # ── Module Operations ──

    def add_module(self, module: ModuleDef) -> None:
        """添加或更新模块定义（写入 SQLite + 缓存）"""
        # 先从缓存移除旧版本
        self._remove_from_cache(module.name)
        # 写入 SQLite
        if self._db:
            self._db.save_module(module)
        # 写入缓存
        self._add_to_cache(module)

    def get_module(self, name: str) -> Optional[ModuleDef]:
        """按名称获取模块（缓存优先）"""
        if name in self._cache:
            return self._cache[name]
        if self._db:
            mod = self._db.load_module(name)
            if mod:
                self._cache[name] = mod
            return mod
        return None

    def get_all_modules(self) -> list[ModuleDef]:
        """获取所有模块"""
        if self._db and not self._cache:
            return self._db.load_all_modules()
        return list(self._cache.values())

    def get_module_names(self) -> list[str]:
        """获取所有模块名"""
        if self._db and not self._cache:
            return self._db.load_module_names()
        return list(self._cache.keys())

    def get_modules_for_file(self, file_path: str) -> list[ModuleDef]:
        """获取某个文件中的所有模块"""
        names = self._files.get(file_path, [])
        return [self._cache[n] for n in names if n in self._cache]

    def has_module(self, name: str) -> bool:
        if name in self._cache:
            return True
        if self._db:
            return self._db.load_module(name) is not None
        return False

    @property
    def module_count(self) -> int:
        if self._db and not self._cache:
            return self._db.get_module_count()
        return len(self._cache)

    # ── Search Operations ──

    def search_modules(self, pattern: str) -> list[ModuleDef]:
        """模糊搜索模块名（大小写不敏感）"""
        if self._db:
            return self._db.search_modules(pattern.lower())
        pattern_lower = pattern.lower()
        results = []
        for name, mod in self._cache.items():
            if pattern_lower in name.lower():
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
                mod = self.get_module(mod_name)
                if mod:
                    results.append((mod, sig_name))
            # 模糊匹配
            if not results:
                entries = self._db.search_signal_index_fuzzy(signal_name.lower(), module_name)
                for mod_name, sig_name in entries:
                    mod = self.get_module(mod_name)
                    if mod:
                        results.append((mod, sig_name))
        else:
            sig_lower = signal_name.lower()
            for mod_name, sig_name in self._signal_index.get(signal_name, []):
                if module_name and mod_name != module_name:
                    continue
                mod = self._cache.get(mod_name)
                if mod:
                    results.append((mod, sig_name))
            if not results:
                for sname, entries in self._signal_index.items():
                    if sig_lower in sname.lower():
                        for mod_name, sig_name in entries:
                            if module_name and mod_name != module_name:
                                continue
                            mod = self._cache.get(mod_name)
                            if mod:
                                results.append((mod, sig_name))
        return results

    def get_module_for_line(self, file_path: str, line: int) -> Optional[ModuleDef]:
        """根据文件路径和行号查找包含该行的模块"""
        file_map = self._module_by_file_line.get(file_path, {})
        name = file_map.get(line)
        return self._cache.get(name) if name else None

    # ── Persistence ──

    def save(self, path: Optional[str] = None) -> None:
        """保存索引（SQLite 自动持久化，此方法为兼容接口）"""
        if self._db:
            logger.info(f"SQLite 索引已持久化 ({len(self._cache)} 个模块)")
            return
        # 无 SQLite 时 fallback 到 JSON
        save_path = path or self.cache_path
        if not save_path:
            return
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
            self._load_from_db()
            return bool(self._cache)
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
        # 清理缓存
        names = list(self._files.get(file_path, []))
        for name in names:
            self._remove_from_cache(name)

    # ── JSON Migration ──

    def migrate_from_json(self, json_path: str) -> bool:
        """从旧版 JSON 缓存迁移数据到 SQLite"""
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

    def clear(self) -> None:
        """清除所有索引"""
        self._cache.clear()
        self._files.clear()
        self._module_by_file_line.clear()
        self._signal_index.clear()
        self._types.clear()
        if self._db:
            self._db.clear_all()
        logger.info("索引已清除")
