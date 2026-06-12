"""
EDA 文件列表解析器 — 解析 .f 文件列表格式
"""

from __future__ import annotations
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FilelistParser:
    """解析 EDA .f 文件列表，提取文件路径和配置指令"""

    MAX_INCLUDE_DEPTH = 5

    def parse(self, filelist_path: str) -> dict:
        """解析 .f 文件，返回 files, incdirs, defines, lib_files, lib_dirs

        Returns:
            dict with keys: files, incdirs, defines, lib_files, lib_dirs
        """
        return self._parse_file(filelist_path, depth=0)

    def _parse_file(self, filelist_path: str, depth: int = 0) -> dict:
        """解析单个 .f 文件（支持递归 -f）"""
        result: dict[str, list[str] | dict[str, str]] = {
            "files": [],
            "incdirs": [],
            "defines": {},
            "lib_files": [],
            "lib_dirs": [],
        }

        base_dir = os.path.dirname(os.path.abspath(filelist_path))

        try:
            with open(filelist_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (OSError, IOError) as e:
            logger.warning(f"无法读取文件列表 {filelist_path}: {e}")
            return result

        for raw_line in lines:
            line = self._strip_comment(raw_line).strip()
            if not line:
                continue

            tokens = line.split()
            if not tokens:
                continue

            cmd = tokens[0]

            if cmd == "-f":
                if depth < self.MAX_INCLUDE_DEPTH and len(tokens) >= 2:
                    sub_path = self._resolve_path(tokens[1], base_dir)
                    if sub_path:
                        sub_result = self._parse_file(sub_path, depth + 1)
                        for key in ("files", "incdirs", "lib_files", "lib_dirs"):
                            result[key].extend(sub_result[key])
                        result["defines"].update(sub_result["defines"])

            elif cmd.startswith("+incdir+"):
                path = cmd[len("+incdir+"):]
                if path:
                    abs_path = self._resolve_path(path, base_dir)
                    if abs_path and abs_path not in result["incdirs"]:
                        result["incdirs"].append(abs_path)
                for tok in tokens[1:]:
                    abs_path = self._resolve_path(tok, base_dir)
                    if abs_path and abs_path not in result["incdirs"]:
                        result["incdirs"].append(abs_path)

            elif cmd == "-v":
                if len(tokens) >= 2:
                    abs_path = self._resolve_path(tokens[1], base_dir)
                    if abs_path and abs_path not in result["lib_files"]:
                        result["lib_files"].append(abs_path)

            elif cmd == "-y":
                if len(tokens) >= 2:
                    abs_path = self._resolve_path(tokens[1], base_dir)
                    if abs_path and abs_path not in result["lib_dirs"]:
                        result["lib_dirs"].append(abs_path)

            elif cmd.startswith("+define+"):
                define_str = cmd[len("+define+"):]
                if define_str:
                    key, _, value = define_str.partition("=")
                    result["defines"][key] = value

            elif not cmd.startswith("-") and not cmd.startswith("+"):
                # Plain RTL file path
                abs_path = self._resolve_path(tokens[0], base_dir)
                if abs_path and abs_path not in result["files"]:
                    if self._is_rtl_file(abs_path):
                        result["files"].append(abs_path)

        return result

    @staticmethod
    def _resolve_path(path: str, base_dir: str) -> str | None:
        """解析相对路径为绝对路径"""
        if not path:
            return None
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(base_dir, path))

    @staticmethod
    def _strip_comment(line: str) -> str:
        """移除行注释 // 和 #"""
        # // comments
        idx = line.find("//")
        if idx >= 0:
            line = line[:idx]
        # # comments (Perl-style, common in .f files)
        if line.lstrip().startswith("#"):
            return ""
        return line

    @staticmethod
    def _is_rtl_file(path: str) -> bool:
        """检查是否为 RTL 文件"""
        ext = os.path.splitext(path)[1].lower()
        return ext in (".v", ".sv", ".svh", ".vh", ".vlog", ".vo")
