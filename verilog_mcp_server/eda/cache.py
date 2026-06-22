"""
EDA 输出缓存机制

缓存策略：
- 缓存目录：.verilog_mcp/yosys_outputs/（可按工具扩展）
- 缓存键：源文件列表的 SHA256 hash
- 缓存命中时直接加载已有 JSON，跳过 EDA 工具调用
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class EdaCache:
    """EDA 工具输出缓存管理器"""

    def __init__(self, cache_dir: str):
        """
        Args:
            cache_dir: 缓存根目录路径，如 ".verilog_mcp/yosys_outputs"
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_files_hash(self, file_paths: list[str]) -> str:
        """计算源文件列表的组合 SHA256 hash

        Args:
            file_paths: RTL 源文件路径列表（需排序以确保一致性）

        Returns:
            组合 hash 字符串
        """
        h = hashlib.sha256()
        for fp in sorted(file_paths):
            h.update(self._hash_file(fp).encode())
        return h.hexdigest()

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """计算单个文件的 SHA256"""
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except OSError:
            # 文件不可读时使用路径作为标识
            h.update(file_path.encode())
        return h.hexdigest()

    def get_cache_path(self, cache_key: str, filename: str) -> Path:
        """获取缓存文件完整路径

        Args:
            cache_key: 源文件组合 hash
            filename: 缓存文件名（如 "yosys_output.json"）

        Returns:
            缓存文件路径
        """
        return self.cache_dir / cache_key / filename

    def check(self, file_paths: list[str], top_module: str) -> Optional[str]:
        """检查缓存是否命中

        Args:
            file_paths: RTL 源文件路径列表
            top_module: 顶层模块名（参与 hash 计算）

        Returns:
            缓存命中时返回 cache_key，未命中返回 None
        """
        # 将 top_module 纳入 hash，因为顶层变化影响综合结果
        all_inputs = list(file_paths) + [f"__top__:{top_module}"]
        cache_key = self.compute_files_hash(all_inputs)
        cache_subdir = self.cache_dir / cache_key
        if cache_subdir.exists() and (cache_subdir / "yosys_output.json").exists():
            logger.info(f"缓存命中: {cache_key[:12]}...")
            return cache_key
        logger.debug(f"缓存未命中: {cache_key[:12]}...")
        return None

    def save(self, cache_key: str, data: dict) -> None:
        """将数据写入缓存

        Args:
            cache_key: 缓存键
            data: 要缓存的数据（存储为 JSON）
        """
        cache_subdir = self.cache_dir / cache_key
        cache_subdir.mkdir(parents=True, exist_ok=True)
        output_path = cache_subdir / "yosys_output.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"缓存已保存: {output_path}")

    def load(self, cache_key: str) -> dict:
        """从缓存加载数据

        Args:
            cache_key: 缓存键

        Returns:
            缓存的字典数据

        Raises:
            FileNotFoundError: 缓存文件不存在
        """
        output_path = self.cache_dir / cache_key / "yosys_output.json"
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
