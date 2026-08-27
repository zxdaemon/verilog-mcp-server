"""语言映射（G1）+ SVA 容错契约（G2）+ corpus 错误率预算（G4）回归防线

覆盖编排卡 G1/G2/G4：
- G1: .vh 映射到 systemverilog（SV 头文件不再落 verilog grammar）
- G2: 时序算子（##1 等）产生 ERROR 节点时，模块提取不阻断
- G4: 真实 corpus 错误率预算（需设 VMS_CORPUS_PATH，CI/本地管线可用）
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from verilog_mcp_server.indexer.module_extractor import ModuleExtractor
from verilog_mcp_server.indexer.verilog_parser import (
    get_language_name,
    parse_file,
    parse_source,
)


def _error_nodes(tree) -> list:
    """递归收集 ERROR / MISSING 节点（与 vms_eng 扫描脚本同口径）"""
    errs: list = []
    stack = [tree.root_node]
    while stack:
        nd = stack.pop()
        if nd.is_error or nd.is_missing:
            errs.append(nd)
        for i in range(nd.child_count):
            stack.append(nd.child(i))
    return errs


# ── G1: 扩展名映射 ─────────────────────────────────────────────

def test_vh_maps_to_systemverilog():
    assert get_language_name("foo.vh") == "systemverilog"
    assert get_language_name("foo.VH") == "systemverilog"
    assert get_language_name("inc/defines.vh") == "systemverilog"


def test_existing_sv_family_mapping_unchanged():
    assert get_language_name("a.v") == "systemverilog"
    assert get_language_name("a.sv") == "systemverilog"
    assert get_language_name("a.svh") == "systemverilog"


def test_unknown_extension_falls_back_to_verilog():
    assert get_language_name("notes.txt") == "verilog"
    assert get_language_name("Makefile") == "verilog"


def test_parse_file_vh_uses_sv_grammar(tmp_path):
    """真实 .vh 头文件经 parse_file 走映射路径，0 ERROR"""
    vh = tmp_path / "axi_loopbuf_regbus_macro.vh"
    vh.write_text("""
`ifndef AXI_LOOPBUF_REGBUS_MACRO_VH
`define AXI_LOOPBUF_REGBUS_MACRO_VH

`define REGBUS_ADDR_W 12
typedef enum logic [1:0] {
    CFG_MODE_IDLE  = 2'b00,
    CFG_MODE_RUN   = 2'b01
} cfg_mode_e;

typedef struct packed {
    logic [31:0] base_addr;
    logic [31:0] length;
} dma_desc_t;

`endif
""")
    result = parse_file(str(vh))
    assert result is not None
    tree, _src = result
    assert _error_nodes(tree) == []


# ── G2: SVA 时序算子 ERROR 容错 ───────────────────────────────

SVA_SEQ_SRC = """
module sva_tolerant(
    input  logic       clk,
    input  logic       hold_i,
    input  logic [3:0] cnt
);
    logic seq_match;

    // ##1 时序算子：ts-systemverilog grammar 无序列算子支持 → ERROR 节点
    // 契约：ERROR 不阻断模块提取（类型化递归容忍）
    sequence s_hold_then_go;
        hold_i ##1 (cnt == 4'd0);
    endsequence

    property p_hold_then_go;
        @(posedge clk) disable iff (~s_hold_then_go.triggered)
        hold_i |-> ##[1:3] (cnt != 4'hf);
    endproperty

    always_comb begin
        seq_match = hold_i & (cnt == 4'd1);
    end

    assert property (p_hold_then_go);
endmodule
"""


def test_sva_temporal_errors_tolerated_by_module_extraction():
    """含 ##1 时序算子的文件即使产生 ERROR 节点，模块提取照常"""
    tree, src = parse_source(SVA_SEQ_SRC)
    errs = _error_nodes(tree)
    # grammar 现状会容忍少量 ERROR；此处不硬断言"必有"也不硬断言"必无"，
    # 只锁上界——无论 grammar 未来是否补齐时序算子，本防线都稳定
    assert len(errs) <= 8

    modules = ModuleExtractor().extract(tree, src, "sva_tolerant.sv")
    assert len(modules) == 1
    mod, node = modules[0]
    assert mod.name == "sva_tolerant"
    assert node is not None


# ── G4: corpus 错误率预算（环境注入真实工程路径）──────────────

@pytest.mark.skipif(
    not os.environ.get("VMS_CORPUS_PATH"),
    reason="corpus 预算防线需设 VMS_CORPUS_PATH（如 cpm/rtl 目录）",
)
def test_corpus_error_rate_budget():
    corpus = Path(os.environ["VMS_CORPUS_PATH"])
    sv_files = sorted(corpus.rglob("*.sv"))
    assert sv_files, f"corpus 无 .sv 文件: {corpus}"

    # 基线（2026-08-27 实测 cpm/rtl）：155 文件 / 113 ERROR / 34 文件有错
    # 预算为基线上限的 ~1.7x——防 grammar/pack 漂移级回归，不防微抖动
    total_errors = 0
    affected = 0
    for f in sv_files:
        result = parse_file(str(f))
        assert result is not None, f"解析失败: {f}"
        tree, _ = result
        n_err = len(_error_nodes(tree))
        total_errors += n_err
        if n_err:
            affected += 1

    assert total_errors <= 200, f"总 ERROR {total_errors} 超预算 200"
    assert affected <= 60, f"有错文件 {affected} 超预算 60"
