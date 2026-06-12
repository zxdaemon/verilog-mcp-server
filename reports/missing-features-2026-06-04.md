# 功能缺失分析

日期: 2026-06-04

---

## 一、索引层缺失（地基）

| # | 缺失功能 | 影响 | 现状 |
|---|---------|------|------|
| 1 | `always_comb/always_ff/always_latch` 识别 | SV 三种专用 always 关键字完全不识别，对应 always 块丢失 | `signal_extractor.py:317` 只处理 `always_construct` |
| 2 | 非 ANSI 端口宽度/类型提取 | 旧式 Verilog 端口声明的位宽和类型被丢弃 | `port_extractor.py` 非 ANSI 路径只取 name+dir |
| 3 | 位置端口连接解析 | `(a, b, c)` 格式的例化端口连接完全不处理 | `instance_extractor.py:82` 只处理 `named_port_connection` |
| 4 | parameter 默认值提取与常量折叠 | 无法回答"此例化中 WIDTH 实际是多少位" | instance_extractor 存了原始文本但不求值 |
| 5 | interface 端口识别 | `axis_if.slave rx` 类端口被跳过 | port_extractor 无 `interface_port` 处理 |
| 6 | package/import 解析 | 跨文件类型引用断裂 | 无 package_extractor |
| 7 | SVA 断言提取 | 断言信息完全丢失 | 无 sva_extractor |
| 8 | `define 宏展开追踪 | 条件编译分支、宏定义值不可见 | 无宏处理器 |

## 二、分析层缺失

| # | 缺失功能 | 价值 |
|---|---------|------|
| 9 | Lint 规则引擎 | 未连接端口、多驱动、未使用信号、宽度不匹配等基本设计规则检查 |
| 10 | 时序路径分析 | 寄存器→组合逻辑→寄存器的数据流路径，逻辑深度计算 |
| 11 | CDC 路径详情 | 当前只按时钟域分组模块，不分析具体跨时钟域信号路径 |
| 12 | 复位域分析 | 异步复位 vs 同步复位，复位域交叉检查 |
| 13 | FSM 检测升级为 AST 级 | 当前依赖正则匹配 case 语句，漏掉 casez/casex，嵌套 case 不可靠 |
| 14 | 设计模式识别 | FIFO、仲裁器、流水线、握手协议等常见模式自动识别 |
| 15 | 总线协议检测 | AXI/AHB/APB 等标准总线接口自动识别 |
| 16 | 跨层级端口数据流穿透 | 端口信号完整跨模块追踪（当前 `rtl_port_dataflow` 有 bug 且功能不完整） |

## 三、工程化能力缺失

| # | 缺失功能 | 价值 |
|---|---------|------|
| 17 | 代码度量面板 | 模块行数分布、扇入/扇出统计、CDC 风险数、参数化复杂度等聚合仪表盘 |
| 18 | RTL 差异对比 | 两个版本的模块/端口/信号增删改报告 |
| 19 | 寄存器地图提取 | 自动提取地址映射表（address decoder → register map） |
| 20 | 自动模块数据手册 | 从 RTL 生成模块级 datasheet（端口表、参数表、FSM 图、时钟域） |
| 21 | 文件依赖图 | include 关系、模块例化依赖拓扑排序 |
| 22 | 综合属性/pragma 识别 | `(* syn_keep *)`、`// synthesis translate_off` 等属性提取 |
| 23 | Testbench 识别 | 区分设计模块和验证模块，提取 `initial`/`fork`/`$display` 等验证结构 |
| 24 | 非综合代码标记 | 识别 `#delay`、`$monitor`、`force/release` 等仅仿真结构 |
| 25 | EDA 项目文件解析 | `.f` 文件列表、`.tcl` 脚本中的文件路径提取 |

## 四、MCP 协议能力缺失

| # | 缺失功能 | 价值 |
|---|---------|------|
| 26 | MCP Resources | 将模块列表、信号索引等暴露为 resource，支持 `resources/list` + `resources/read` |
| 27 | MCP Prompts | 预置分析提示词模板（"分析此模块的时钟域"、"检查此设计的 CDC 风险"） |
| 28 | 流式进度反馈 | 长时间分析（全量 lint、大层次树）无进度通知 |
| 29 | 分析结果缓存 | 每次调用重新计算，无跨请求缓存（仅有索引缓存） |

## 五、性能与规模缺失

| # | 缺失功能 | 价值 |
|---|---------|------|
| 30 | 并行模块解析 | `builder.py` 单线程逐文件解析 |
| 31 | 大结果分页 | 搜索/分析结果无分页，超大设计可能超出 MCP 响应限制 |

---

## 已完成项（对照原路线图）

以下原路线图中的项目已实现：

- Phase 1.2: 统一信号分类器 (`signal_classifier.py`)
- Phase 1.3: generate 块展开 (`iter_module_body_deep`)
- Phase 2.1: 表达式 AST 遍历 (`expr_walker.py`)
- Phase 3.4: type 提取 (`type_extractor.py`)
- drivers/loads 的 assign 和 always 提取 (`_extract_assign_drivers_loads`)
