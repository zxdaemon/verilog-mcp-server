## ADDED Requirements

### Requirement: 位置端口连接识别
`indexer/instance_extractor.py` SHALL 处理 `list_of_port_connections` 中的位置端口连接（即 unnamed `expression` 作为子节点，而非 `named_port_connection`）。系统 SHALL 按连接位置序号，将其映射到子模块声明顺序中对应位置的形式端口名。

#### Scenario: 全位置连接
- **WHEN** 源文件包含 `my_mod u_mod (clk, rst_n, data_in, data_out);` 且 `my_mod` 端口顺序为 `clk, rst_n, din, dout`
- **THEN** port_connections 为 `{"clk": "clk", "rst_n": "rst_n", "din": "data_in", "dout": "data_out"}`

#### Scenario: 子模块未索引时的位置连接
- **WHEN** 源文件包含位置连接但子模块 `unknown_mod` 不在索引中
- **THEN** port_connections 使用占位名 `{"__pos_0": "actual0", "__pos_1": "actual1", ...}`

#### Scenario: 命名和位置混合连接
- **WHEN** 源文件包含 `my_mod u_mod (.clk(clk), .rst_n(rst_n), data_in, data_out);`
- **THEN** 系统正确处理混合连接：命名连接按名匹配，位置连接按序号匹配（跳过已命名的序号位置）
