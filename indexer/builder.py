"""
索引构建器 — 协调各提取器，完成完整索引
"""

from __future__ import annotations
import logging
from typing import Optional

from .project_scanner import ProjectScanner
from .verilog_parser import parse_file, find_child, get_node_text
from .module_extractor import ModuleExtractor
from .port_extractor import PortExtractor
from .instance_extractor import InstanceExtractor
from .signal_extractor import SignalExtractor
from database.index_store import IndexStore

logger = logging.getLogger(__name__)


class IndexBuilder:
    """协调扫描、解析、提取流程，构建完整索引"""

    def __init__(self, config: dict, index_store: IndexStore):
        self.config = config
        self.index_store = index_store
        self.scanner = ProjectScanner(config.get("index", {}))
        self.module_extractor = ModuleExtractor()
        self.port_extractor = PortExtractor()
        self.instance_extractor = InstanceExtractor()
        self.signal_extractor = SignalExtractor()

    def build(self) -> IndexStore:
        """全量构建索引"""
        logger.info("开始构建索引...")
        self.index_store.clear()

        files = self.scanner.scan()
        total_files = len(files)
        parsed_count = 0
        module_count = 0

        for i, file_path in enumerate(files):
            result = parse_file(str(file_path))
            if result is None:
                continue

            tree, source_text = result
            parsed_count += 1

            # 提取所有 module 定义骨架
            modules = self.module_extractor.extract(tree, source_text, str(file_path))
            if not modules:
                continue

            for mod in modules:
                # 找到对应的 module_declaration 节点
                module_node = self._find_module_node(tree, mod.name, source_text)
                if module_node is None:
                    continue

                # 提取端口
                mod.ports = self.port_extractor.extract_from_module(module_node, source_text)

                # module body = module_declaration 的所有子节点（tree-sitter 没有单独 body 包装）
                body_node = module_node

                # 提取信号
                mod.signals = self.signal_extractor.extract_signals(body_node, source_text)

                # 提取例化
                mod.instances = self.instance_extractor.extract_from_module_body(body_node, source_text, str(file_path))

                # 提取 assign
                mod.assignments = self.signal_extractor.extract_assignments(body_node, source_text, str(file_path))

                # 提取 always
                mod.always_blocks = self.signal_extractor.extract_always_blocks(body_node, source_text)

                # 添加到索引
                self.index_store.add_module(mod)
                module_count += 1

            if (i + 1) % 50 == 0:
                logger.info(f"索引进度: {i+1}/{total_files} 文件, {module_count} 模块")

        logger.info(f"索引完成: {parsed_count}/{total_files} 文件, {module_count} 模块")

        # 自动保存缓存
        if self.config.get("cache", {}).get("auto_save", True):
            self.index_store.save()

        return self.index_store

    def _find_module_node(self, tree, module_name: str, source_text: str):
        """在 AST 中查找指定名称的 module_declaration 节点"""
        return self._search_module_node(tree.root_node(), module_name, source_text)

    def _search_module_node(self, node, module_name: str, source_text: str):
        """递归搜索 module_declaration 节点"""
        if node.kind() == "module_declaration":
            header = find_child(node, "module_ansi_header")
            if header:
                for i in range(header.child_count()):
                    child = header.child(i)
                    if child.kind() == "simple_identifier":
                        name = get_node_text(child, source_text)
                        if name == module_name:
                            return node
                # 循环结束未匹配，继续递归
            else:
                # 无 header，尝试从子节点找模块名
                for i in range(node.child_count()):
                    child = node.child(i)
                    if child.kind() == "simple_identifier":
                        name = get_node_text(child, source_text)
                        if name == module_name:
                            return node
            return None

        for i in range(node.child_count()):
            result = self._search_module_node(node.child(i), module_name, source_text)
            if result:
                return result
        return None
