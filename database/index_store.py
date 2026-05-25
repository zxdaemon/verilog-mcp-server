"""
内存索引 + JSON 持久化存储
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from .models import ModuleDef

logger = logging.getLogger(__name__)


class IndexStore:
    """模块索引存储，支持内存访问和 JSON 持久化"""

    def __init__(self, cache_path: Optional[str] = None):
        self._modules: dict[str, ModuleDef] = {}       # name → ModuleDef
        self._files: dict[str, list[str]] = {}         # file_path → [module_names]
        self._module_by_file_line: dict[str, dict[int, str]] = {}  # file_path → {line: module_name}
        self._signal_index: dict[str, list[tuple[str, str]]] = {}  # signal_name → [(module_name, signal_def)]
        self.cache_path = cache_path

    # ── Module Operations ──

    def add_module(self, module: ModuleDef) -> None:
        """添加或更新模块定义"""
        self._modules[module.name] = module

        # 文件 → 模块 映射
        self._files.setdefault(module.file_path, [])
        if module.name not in self._files[module.file_path]:
            self._files[module.file_path].append(module.name)

        # 文件行号 → 模块
        self._module_by_file_line.setdefault(module.file_path, {})
        for line in range(module.line_start, module.line_end + 1):
            self._module_by_file_line[module.file_path][line] = module.name

        # 信号索引
        for sig in module.signals:
            self._signal_index.setdefault(sig.name, [])
            entry = (module.name, sig.name)
            if entry not in self._signal_index[sig.name]:
                self._signal_index[sig.name].append(entry)

        # 端口也加入信号索引
        for port in module.ports:
            self._signal_index.setdefault(port.name, [])
            entry = (module.name, port.name)
            if entry not in self._signal_index[port.name]:
                self._signal_index[port.name].append(entry)

    def get_module(self, name: str) -> Optional[ModuleDef]:
        """按名称获取模块"""
        return self._modules.get(name)

    def get_all_modules(self) -> list[ModuleDef]:
        """获取所有模块"""
        return list(self._modules.values())

    def get_module_names(self) -> list[str]:
        """获取所有模块名"""
        return list(self._modules.keys())

    def get_modules_for_file(self, file_path: str) -> list[ModuleDef]:
        """获取某个文件中的所有模块"""
        names = self._files.get(file_path, [])
        return [self._modules[n] for n in names if n in self._modules]

    def has_module(self, name: str) -> bool:
        return name in self._modules

    @property
    def module_count(self) -> int:
        return len(self._modules)

    # ── Search Operations ──

    def search_modules(self, pattern: str) -> list[ModuleDef]:
        """模糊搜索模块名（大小写不敏感）"""
        pattern_lower = pattern.lower()
        results = []
        for name, mod in self._modules.items():
            if pattern_lower in name.lower():
                results.append(mod)
        # 精确匹配优先
        results.sort(key=lambda m: (m.name.lower() != pattern_lower, m.name))
        return results

    def search_signals(self, signal_name: str, module_name: Optional[str] = None) -> list[tuple[ModuleDef, str]]:
        """按信号名搜索，可选限定模块范围"""
        results = []
        sig_lower = signal_name.lower()
        for mod_name, sig_name in self._signal_index.get(signal_name, []):
            if module_name and mod_name != module_name:
                continue
            mod = self._modules.get(mod_name)
            if mod:
                results.append((mod, sig_name))
        # 进一步模糊匹配
        if not results:
            for sname, entries in self._signal_index.items():
                if sig_lower in sname.lower():
                    for mod_name, sig_name in entries:
                        if module_name and mod_name != module_name:
                            continue
                        mod = self._modules.get(mod_name)
                        if mod:
                            results.append((mod, sig_name))
        return results

    def get_module_for_line(self, file_path: str, line: int) -> Optional[ModuleDef]:
        """根据文件路径和行号查找包含该行的模块"""
        file_map = self._module_by_file_line.get(file_path, {})
        name = file_map.get(line)
        return self._modules.get(name) if name else None

    # ── Persistence ──

    def save(self, path: Optional[str] = None) -> None:
        """保存索引到 JSON 文件"""
        save_path = path or self.cache_path
        if not save_path:
            return
        data = {
            "modules": {name: mod.to_dict() for name, mod in self._modules.items()},
            "files": self._files,
        }
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"索引已保存到 {save_path} ({len(self._modules)} 个模块)")

    def load(self, path: Optional[str] = None) -> bool:
        """从 JSON 文件加载索引"""
        load_path = path or self.cache_path
        if not load_path or not Path(load_path).exists():
            return False
        with open(load_path) as f:
            data = json.load(f)
        self._modules = {}
        for name, mod_dict in data.get("modules", {}).items():
            self.add_module(ModuleDef.from_dict(mod_dict))
        self._files = data.get("files", {})
        logger.info(f"已从 {load_path} 加载索引 ({len(self._modules)} 个模块)")
        return True

    def clear(self) -> None:
        """清除所有索引"""
        self._modules.clear()
        self._files.clear()
        self._module_by_file_line.clear()
        self._signal_index.clear()
        logger.info("索引已清除")
