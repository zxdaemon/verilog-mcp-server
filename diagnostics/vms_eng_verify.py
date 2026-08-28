#!/usr/bin/env python3.12
"""VMS 引擎实证：运行安装版是否真实使用 tree-sitter-systemverilog 解析 .sv"""
import sys
from pathlib import Path

# ── 1. 运行安装版的解析模块（与 MCP 服务进程同一份代码）──
import verilog_mcp_server.indexer.verilog_parser as vp
print("module file:", vp.__file__)
print("LANGUAGE_MAP:", vp.LANGUAGE_MAP)

# ── 2. 用运行版 parse_file 解析真实 SV 文件，打印身份与错误统计 ──
def stats(tree):
    n = m = 0
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            m += 1
        n += 1
        for i in range(node.child_count):
            stack.append(node.child(i))
    return n, m

def kinds(tree, wanted):
    found = {}
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in wanted and not node.is_error:
            found[node.type] = found.get(node.type, 0) + 1
        for i in range(node.child_count):
            stack.append(node.child(i))
    return found

BASE = Path("/home/zhangxudong/shared/Projects/WorkCopy")
sv_files = [
    BASE / "TsmDesign/cpm/rtl/cpm_pkg.sv",
    BASE / "TsmDesign/cpm/verify/feq/tb/tb_feq_cpm_abs.sv",
]
v_file = BASE / "AlphaDesign/JPEG/JPG_TOP.v"

for f in sv_files:
    r = vp.parse_file(str(f))
    assert r, "parse failed"
    tree, text = r
    n, m = stats(tree)
    print(f"\n[SV→运行映射={vp.get_language_name(str(f))}] {f.name}: nodes={n} errs={m}")
    print("  签名节点:", kinds(tree, {"package_declaration","module_declaration",
          "class_declaration","always_construct","struct_union","interface_declaration"}))

# ── 3. A/B 对照：同一 .sv 喂给 ts-verilog grammar ──
from tree_sitter_language_pack import get_parser
p_vlog = get_parser("verilog")
f = sv_files[0]
src = f.read_text(encoding="utf-8").encode("utf-8")
t_v = p_vlog.parse(src)
n_v, m_v = stats(t_v)
print(f"\n[A/B] {f.name} 用 ts-verilog 解析: nodes={n_v} ERROR/missing={m_v}")

# ── 4. 运行映射下 .v 文件（也应走 systemverilog）──
r = vp.parse_file(str(v_file))
tree, text = r
n, m = stats(tree)
print(f"\n[.v→运行映射={vp.get_language_name(str(v_file))}] {v_file.name}: nodes={n} errs={m}")

# ── 5. parser cache 中实际加载的 grammar 身份 ──
print("\n[_parser_cache 身份]")
for k, p in vp._parser_cache.items():
    print(f"  {k}: language.name={getattr(p.language,'name','?')}")
