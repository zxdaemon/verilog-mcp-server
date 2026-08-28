#!/usr/bin/env python3.12
"""第二轮：grammar 能力边界 + 错误节点钻取 + 全库扫描"""
from pathlib import Path
from tree_sitter_language_pack import get_parser

p_sv = get_parser("systemverilog")
p_v = get_parser("verilog")

def errstats(tree):
    errs = []
    stack = [tree.root_node]
    while stack:
        nd = stack.pop()
        if nd.is_error or nd.is_missing:
            errs.append(nd)
        for i in range(nd.child_count):
            stack.append(nd.child(i))
    return errs

def parse_count(p, path):
    src = Path(path).read_text(encoding="utf-8", errors="replace").encode("utf-8")
    t = p.parse(src)
    return t, errstats(t)

BASE = Path("/home/zhangxudong/shared/Projects/WorkCopy")

# ── 1. JPG_TOP.v 的 6 个错误节点钻取 ──
f = BASE / "AlphaDesign/JPEG/JPG_TOP.v"
t, errs = parse_count(p_sv, f)
print(f"[SV grammar] {f.name}: 错误节点 {len(errs)}")
raw = f.read_bytes()
for e in errs:
    a, b = e.byte_range
    print("  ->", raw[a:min(b, a+80)].decode("utf-8", "replace").replace("\n", " ")[:80])

# ── 2. 找 SV 重度文件（class/UVM/interface）做 A/B ──
heavy = None
import subprocess
out = subprocess.run(["grep", "-rl", "--include=*.sv", "-e", "class", str(BASE/"TsmDesign/cpm")],
                     capture_output=True, text=True).stdout.splitlines()[:3]
for cand in out:
    text = open(cand).read()
    if "typedef" in text and ("logic" in text) and len(text) > 3000:
        heavy = cand; break
if heavy:
    for name, p in (("ts-systemverilog", p_sv), ("ts-verilog", p_v)):
        t, errs = parse_count(p, heavy)
        print(f"[A/B] {Path(heavy).name}({len(Path(heavy).read_bytes())}B) @ {name}: ERROR={len(errs)}")

# ── 3. cpm/rtl 全 .sv 扫描（ts-systemverilog）──
svdir = BASE/"TsmDesign/cpm/rtl"
svfiles = sorted(svdir.rglob("*.sv"))
bad = []
tot_err = 0
for s in svfiles:
    t, errs = parse_count(p_sv, s)
    tot_err += len(errs)
    if errs:
        bad.append(s.name)
print(f"\n[cpm/rtl 扫描 @ systemverilog] 文件={len(svfiles)} 总错误节点={tot_err} 有错文件={len(bad)} {bad[:5]}")

# ── 4. JPEG 目录 .v 扫描（ts-systemverilog vs ts-verilog）──
vdir = BASE/"AlphaDesign/JPEG"
vfiles = sorted(vdir.glob("*.v"))[:30]
for name, p in (("systemverilog", p_sv), ("verilog", p_v)):
    bad = []
    for s in vfiles:
        t, errs = parse_count(p, s)
        if errs:
            bad.append((s.name, len(errs)))
    print(f"[JPEG .v 扫描 @ {name}] 文件={len(vfiles)} 有错={len(bad)} {bad[:4]}")
