"""
项目文件扫描器 — 发现 .v / .sv / .svh 文件
"""

from __future__ import annotations
import fnmatch
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProjectScanner:
    """扫描项目目录，按扩展名和排除规则过滤 RTL 文件"""

    def __init__(self, config: dict):
        self.paths: list[str] = config.get("paths", [])
        self.extensions: list[str] = config.get("extensions", [".v", ".sv", ".svh"])
        self.exclude_dirs: list[str] = config.get("exclude_dirs", [])
        self.exclude_files: list[str] = config.get("exclude_files", [])

    def scan(self) -> list[Path]:
        """
        扫描所有配置路径，返回匹配的 RTL 文件列表
        
        Returns:
            list[Path]: 按文件路径排序的 RTL 文件列表
        """
        files: list[Path] = []
        seen: set[str] = set()

        for path_str in self.paths:
            base = Path(path_str).expanduser().resolve()
            if not base.exists():
                logger.warning(f"路径不存在: {base}")
                continue
            if base.is_file():
                if self._matches_ext(base) and str(base) not in seen:
                    files.append(base)
                    seen.add(str(base))
                continue

            # 递归扫描目录
            for fpath in sorted(base.rglob("*")):
                if not fpath.is_file():
                    continue
                if str(fpath) in seen:
                    continue
                if not self._matches_ext(fpath):
                    continue
                if self._is_excluded(fpath):
                    continue
                files.append(fpath)
                seen.add(str(fpath))

        logger.info(f"扫描完成: 共发现 {len(files)} 个 RTL 文件")
        return files

    def _matches_ext(self, fpath: Path) -> bool:
        """检查文件扩展名是否匹配"""
        return fpath.suffix.lower() in self.extensions

    def _is_excluded(self, fpath: Path) -> bool:
        """检查文件是否被排除"""
        # 检查父目录是否在排除列表中
        for parent in fpath.parents:
            if parent.name in self.exclude_dirs:
                return True
        # 检查文件名通配符
        for pattern in self.exclude_files:
            if fnmatch.fnmatch(fpath.name, pattern):
                return True
        return False
