"""
Parameter Propagation Engine

从顶层模块开始 BFS 遍历例化树，传播参数实际值。

核心能力:
- BFS traversal from top module through instantiation tree
- 通过例化时 #(.PARAM(value)) 覆盖参数值 (InstanceDef.param_overrides)
- 使用默认参数值
- 简单算术表达式求值 (二进制运算, $clog2, 位宽选择)
- 标记未解析参数
- defparam 支持 (最高优先级)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..database.index_store import IndexStore


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────


@dataclass
class ResolvedParam:
    """已传播解析的参数结果"""

    name: str
    default_value: str | None = None
    resolved_value: str | None = None
    is_resolved: bool = False
    depth: int = 0
    path: str = ""
    override_source: str = "default"  # default / instance / defparam


# ──────────────────────────────────────────────
# Expression Evaluator
# ──────────────────────────────────────────────


# Verilog number literal pattern: [size]'[s][bohdBODH]value
_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        (\d+)\s*'\s*([sS]?)\s*([bBoOdDhH])\s*([0-9a-fA-F_xzXZ?_]+)   # sized: 8'd255, 16'hff, 'hFF
        |
        (\d+)\s*'\s*([sS]?)\s*([bBoOdDhH])\s*([0-9a-fA-F_xzXZ?_]+)   # alternate pattern
        |
        '([sS]?)\s*([bBoOdDhH])\s*([0-9a-fA-F_xzXZ?_]+)               # unsized: 'hFF, 'd5
        |
        (\d+)                                                          # plain decimal: 255
    )
    """,
    re.VERBOSE,
)

_IDENTIFIER_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_$]*\b")
_FUNCTION_PATTERN = re.compile(r"\$(\w+)\s*\(([^)]*)\)")


def _parse_verilog_number(text: str) -> int | None:
    """Parse a Verilog number literal into an integer.
    Returns None if the number contains X/Z/? bits.
    """
    text = text.strip()
    if not text:
        return None

    # Pattern: [size]'[s][base]value
    m = re.match(
        r"^(?:(\d+))?\s*'([sS])?\s*([bBoOdDhH])\s*([0-9a-fA-F_xzXZ?_]+)$", text
    )
    if m:
        size_str, signed_str, base_char, value_str = m.groups()
        base = base_char.lower()
        base_map = {"b": 2, "o": 8, "d": 10, "h": 16}
        radix = base_map.get(base, 10)

        if "x" in value_str.lower() or "z" in value_str.lower() or "?" in value_str.lower():
            return None  # can't resolve X/Z

        try:
            val = int(value_str, radix)
        except ValueError:
            return None

        if size_str and int(size_str) > 0:
            bit_width = int(size_str)
            # Sign-extend if signed
            if signed_str:
                if val & (1 << (bit_width - 1)):
                    val -= 1 << bit_width
        return val

    # Plain decimal
    m = re.match(r"^(\d+)$", text)
    if m:
        return int(m.group(1))

    return None


def _eval_clog2(arg: int | None) -> int | None:
    """$clog2(n) = ceil(log2(n)). Returns None for invalid input."""
    if arg is None or arg <= 0:
        return None
    if arg == 1:
        return 0
    return math.ceil(math.log2(arg))


def _eval_function(name: str, arg: int | None) -> int | None:
    """Evaluate a known SystemVerilog function."""
    fn_name = name.lower()
    if fn_name == "clog2":
        return _eval_clog2(arg)
    elif fn_name == "bits":
        # $bits(value) - for simplicity return arg if it's an int
        return arg
    return None


# Precedence table: binary operators
_BIN_OP_PRECEDENCE: dict[str, int] = {
    "**": 10,
    "*": 9,
    "/": 9,
    "%": 9,
    "+": 8,
    "-": 8,
    "<<": 7,
    ">>": 7,
    ">>>": 7,
    "<<<": 7,
    "<": 6,
    "<=": 6,
    ">": 6,
    ">=": 6,
    "==": 5,
    "!=": 5,
    "===": 5,
    "!==": 5,
    "&": 4,
    "^": 3,
    "|": 2,
    "&&": 1,
    "||": 0,
}

_BIN_OP_FUNCS: dict[str, Any] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a // b if b != 0 else None,
    "%": lambda a, b: a % b if b != 0 else None,
    "**": lambda a, b: a**b,
    "<<": lambda a, b: a << b,
    ">>": lambda a, b: a >> b,
    ">>>": lambda a, b: a >> b if a >= 0 else (a >> b) | (~((1 << (a.bit_length())) - 1) >> b),
    "<<<": lambda a, b: a << b,
    "&": lambda a, b: a & b,
    "|": lambda a, b: a | b,
    "^": lambda a, b: a ^ b,
    "&&": lambda a, b: 1 if (a != 0 and b != 0) else 0,
    "||": lambda a, b: 1 if (a != 0 or b != 0) else 0,
    "==": lambda a, b: 1 if a == b else 0,
    "!=": lambda a, b: 1 if a != b else 0,
    "<": lambda a, b: 1 if a < b else 0,
    "<=": lambda a, b: 1 if a <= b else 0,
    ">": lambda a, b: 1 if a > b else 0,
    ">=": lambda a, b: 1 if a >= b else 0,
}


def _tokenize_expr(expr: str) -> list[str]:
    """Tokenize a Verilog expression into tokens.

    Handles: identifiers, numbers, operators, parentheses, commas.
    """
    tokens: list[str] = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in " \t\n\r":
            i += 1
            continue
        # Multi-character operators
        if expr[i : i + 4] == ">>>=":
            tokens.append(">>>=")
            i += 4
        elif expr[i : i + 3] in (">>>", "<<<", "===", "!==", "**"):
            tokens.append(expr[i : i + 3])
            i += 3
        elif expr[i : i + 2] in (
            "<<",
            ">>",
            "<=",
            ">=",
            "==",
            "!=",
            "&&",
            "||",
            "++",
            "--",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "&=",
            "|=",
            "^=",
            "~&",
            "~|",
            "~^",
            "^~",
        ):
            tokens.append(expr[i : i + 2])
            i += 2
        elif ch in "(){}[],;:#?@":
            tokens.append(ch)
            i += 1
        elif ch in "+-*/%~&|^!<>=`":
            tokens.append(ch)
            i += 1
        elif ch.isdigit() or ch == "'":
            # Number literal (could start with digit or ')
            start = i
            if ch == "'":
                i += 1
            else:
                while i < len(expr) and (expr[i].isalnum() or expr[i] in "'_."):
                    i += 1
            tokens.append(expr[start:i])
        elif ch.isalpha() or ch == "_" or ch == "$":
            start = i
            while i < len(expr) and (expr[i].isalnum() or expr[i] in "_$"):
                i += 1
            tokens.append(expr[start:i])
        elif ch == ".":
            # Could be hierarchical path or just a dot
            tokens.append(".")
            i += 1
        else:
            # Skip unknown characters
            i += 1
    return tokens


def _eval_simple_expr(
    token_str: str, params: dict[str, str], _depth: int = 0
) -> tuple[str, bool]:
    """Evaluate a simple Verilog expression containing identifiers,
    numbers, basic arithmetic, and $clog2/$bits.

    Returns (resolved_value_string, is_fully_resolved).
    """
    # Protection against infinite recursion
    if _depth > 20:
        return token_str, False

    expr = token_str.strip()
    if not expr:
        return expr, True

    # Check if it's a Verilog number literal
    num_val = _parse_verilog_number(expr)
    if num_val is not None:
        return str(num_val), True

    # Check if it's a single identifier
    if _IDENTIFIER_PATTERN.fullmatch(expr):
        # Look up in known params
        if expr in params:
            val = params[expr]
            # Try to resolve it further
            if val != expr:
                return _eval_simple_expr(val, params, _depth + 1)
            return val, False  # circular or unresolvable
        return expr, False

    # Check for $function(...)
    func_match = re.match(r"^\$(\w+)\((.*)\)$", expr)
    if func_match:
        func_name = func_match.group(1)
        inner = func_match.group(2).strip()
        arg_val, arg_resolved = _eval_simple_expr(inner, params, _depth + 1)
        if arg_resolved:
            arg_int = int(arg_val)
            result = _eval_function(func_name, arg_int)
            if result is not None:
                return str(result), True
        # If arg contains unresolved params, return expression as-is
        return expr, False

    # Handle ternary: cond ? true_expr : false_expr
    ternary_match = _match_ternary(expr)
    if ternary_match:
        cond, true_branch, false_branch = ternary_match
        cond_val, cond_resolved = _eval_simple_expr(cond, params, _depth + 1)
        if cond_resolved:
            cond_int = int(cond_val)
            if cond_int:
                return _eval_simple_expr(true_branch, params, _depth + 1)
            else:
                return _eval_simple_expr(false_branch, params, _depth + 1)
        return expr, False

    # Handle concatenation: {a, b, c}
    concat_match = re.match(r"^\{([^}]+)\}$", expr)
    if concat_match:
        inner = concat_match.group(1)
        # Split by commas respecting nested braces
        parts = _split_comma_outside_braces(inner)
        if not parts:
            return "0", True
        result_bits = 0
        total_bits = 0
        all_resolved = True
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Check for replication: {n{...}}
            repl_match = re.match(r"^(\d+)\{", part)
            if repl_match:
                repl_count = int(repl_match.group(1))
                inner_repl = part[part.index("{") + 1 : -1]
                pv, pr = _eval_simple_expr(inner_repl, params, _depth + 1)
                if pr:
                    for _ in range(repl_count):
                        pi = int(pv)
                        nbits = pi.bit_length() or 1
                        result_bits = (result_bits << nbits) | pi
                        total_bits += nbits
                else:
                    all_resolved = False
            else:
                pv, pr = _eval_simple_expr(part, params, _depth + 1)
                if pr:
                    pi = int(pv)
                    nbits = pi.bit_length() or 1
                    result_bits = (result_bits << nbits) | pi
                    total_bits += nbits
                else:
                    all_resolved = False
        if all_resolved:
            return str(result_bits), True
        return expr, False

    # Handle bit-select: sig[bit]
    bit_sel_match = re.match(r"^(\w+)\[(\d+)\]$", expr)
    if bit_sel_match:
        sig = bit_sel_match.group(1)
        index = int(bit_sel_match.group(2))
        if sig in params:
            val, resolved = _eval_simple_expr(params[sig], params, _depth + 1)
            if resolved:
                ival = int(val)
                return str((ival >> index) & 1), True
        return expr, False

    # Handle part-select: sig[hi:lo]
    part_sel_match = re.match(r"^(\w+)\[(\d+):(\d+)\]$", expr)
    if part_sel_match:
        sig = part_sel_match.group(1)
        hi = int(part_sel_match.group(2))
        lo = int(part_sel_match.group(3))
        if sig in params:
            val, resolved = _eval_simple_expr(params[sig], params, _depth + 1)
            if resolved:
                ival = int(val)
                width = hi - lo + 1
                return str((ival >> lo) & ((1 << width) - 1)), True
        return expr, False

    # Binary expression: tokenize and evaluate with precedence
    try:
        result = _eval_binop_expr(expr, params, _depth)
        if result is not None:
            return result
    except Exception:
        pass

    return expr, False


def _split_comma_outside_braces(s: str) -> list[str]:
    """Split by commas, respecting nested {}."""
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch == "{":
            depth += 1
            current += ch
        elif ch == "}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current:
        parts.append(current)
    return parts


def _match_ternary(expr: str) -> tuple[str, str, str] | None:
    """Match cond ? true_expr : false_expr at top level."""
    expr = expr.strip()
    q_pos = -1
    depth = 0
    for i, ch in enumerate(expr):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "?" and depth == 0:
            q_pos = i
            break
    if q_pos < 0:
        return None

    cond = expr[:q_pos]
    rest = expr[q_pos + 1 :]

    # Find the ':' at top level
    col_pos = -1
    depth = 0
    for i, ch in enumerate(rest):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == ":" and depth == 0:
            col_pos = i
            break
    if col_pos < 0:
        return None

    true_branch = rest[:col_pos].strip()
    false_branch = rest[col_pos + 1 :].strip()
    return cond.strip(), true_branch, false_branch


def _eval_binop_expr(
    expr: str, params: dict[str, str], depth: int
) -> tuple[str, bool] | None:
    """Evaluate a binary operator expression using precedence climbing."""
    tokens = _tokenize_expr(expr)
    if not tokens:
        return None

    # If there's only one token, evaluate it directly
    if len(tokens) == 1:
        return _eval_simple_expr(tokens[0], params, depth + 1)

    # Remove outer parentheses
    while len(tokens) >= 2 and tokens[0] == "(" and _matching_paren(tokens) == len(tokens) - 1:
        tokens = tokens[1:-1]

    if len(tokens) == 1:
        return _eval_simple_expr(tokens[0], params, depth + 1)

    # Parse with precedence climbing
    result, ok, _next_pos = _parse_expression(tokens, 0, params, depth)
    return result, ok


def _matching_paren(tokens: list[str]) -> int:
    """Find matching closing paren for tokens starting at 0."""
    if not tokens or tokens[0] != "(":
        return -1
    depth = 1
    for i in range(1, len(tokens)):
        if tokens[i] == "(":
            depth += 1
        elif tokens[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _parse_expression(
    tokens: list[str], pos: int, params: dict[str, str], depth: int
) -> tuple[str, bool]:
    """Parse expression using precedence climbing."""
    # Parse primary (term)
    term, ok, next_pos = _parse_primary(tokens, pos, params, depth)
    min_prec = -1  # lowest precedence

    while next_pos < len(tokens):
        token = tokens[next_pos]
        if token == ")":
            break
        if token in ("?", ":", "#", ".", ","):
            break

        if token in _BIN_OP_PRECEDENCE:
            prec = _BIN_OP_PRECEDENCE[token]
            if prec <= min_prec:
                break

            # Consume operator
            op = token
            next_pos += 1

            # Parse right-hand side
            rhs, ok2, next_pos = _parse_primary(tokens, next_pos, params, depth)
            if not ok2:
                return term, False, next_pos

            # Try to evaluate
            op_func = _BIN_OP_FUNCS.get(op)
            if ok and ok2 and op_func:
                try:
                    a = int(term) if term.lstrip("-").isdigit() or (term.startswith("-") and term[1:].isdigit()) else int(term)
                    b = int(rhs) if rhs.lstrip("-").isdigit() or (rhs.startswith("-") and rhs[1:].isdigit()) else int(rhs)
                    res = op_func(a, b)
                    if res is not None:
                        term = str(res)
                        ok = True
                    else:
                        ok = False
                except (ValueError, TypeError):
                    term = f"({term} {op} {rhs})"
                    ok = False
            else:
                term = f"({term} {op} {rhs})"
                ok = False
        elif token == "(":
            # Function call or parenthesized expression
            sub_expr, ok, next_pos = _parse_expression(
                tokens, next_pos + 1, params, depth
            )
            if next_pos < len(tokens) and tokens[next_pos] == ")":
                next_pos += 1
        else:
            break

    return term, ok, next_pos


def _parse_primary(
    tokens: list[str], pos: int, params: dict[str, str], depth: int
) -> tuple[str, bool, int]:
    """Parse a primary expression."""
    if pos >= len(tokens):
        return "", False, pos

    token = tokens[pos]

    # Unary minus
    if token == "-" and pos + 1 < len(tokens):
        next_token = tokens[pos + 1]
        if _is_unary_op_context(tokens, pos):
            val, ok, next_pos = _parse_primary(tokens, pos + 1, params, depth)
            if ok:
                try:
                    return str(-int(val)), True, next_pos
                except (ValueError, TypeError):
                    return f"(-{val})", False, next_pos
            return f"(-{val})", False, next_pos

    # Unary ~ (bitwise NOT)
    if token == "~" and pos + 1 < len(tokens):
        val, ok, next_pos = _parse_primary(tokens, pos + 1, params, depth)
        if ok:
            try:
                return str(~int(val)), True, next_pos
            except (ValueError, TypeError):
                return f"(~{val})", False, next_pos
        return f"(~{val})", False, next_pos

    # Unary ! (logical NOT)
    if token == "!" and pos + 1 < len(tokens):
        val, ok, next_pos = _parse_primary(tokens, pos + 1, params, depth)
        if ok:
            try:
                return str(1 if int(val) == 0 else 0), True, next_pos
            except (ValueError, TypeError):
                return f"(!{val})", False, next_pos
        return f"(!{val})", False, next_pos

    # Parenthesized expression
    if token == "(":
        sub_result, ok, next_pos = _parse_expression(
            tokens, pos + 1, params, depth
        )
        if next_pos < len(tokens) and tokens[next_pos] == ")":
            next_pos += 1
        return sub_result, ok, next_pos

    # Function call: $function(args)
    if token.startswith("$") and pos + 1 < len(tokens) and tokens[pos + 1] == "(":
        func_name = token[1:]
        # Find matching paren
        open_pos = pos + 1
        close_pos = _find_matching_paren(tokens, open_pos)
        if close_pos > open_pos:
            arg_tokens = tokens[open_pos + 1 : close_pos]
            arg_str = "".join(arg_tokens)
            arg_val, arg_ok = _eval_simple_expr(arg_str, params, depth + 1)
            if arg_ok:
                arg_int = int(arg_val)
                result = _eval_function(func_name, arg_int)
                if result is not None:
                    return str(result), True, close_pos + 1
            return f"${func_name}({arg_val})", False, close_pos + 1
        return f"${func_name}(...)", False, close_pos + 1

    # Number or identifier
    result, ok = _eval_simple_expr(token, params, depth + 1)
    return result, ok, pos + 1


def _find_matching_paren(tokens: list[str], open_pos: int) -> int:
    """Find the closing parenthesis matching the one at open_pos."""
    depth = 0
    for i in range(open_pos, len(tokens)):
        if tokens[i] == "(":
            depth += 1
        elif tokens[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _is_unary_op_context(tokens: list[str], pos: int) -> bool:
    """Check if an operator at pos is unary (preceded by another operator or start)."""
    if pos == 0:
        return True
    prev = tokens[pos - 1]
    return prev in _BIN_OP_PRECEDENCE or prev in ("(", ",")


# ──────────────────────────────────────────────
# Propagator
# ──────────────────────────────────────────────


class ParamPropagator:
    """参数传播器

    从顶层模块开始 BFS 遍历例化树，传播参数实际值。

    Usage:
        propagator = ParamPropagator(index_store, top_module="top")
        results = propagator.propagate()
        # results = {"top": {"WIDTH": ResolvedParam(...)}, ...}
        print(ParamPropagator.format_params("top", results["top"]))
    """

    def __init__(
        self,
        index_store: IndexStore,
        top_module: str = "",
        max_depth: int = 100,
    ):
        self.index_store = index_store
        self.top_module = top_module
        self.max_depth = max_depth
        self._cache: dict[str, dict[str, ResolvedParam]] = {}

    def propagate(self) -> dict[str, dict[str, ResolvedParam]]:
        """BFS 遍历例化树，传播参数实际值。

        Returns:
            {module_name: {param_name: ResolvedParam}}
        """
        if self._cache:
            return self._cache

        from ..database.models import ModuleDef

        # BFS queue: (module_name, context_params, depth, path)
        queue: list[tuple[str, dict[str, str], int, str]] = [
            (self.top_module, {}, 0, self.top_module)
        ]
        visited_modules: set[str] = set()
        results: dict[str, dict[str, ResolvedParam]] = {}

        while queue and len(visited_modules) < self.max_depth:
            mod_name, context_params, depth, path = queue.pop(0)

            if mod_name in visited_modules:
                # Still propagate if we visit again with different context
                # (different parent may override params differently)
                pass

            mod = self.index_store.get_module(mod_name)
            if mod is None:
                continue

            # Check for defparam overrides from parent context
            # Defparam format: defparam path.param = value;
            # For now, merge defparam overrides from the context
            defparam_overrides: dict[str, str] = {}
            # Extract defparam-like entries from context
            defparam_prefix = f"defparam."
            for key, val in list(context_params.items()):
                if key.startswith(defparam_prefix):
                    defparam_overrides[key[len(defparam_prefix):]] = val

            # Resolve this module's parameters
            # Build a module-level context that includes parent-specified overrides
            # plus the module's own params as they become resolved (so later params
            # can reference earlier ones, e.g. DEPTH = WIDTH * 2)
            mod_context: dict[str, str] = dict(context_params)
            mod_params: dict[str, ResolvedParam] = {}

            for p in mod.parameters:
                if p.type == "localparam":
                    # localparam: default only, never overridden
                    val, resolved = self._eval(p.default_value or "", mod_context)
                    rp = ResolvedParam(
                        name=p.name,
                        default_value=p.default_value,
                        resolved_value=val,
                        is_resolved=resolved,
                        depth=depth,
                        path=path,
                        override_source="default",
                    )
                else:
                    # Priority: defparam > instance override > default
                    if p.name in defparam_overrides:
                        override_val = defparam_overrides[p.name]
                        val, resolved = self._eval(override_val, mod_context)
                        override_source = "defparam"
                    elif p.name in context_params:
                        override_val = context_params[p.name]
                        val, resolved = self._eval(override_val, mod_context)
                        override_source = "instance"
                    else:
                        val, resolved = self._eval(p.default_value or "", mod_context)
                        override_source = "default"

                    rp = ResolvedParam(
                        name=p.name,
                        default_value=p.default_value,
                        resolved_value=val,
                        is_resolved=resolved,
                        depth=depth,
                        path=path,
                        override_source=override_source,
                    )

                mod_params[p.name] = rp

                # Add resolved value to module context so subsequent params
                # can reference earlier ones (e.g. DEPTH = WIDTH * 2)
                if resolved:
                    mod_context[p.name] = val
                elif p.default_value:
                    mod_context[p.name] = p.default_value

            results[mod_name] = mod_params
            visited_modules.add(mod_name)

            # Enqueue child instances
            for inst in mod.instances:
                if inst.is_primitive:
                    continue

                # Children do NOT auto-inherit parent's parameter values.
                # Only explicitly-overridden values (from instantiation syntax)
                # are passed down, evaluated in the parent's context.
                child_context: dict[str, str] = {}
                for p_name, p_val in inst.param_overrides.items():
                    e_val, _ = self._eval(p_val, mod_context)
                    child_context[p_name] = e_val

                # Preserve defparam context across the hierarchy
                for key, val in context_params.items():
                    if key.startswith("defparam."):
                        child_context[key] = val

                child_path = f"{path}.{inst.instance_name}" if inst.instance_name else f"{path}.<anon>"
                queue.append(
                    (inst.module_type, child_context, depth + 1, child_path)
                )

        self._cache = results
        return results

    def _eval(self, expr: str, params: dict[str, str]) -> tuple[str, bool]:
        """Evaluate a Verilog expression string."""
        result, ok = _eval_simple_expr(expr, params)
        return result, ok

    @staticmethod
    def format_params(module_name: str, params: dict[str, ResolvedParam]) -> str:
        """将模块参数格式化为人类可读字符串。

        Args:
            module_name: 模块名
            params: {param_name: ResolvedParam}

        Returns:
            格式化的参数列表字符串
        """
        if not params:
            return f"{module_name}: (无参数)"

        lines = [f"  {module_name}:"]
        for name, rp in sorted(params.items(), key=lambda x: x[0]):
            status = "✓" if rp.is_resolved else "△"
            source = rp.override_source
            if rp.is_resolved:
                line = f"    {status} {name} = {rp.resolved_value}"
            else:
                default_str = f" (default: {rp.default_value})" if rp.default_value else ""
                line = f"    {status} {name} = {rp.resolved_value or rp.default_value or '?'}{default_str}"
            if source != "default":
                line += f" [override: {source}]"
            lines.append(line)

        return "\n".join(lines)

    def get_param(self, module_name: str, param_name: str) -> ResolvedParam | None:
        """获取已解析的参数值，延迟传播。"""
        if module_name not in self._cache:
            self.propagate()
        mod_params = self._cache.get(module_name)
        if mod_params is None:
            return None
        return mod_params.get(param_name)
