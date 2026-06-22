"""
EDA 工具适配器抽象基类

所有 EDA 工具适配器（Yosys、Verilator、DC 等）均继承此基类。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BaseEdaAdapter(ABC):
    """EDA 工具适配器抽象基类"""

    def __init__(self, config: Optional[dict] = None):
        """
        Args:
            config: 工具特定配置字典，如 {"yosys_path": "/usr/bin/yosys", "extra_args": []}
        """
        self.config = config or {}
        self._available: Optional[bool] = None

    @abstractmethod
    def check_available(self) -> bool:
        """检测 EDA 工具是否可用（PATH 中是否存在）

        Returns:
            True 表示工具可用
        """
        ...

    @abstractmethod
    def run(self, file_paths: list[str], top_module: str, output_dir: str) -> bool:
        """运行 EDA 工具

        Args:
            file_paths: RTL 源文件路径列表
            top_module: 顶层模块名
            output_dir: 输出结果目录

        Returns:
            True 表示运行成功
        """
        ...

    @abstractmethod
    def parse_output(self, output_dir: str) -> dict:
        """解析 EDA 工具输出

        Args:
            output_dir: 输出结果目录

        Returns:
            解析后的结构化数据字典，各子类定义具体结构
        """
        ...

    def is_available(self) -> bool:
        """返回缓存的可用性检查结果"""
        if self._available is None:
            self._available = self.check_available()
        return self._available
