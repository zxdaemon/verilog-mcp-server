"""
tree-sitter Verilog/SystemVerilog 解析封装

兼容 tree-sitter 0.23+ API (tree_sitter_language_pack v0.12+)
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from tree_sitter_language_pack import get_language, get_parser

logger = logging.getLogger(__name__)

# 语言映射
LANGUAGE_MAP = {
    ".v": "systemverilog",
    ".sv": "systemverilog",
    ".svh": "systemverilog",
}

# 缓存已加载的 parser
_parser_cache: dict[str, object] = {}


def _get_parser(lang_name: str):
    """获取或缓存 tree-sitter parser"""
    if lang_name not in _parser_cache:
        try:
            parser = get_parser(lang_name)
            _parser_cache[lang_name] = parser
            logger.debug(f"加载 parser: {lang_name}")
        except Exception as e:
            logger.error(f"加载 parser '{lang_name}' 失败: {e}")
            raise
    return _parser_cache[lang_name]


def get_language_name(file_path: str) -> str:
    """根据文件扩展名获取 tree-sitter 语言名"""
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "verilog")


def parse_file(file_path: str) -> Optional[tuple[object, str]]:
    """
    解析单个 RTL 文件，返回 (tree, source_text) 元组

    Args:
        file_path: RTL 文件路径

    Returns:
        (tree-sitter Tree, 源码文本) 元组，失败返回 None
    """
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return None

        source_text = path.read_text(encoding="utf-8", errors="replace")

        lang_name = get_language_name(str(path))
        parser = _get_parser(lang_name)
        tree = parser.parse(source_text)

        logger.debug(f"解析成功: {file_path} ({lang_name}, {len(source_text)} chars)")
        return tree, source_text

    except Exception as e:
        logger.warning(f"解析文件失败 {file_path}: {e}")
        return None


def parse_source(source_text: str, lang: str = "systemverilog") -> Optional[tuple[object, str]]:
    """
    解析内存中的源码（用于测试）

    Args:
        source_text: 源码文本
        lang: 语言名 (verilog / systemverilog)

    Returns:
        (tree-sitter Tree, 源码文本) 元组
    """
    parser = _get_parser(lang)
    tree = parser.parse(source_text)
    return tree, source_text


def get_node_text(node, source_text: str) -> str:
    """获取 AST 节点对应的源码文本（兼容 v0.23+ tree-sitter API）"""
    if node is None:
        return ""
    try:
        br = node.byte_range()
        return source_text[br.start:br.end]
    except Exception:
        return ""


def get_source_lines(source_text: str) -> list[str]:
    """将源码按行分割"""
    return source_text.splitlines()


def get_node_line(node) -> int:
    """获取节点起始行号（1-indexed）"""
    try:
        pos = node.start_position()
        return pos.row + 1
    except Exception:
        return 0


def get_node_line_end(node) -> int:
    """获取节点结束行号（1-indexed）"""
    try:
        pos = node.end_position()
        return pos.row + 1
    except Exception:
        return 0


def for_each_child(node, callback):
    """遍历节点所有子节点"""
    for i in range(node.child_count()):
        child = node.child(i)
        callback(child)


def find_child(node, kind_name: str):
    """查找第一个指定 kind 的子节点"""
    for i in range(node.child_count()):
        child = node.child(i)
        if child.kind() == kind_name:
            return child
    return None


def find_children(node, kind_name: str) -> list:
    """查找所有指定 kind 的子节点"""
    results = []
    for i in range(node.child_count()):
        child = node.child(i)
        if child.kind() == kind_name:
            results.append(child)
    return results


def recursive_find(node, kind_name: str, max_depth: int = 20) -> list:
    """递归查找所有指定 kind 的节点"""
    results = []
    _recursive_find(node, kind_name, results, 0, max_depth)
    return results


def _recursive_find(node, kind_name: str, results: list, depth: int, max_depth: int):
    if depth > max_depth:
        return
    if node.kind() == kind_name:
        results.append(node)
    for i in range(node.child_count()):
        child = node.child(i)
        _recursive_find(child, kind_name, results, depth + 1, max_depth)
