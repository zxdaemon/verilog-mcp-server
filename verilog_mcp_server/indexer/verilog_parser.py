"""
tree-sitter Verilog/SystemVerilog 解析封装

兼容 tree-sitter 0.23+ API (tree_sitter_language_pack v0.12+)
"""

from __future__ import annotations
import logging
from pathlib import Path
import re
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
        tree = parser.parse(source_text.encode("utf-8"))

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
    tree = parser.parse(source_text.encode("utf-8"))
    return tree, source_text


def get_node_text(node, source_text: str) -> str:
    """获取 AST 节点对应的源码文本（兼容 v0.23+ tree-sitter API）

    tree-sitter 的 byte_range 是 UTF-8 字节偏移；source_text 是 Python str
    （字符索引）。对含多字节字符（中文注释等）的文件，直接按字节偏移切
    str 会错位（每汉字 3 字节），产生错误模块名甚至伪模块。此处统一走
    bytes 空间：encode 后按字节切片再 decode，ASCII 文件输出与旧实现
    逐字节一致，多字节文件修复错位。
    """
    if node is None:
        return ""
    try:
        br = node.byte_range
        source_bytes = source_text.encode("utf-8")
        return source_bytes[br[0]:br[1]].decode("utf-8")
    except (AttributeError, TypeError, IndexError):
        return ""


def get_source_lines(source_text: str) -> list[str]:
    """将源码按行分割"""
    return source_text.splitlines()


def get_node_line(node) -> int:
    """获取节点起始行号（1-indexed）"""
    try:
        pos = node.start_point
        return pos.row + 1
    except (AttributeError, TypeError):
        return 0


def get_node_line_end(node) -> int:
    """获取节点结束行号（1-indexed）"""
    try:
        pos = node.end_point
        return pos.row + 1
    except (AttributeError, TypeError):
        return 0


def for_each_child(node, callback):
    """遍历节点所有子节点"""
    for i in range(node.child_count):
        child = node.child(i)
        callback(child)


def find_child(node, kind_name: str):
    """查找第一个指定 kind 的子节点"""
    for i in range(node.child_count):
        child = node.child(i)
        if child.type == kind_name:
            return child
    return None


def find_children(node, kind_name: str) -> list:
    """查找所有指定 kind 的子节点"""
    results = []
    for i in range(node.child_count):
        child = node.child(i)
        if child.type == kind_name:
            results.append(child)
    return results


def iter_module_body(module_node):
    """遍历 module body 的所有语句，自动展开 module_item 包装（兼容非 ANSI 风格）"""
    for i in range(module_node.child_count):
        child = module_node.child(i)
        if child.type == "module_item":
            for j in range(child.child_count):
                yield child.child(j)
        else:
            yield child


def iter_module_body_deep(module_node):
    """遍历 module body 的所有语句，包括 generate 块内部的语句"""
    for child in _iter_with_generate(module_node, depth=0):
        yield child


_GENERATE_KINDS = {"generate_construct", "generate_region",
                   "conditional_generate_construct",
                   "loop_generate_construct", "generate_block",
                   "if_generate_construct", "case_generate_construct"}


def _iter_with_generate(node, depth):
    if depth > 20:
        return
    for i in range(node.child_count):
        child = node.child(i)
        if child.type == "module_item":
            for j in range(child.child_count):
                gc = child.child(j)
                if gc.type in _GENERATE_KINDS:
                    yield from _iter_with_generate(gc, depth + 1)
                else:
                    yield gc
        elif child.type in _GENERATE_KINDS:
            yield from _iter_with_generate(child, depth + 1)
        else:
            yield child


def recursive_find(node, kind_name: str, max_depth: int = 20) -> list:
    """递归查找所有指定 kind 的节点"""
    results = []
    _recursive_find(node, kind_name, results, 0, max_depth)
    return results


def _recursive_find(node, kind_name: str, results: list, depth: int, max_depth: int):
    if depth > max_depth:
        return
    if node.type == kind_name:
        results.append(node)
    for i in range(node.child_count):
        child = node.child(i)
        _recursive_find(child, kind_name, results, depth + 1, max_depth)


# ── 并行解析支持 ──

def parse_single_file(file_path: str) -> tuple | None:
    """解析单个文件（顶层函数，用于 ProcessPoolExecutor）"""
    result = parse_file(file_path)
    if result:
        return (file_path, result[0], result[1])
    return None
