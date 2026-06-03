"""
索引构建器 — 协调各提取器，完成完整索引
"""

from __future__ import annotations
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from .project_scanner import ProjectScanner
from .verilog_parser import parse_file, find_child, get_node_text
from .module_extractor import ModuleExtractor
from .port_extractor import PortExtractor
from .instance_extractor import InstanceExtractor
from .signal_extractor import SignalExtractor
from .type_extractor import TypeExtractor
from ..database.index_store import IndexStore

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
        self.instance_extractor._index_store = index_store
        self.signal_extractor = SignalExtractor()
        self.type_extractor = TypeExtractor()

    def build(self, incremental: bool = False) -> IndexStore:
        """构建索引

        Args:
            incremental: True 时自动检测变更文件并增量构建，False 时全量重建
        """
        if incremental:
            return self.build_incremental()

        logger.info("开始构建索引...")
        self.index_store.clear()

        files = self.scanner.scan()
        total_files = len(files)
        parsed_count = 0
        module_count = 0

        for i, file_path in enumerate(files):
            fp = str(file_path)
            result = parse_file(fp)
            if result is None:
                continue

            tree, source_text = result
            parsed_count += 1

            modules = self.module_extractor.extract(tree, source_text, fp)
            if not modules:
                continue

            for mod in modules:
                module_node = self._find_module_node(tree, mod.name, source_text)
                if module_node is None:
                    continue

                mod.ports = self.port_extractor.extract_from_module(module_node, source_text)
                body_node = module_node
                mod.signals = self.signal_extractor.extract_signals(body_node, source_text)
                mod.instances = self.instance_extractor.extract_from_module_body(body_node, source_text, fp)
                mod.assignments = self.signal_extractor.extract_assignments(body_node, source_text, fp)
                mod.always_blocks = self.signal_extractor.extract_always_blocks(body_node, source_text)

                drivers_map, loads_map = self.signal_extractor.extract_drivers_and_loads(
                    body_node, source_text, fp)
                for sig in mod.signals:
                    sig.drivers = drivers_map.get(sig.name, [])
                    sig.loads = loads_map.get(sig.name, [])

                for td in self.type_extractor.extract_types(body_node, source_text, fp):
                    self.index_store.add_type(td)

                self.index_store.add_module(mod)
                module_count += 1

            # 更新文件元信息
            self._update_file_meta(fp)

            if (i + 1) % 50 == 0:
                logger.info(f"索引进度: {i+1}/{total_files} 文件, {module_count} 模块")

        logger.info(f"索引完成: {parsed_count}/{total_files} 文件, {module_count} 模块")

        if self.config.get("cache", {}).get("auto_save", True):
            self.index_store.save()

        return self.index_store

    # ── Incremental Build ──

    def build_incremental(self, changed_files: Optional[list[str]] = None) -> IndexStore:
        """增量构建索引，仅重新解析变更文件

        Args:
            changed_files: 指定要重新解析的文件列表。为 None 时自动检测变更。
        """
        logger.info("开始增量构建索引...")

        if not changed_files:
            changed_files = self._detect_changed_files()

        # 同时处理新增和删除的文件
        new_files = self._detect_new_files()
        deleted_files = self._detect_deleted_files()

        all_changed = list(set(changed_files + new_files))

        if not all_changed and not deleted_files:
            logger.info("无文件变更，跳过增量构建")
            return self.index_store
        total_ops = len(all_changed) + len(deleted_files)
        logger.info(f"增量构建: {len(all_changed)} 文件需重新解析, {len(deleted_files)} 文件已删除")

        # 删除已不存在的文件
        for fp in deleted_files:
            self.index_store.remove_file(fp)
            logger.debug(f"已删除文件索引: {fp}")

        # 重新解析变更文件
        module_count = 0
        for i, file_path in enumerate(all_changed):
            self.index_store.remove_file(file_path)
            self._parse_and_index_file(file_path)
            if (i + 1) % 50 == 0:
                logger.info(f"增量进度: {i+1}/{len(all_changed)} 文件")

        # 更新文件元信息
        for fp in all_changed:
            self._update_file_meta(fp)

        logger.info(f"增量构建完成: {len(all_changed)} 文件重新解析, {len(deleted_files)} 文件删除")

        if self.config.get("cache", {}).get("auto_save", True):
            self.index_store.save()

        return self.index_store

    def _detect_changed_files(self) -> list[str]:
        """通过 mtime + SHA256 检测变更文件"""
        if not self.index_store._db:
            return []

        scanned = self.scanner.scan()
        stored_metas = self.index_store._db.get_all_file_metas()
        changed = []

        for file_path in scanned:
            fp = str(file_path)
            stored = stored_metas.get(fp)
            if stored is None:
                # 新文件
                changed.append(fp)
                continue
            try:
                current_mtime = os.path.getmtime(fp)
                if current_mtime != stored["mtime"]:
                    current_sha = self._compute_file_hash(fp)
                    if current_sha != stored["sha256"]:
                        changed.append(fp)
            except OSError:
                changed.append(fp)

        return changed

    def _detect_new_files(self) -> list[str]:
        """检测扫描结果中存在但数据库中不存在的文件"""
        if not self.index_store._db:
            return []

        scanned = {str(fp) for fp in self.scanner.scan()}
        stored = set(self.index_store._db.get_all_file_metas().keys())
        return list(scanned - stored)

    def _detect_deleted_files(self) -> list[str]:
        """检测数据库中存在但文件系统中已不存在的文件"""
        if not self.index_store._db:
            return []

        stored = self.index_store._db.get_all_file_metas()
        return [fp for fp in stored if not Path(fp).exists()]

    def _update_file_meta(self, file_path: str) -> None:
        """更新文件的 mtime 和 SHA256 到数据库"""
        if not self.index_store._db:
            return
        try:
            mtime = os.path.getmtime(file_path)
            sha = self._compute_file_hash(file_path)
            self.index_store._db.set_file_meta(file_path, mtime, sha)
        except OSError:
            pass

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """计算文件 SHA256"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _parse_and_index_file(self, file_path: str) -> int:
        """解析单个文件并将其模块添加到索引，返回模块数"""
        result = parse_file(file_path)
        if result is None:
            return 0

        tree, source_text = result
        modules = self.module_extractor.extract(tree, source_text, file_path)
        if not modules:
            return 0

        count = 0
        for mod in modules:
            module_node = self._find_module_node(tree, mod.name, source_text)
            if module_node is None:
                continue

            mod.ports = self.port_extractor.extract_from_module(module_node, source_text)
            body_node = module_node
            mod.signals = self.signal_extractor.extract_signals(body_node, source_text)
            mod.instances = self.instance_extractor.extract_from_module_body(body_node, source_text, file_path)
            mod.assignments = self.signal_extractor.extract_assignments(body_node, source_text, file_path)
            mod.always_blocks = self.signal_extractor.extract_always_blocks(body_node, source_text)

            drivers_map, loads_map = self.signal_extractor.extract_drivers_and_loads(
                body_node, source_text, file_path)
            for sig in mod.signals:
                sig.drivers = drivers_map.get(sig.name, [])
                sig.loads = loads_map.get(sig.name, [])

            for td in self.type_extractor.extract_types(body_node, source_text, file_path):
                self.index_store.add_type(td)

            self.index_store.add_module(mod)
            count += 1

        return count

    def _find_module_node(self, tree, module_name: str, source_text: str):
        """在 AST 中查找指定名称的 module_declaration 节点"""
        return self._search_module_node(tree.root_node(), module_name, source_text)

    def _search_module_node(self, node, module_name: str, source_text: str):
        """递归搜索 module_declaration 节点"""
        if node.kind() == "module_declaration":
            header = find_child(node, "module_ansi_header")
            if not header:
                header = find_child(node, "module_nonansi_header")
            if header:
                # 在 header 中找模块名（simple_identifier）
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
