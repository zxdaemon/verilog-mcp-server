## ADDED Requirements

### Requirement: Testbench module identification
The system SHALL detect verification/testbench structures in modules and mark them accordingly.

#### Scenario: Module with initial block
- **WHEN** a module contains an `initial` block
- **THEN** `ModuleDef.is_testbench` is `true`

#### Scenario: Module with system task calls
- **WHEN** a module contains `$display`, `$monitor`, `$strobe`, `$finish`, or `$fatal`
- **THEN** `ModuleDef.has_non_synth_constructs` is `true`

#### Scenario: RTL design module
- **WHEN** a module contains only `always`/`assign`/`wire`/`reg` declarations with no simulation-only constructs
- **THEN** `ModuleDef.is_testbench` is `false` and `has_non_synth_constructs` is `false`

### Requirement: Non-synthesizable construct detection
The system SHALL detect and flag non-synthesizable constructs within any module.

#### Scenario: Delay control in module
- **WHEN** a module contains `#5` or `#(cycle)` delay control
- **THEN** `ModuleDef.has_non_synth_constructs` is `true`

#### Scenario: Force/release statements
- **WHEN** a module contains `force signal = value;` or `release signal;`
- **THEN** `ModuleDef.has_non_synth_constructs` is `true`

#### Scenario: Fork-join block
- **WHEN** an initial block contains `fork ... join`
- **THEN** the module is flagged as testbench
