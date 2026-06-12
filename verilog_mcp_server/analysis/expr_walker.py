"""
AST 表达式信号引用提取器 (Expression Walker)

用 tree-sitter 解析表达式片段，递归遍历 AST 节点，
提取所有信号引用（simple_identifier / hierarchical_identifier），
过滤关键字和数字常量。
"""

from __future__ import annotations
import re

# Lazy import to avoid loading tree-sitter unless needed
_tree_sitter_lang = None


def _get_parser():
    """延迟加载 tree-sitter-systemverilog parser（模块级单例）"""
    global _tree_sitter_lang
    if _tree_sitter_lang is not None:
        try:
            import tree_sitter_systemverilog as tssv
            from tree_sitter import Language, Parser
            lang = Language(tssv.language())
            parser = Parser(lang)
            return parser
        except ImportError:
            return None

    try:
        import tree_sitter_systemverilog as tssv
        from tree_sitter import Language, Parser
        lang = Language(tssv.language())
        parser = Parser(lang)
        _tree_sitter_lang = parser
        return parser
    except ImportError:
        _tree_sitter_lang = False
        return None


_KEYWORDS = {
    "if", "else", "for", "while", "case", "endcase", "casez", "casex",
    "begin", "end", "repeat", "forever", "posedge", "negedge",
    "or", "and", "not", "xor", "nand", "nor", "xnor",
    "input", "output", "inout", "wire", "reg", "logic",
    "assign", "always", "always_comb", "always_ff", "always_latch",
    "module", "endmodule", "parameter", "localparam",
    "integer", "real", "time", "genvar", "generate", "endgenerate",
    "fork", "join", "disable", "wait", "assert", "assume", "cover",
    "property", "sequence", "signed", "unsigned",
    "typedef", "enum", "struct", "union", "package", "import", "export",
    "function", "endfunction", "task", "endtask",
}

_CONSTANT_RE = re.compile(
    r"^\d+'[bBdDhHoO][0-9a-fA-F_xXzZ?]+$"  # sized literal
    r"|^'[bBdDhHoO][0-9a-fA-F_xXzZ?]+$"    # unsized literal
    r"|^\d+$"                                 # plain integer
)


def _is_constant(name: str) -> bool:
    return bool(_CONSTANT_RE.match(name))


def extract_signal_refs(expr_text: str) -> list[str]:
    """解析表达式文本，返回其中引用的信号名列表（去重保持首次出现顺序）

    如果 tree-sitter 不可用，回退到基于正则的简单提取。
    """
    parser = _get_parser()
    if parser is None:
        return _fallback_extract(expr_text)

    try:
        source = expr_text.encode("utf-8")
        tree = parser.parse(source)
    except (ValueError, AttributeError, TypeError):
        return _fallback_extract(expr_text)

    seen: set[str] = set()
    result: list[str] = []

    def _walk(node, depth: int = 0):
        if depth > 50:
            return
        kind = node.kind()
        if kind in ("simple_identifier", "hierarchical_identifier"):
            name = source[node.start_byte:node.end_byte].decode("utf-8")
            if (name not in seen and name.lower() not in _KEYWORDS
                    and not _is_constant(name)):
                seen.add(name)
                result.append(name)
        for i in range(node.child_count()):
            _walk(node.child(i), depth + 1)

    _walk(tree.root_node)
    return result


def _fallback_extract(expr_text: str) -> list[str]:
    """回退：基于正则的表达式信号提取"""
    seen: set[str] = set()
    result: list[str] = []
    text = expr_text.replace("{", " ").replace("}", " ")
    for token in re.split(r'[\s+\-*/&|^%<>()\[\]:;,!~=]+', text):
        token = token.strip()
        if not token or _is_constant(token) or token.lower() in _KEYWORDS:
            continue
        if token[0].isalpha() or token[0] == "_":
            if token not in seen:
                seen.add(token)
                result.append(token)
    return result
