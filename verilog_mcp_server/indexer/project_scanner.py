"""
项目文件扫描器 — 发现 .v / .sv / .svh 文件
"""

from __future__ import annotations
import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

from .filelist_parser import FilelistParser

logger = logging.getLogger(__name__)


class ProjectScanner:
    """扫描项目目录，按扩展名和排除规则过滤 RTL 文件"""

    def __init__(self, config: dict):
        self.paths: list[str] = config.get("paths", [])
        self.extensions: list[str] = config.get("extensions", [".v", ".sv", ".svh"])
        self.exclude_dirs: list[str] = config.get("exclude_dirs", [])
        self.exclude_files: list[str] = config.get("exclude_files", [])

    def scan(self) -> tuple[list[Path], list[str], dict[str, str]]:
        """
        扫描所有配置路径，返回匹配的 RTL 文件列表及 filelist 元数据

        Returns:
            (files, incdirs, defines) 三元组
            - files: RTL 文件列表
            - incdirs: .f 文件中收集的 +incdir+ 路径
            - defines: .f 文件中收集的 +define+ 宏定义
        """
        files: list[Path] = []
        seen: set[str] = set()
        all_incdirs: list[str] = []
        all_defines: dict[str, str] = {}

        for path_str in self.paths:
            base = Path(path_str).expanduser().resolve()
            if not base.exists():
                logger.warning(f"路径不存在: {base}")
                continue
            if base.is_file():
                if self._is_filelist(base):
                    fpaths, incdirs, defines = self._expand_filelist(base)
                    for fpath_str in fpaths:
                        fpath = Path(fpath_str)
                        if str(fpath) not in seen:
                            files.append(fpath)
                            seen.add(str(fpath))
                    for d in incdirs:
                        if d not in all_incdirs:
                            all_incdirs.append(d)
                    all_defines.update(defines)
                    continue
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
        if all_incdirs:
            logger.info(f"filelist include dirs: {len(all_incdirs)} 个")
        if all_defines:
            logger.info(f"filelist defines: {len(all_defines)} 个")
        return files, all_incdirs, all_defines

    def _is_filelist(self, fpath: Path) -> bool:
        """检查是否为 .f 文件列表"""
        return fpath.suffix.lower() == ".f"

    def _expand_filelist(self, fpath: Path) -> tuple[list[str], list[str], dict[str, str]]:
        """解析 .f 文件并返回 (文件路径列表, incdirs, defines)"""
        parser = FilelistParser()
        try:
            result = parser.parse(str(fpath))
            rtl_files = result.get("files", [])
            incdirs = result.get("incdirs", [])
            defines = result.get("defines", {})
            logger.info(f"文件列表 {fpath.name}: {len(rtl_files)} 文件, {len(incdirs)} incdirs, {len(defines)} defines")
            return rtl_files, incdirs, defines
        except Exception as e:
            logger.warning(f"解析文件列表失败 {fpath}: {e}")
            return [], [], {}

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
