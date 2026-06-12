# OpenC910 设计概览报告

## 总体规模
| 指标 | 数值 |
|------|------|
| 模块总数 | 534 |
| 文件总数 | 530 |
| 端口总数 | 26928 |
| 信号总数 | 65921 |
| 子模块例化 | 3133 |
| always 块 | 3454 |
| assign 语句 | 31276 |

## 模块目录分布
| 目录 | 模块数 |
|------|--------|
| C910_RTL_FACTORY/gen_rtl/lsu | 70 |
| C910_RTL_FACTORY/gen_rtl/idu | 57 |
| C910_RTL_FACTORY/gen_rtl/ifu | 50 |
| C910_RTL_FACTORY/gen_rtl/fpga | 42 |
| C910_RTL_FACTORY/gen_rtl/ciu | 37 |
| C910_RTL_FACTORY/gen_rtl/l2c | 33 |
| C910_RTL_FACTORY/gen_rtl/vfalu | 32 |
| C910_RTL_FACTORY/gen_rtl/had | 22 |
| C910_RTL_FACTORY/gen_rtl/rtu | 22 |
| C910_RTL_FACTORY/gen_rtl/mmu | 21 |
| C910_RTL_FACTORY/gen_rtl/iu | 14 |
| C910_RTL_FACTORY/gen_rtl/plic | 14 |
| smart_run/logical/common | 12 |
| C910_RTL_FACTORY/gen_rtl/vfdsu | 12 |
| C910_RTL_FACTORY/gen_rtl/vfmau | 11 |

## TOP 10 最大模块
| 模块 | 信号 | always | assign | 例化 |
|------|------|--------|--------|------|
| ct_idu_top | 1750 | 0 | 27 | 25 |
| ct_lsu_top | 1728 | 0 | 14 | 32 |
| ct_core | 1519 | 0 | 0 | 7 |
| ct_ifu_top | 1294 | 0 | 0 | 22 |
| ct_ifu_ipdp | 1263 | 97 | 764 | 7 |
| ct_rtu_pst_preg | 1235 | 5 | 1230 | 135 |
| ct_ciu_top | 1093 | 1 | 14 | 21 |
| ct_ifu_ibuf | 1009 | 43 | 596 | 35 |
| ct_rtu_rob | 971 | 15 | 620 | 84 |
| ct_rtu_pst_vreg | 945 | 4 | 967 | 106 |