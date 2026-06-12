# OpenC910 代码质量审查报告

## Always 块分类

| 模块 | always | 时序 | 组合 | 锁存器 |
|------|--------|------|------|--------|
| ct_idu_id_split_long | 164 | 40 | 124 | 0 |
| ct_ifu_ipdp | 97 | 16 | 81 | 0 |
| ct_idu_is_dp | 69 | 1 | 68 | 0 |
| ct_idu_ir_frt | 67 | 1 | 66 | 0 |
| ct_cp0_regs | 66 | 59 | 7 | 0 |
| ct_ifu_ras | 63 | 58 | 5 | 0 |
| ct_ifu_lbuf | 60 | 32 | 28 | 0 |
| ct_idu_ir_rt | 59 | 0 | 59 | 0 |
| ct_ifu_bht | 58 | 32 | 26 | 0 |
| ct_ciu_snb_sab_entry | 54 | 42 | 12 | 0 |
| ct_idu_rf_dp | 53 | 48 | 5 | 0 |
| ct_ifu_ibuf | 43 | 4 | 39 | 0 |
| ct_lsu_wmb | 36 | 22 | 14 | 0 |
| ct_mmu_iplru | 36 | 33 | 3 | 0 |
| ct_ebiu_write_channel | 35 | 29 | 6 | 0 |

## FSM 状态机

- **ct_cp0_iui**::rst_dcache_inv_fsm: 2 状态 [symbolic] Moore
- **ct_cp0_iui**::rst_icache_inv_fsm: 2 状态 [symbolic] Moore
- **ct_cp0_iui**::rst_tlb_inv_fsm: 2 状态 [symbolic] Moore
- **ct_cp0_iui**::rst_cache_inv_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_funored_w_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_fnorm_wf_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_fored_w_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_fored_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::zvlsseg_unit_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::zvlsseg_index_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_index_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_fnorm_wv_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_stride_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::vec_funored_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::zvlsseg_stride_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_idu_id_split_long**::amo_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_l2c_data**::data_ram_state_fsm: 2 状态 [symbolic] Moore
- **ct_l2c_prefetch**::pref_state_fsm: 2 状态 [symbolic] Moore
- **ct_mmu_tlboper**::tlbiall_cur_st_fsm: 2 状态 [symbolic] Moore
- **ct_rtu_pst_ereg_entry**::wb_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_rtu_pst_preg_entry**::wb_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_rtu_pst_vreg_entry**::wb_cur_state_fsm: 2 状态 [symbolic] Moore
- **ct_vfdsu_ctrl**::srt_cur_state_fsm: 2 状态 [symbolic] Moore

检测到 9 个含状态机的模块

## 关键模块引用统计

- **gated_clk_cell**: 被 741 个模块例化
- **ct_core**: 被 1 个模块例化
- **openC910**: 被 1 个模块例化
- **fpga_ram**: 被 103 个模块例化
- **ram**: 被 48 个模块例化