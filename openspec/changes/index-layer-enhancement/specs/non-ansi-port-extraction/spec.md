## ADDED Requirements

### Requirement: Non-ANSI port width and type extraction
The port extractor SHALL extract bit width, variable type (wire/reg/logic), and signed attribute from non-ANSI port declarations in the module body.

#### Scenario: Basic non-ANSI output port
- **WHEN** a module uses non-ANSI header `module foo(a, b, c);` with body declarations `output [7:0] a; wire [7:0] a; input b; input [3:0] c;`
- **THEN** port `a` has `direction=output`, `width_range="[7:0]"`, `var_type="wire"`
- **AND** port `b` has `direction=input`, `width_range=""`, `var_type=""`
- **AND** port `c` has `direction=input`, `width_range="[3:0]"`, `var_type=""`

#### Scenario: Non-ANSI signed port
- **WHEN** a non-ANSI module declares `output signed [15:0] result; wire signed [15:0] result;`
- **THEN** port `result` has `signed=true`, `width_range="[15:0]"`

#### Scenario: Non-ANSI reg output port
- **WHEN** a non-ANSI module declares `output reg [31:0] count;`
- **THEN** port `count` has `var_type="reg"`, `width_range="[31:0]"`

### Requirement: ANSI and non-ANSI port output consistency
Ports extracted from ANSI and non-ANSI modules SHALL have the same set of fields populated.

#### Scenario: Mixed port styles in project
- **WHEN** a project contains both ANSI-style module `module bar(input clk, output reg [7:0] out);` and non-ANSI `module foo(clk, out); input clk; output reg [7:0] out;`
- **THEN** both modules' port lists have identical field completeness (`direction`, `var_type`, `width_range`, `signed`)
