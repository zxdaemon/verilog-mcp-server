## MODIFIED Requirements

### Requirement: ModuleDef extended fields
`ModuleDef` SHALL include new fields to store package imports, SVA assertions, and testbench detection results.

#### Scenario: Module with package imports
- **WHEN** a module imports `my_pkg::*` and `util_pkg::helper`
- **THEN** `ModuleDef.package_imports` contains two `PackageImportDef` entries with correct `package`, `symbol`, `wildcard` fields

#### Scenario: Module with SVA assertions
- **WHEN** a module contains `assert property(@(posedge clk) req |=> ack);` and a named `sequence handshake;`
- **THEN** `ModuleDef.assertions` contains entries with `type`, `keyword`, `property`/`name` fields

#### Scenario: Testbench module detection flags
- **WHEN** a module contains `initial begin ... end` block
- **THEN** `ModuleDef.is_testbench` is `true`
- **WHEN** a module contains `#5` delay and `$display` call but no `initial` block
- **THEN** `ModuleDef.is_testbench` is `false`, `ModuleDef.has_non_synth_constructs` is `true`

#### Scenario: Legacy ModuleDef serialization
- **WHEN** a `ModuleDef` serialized before these fields existed is loaded
- **THEN** `package_imports` defaults to `[]`, `assertions` defaults to `[]`, `is_testbench` defaults to `false`, `has_non_synth_constructs` defaults to `false`

### Requirement: FileMeta dataclass
The system SHALL include a `FileMeta` dataclass to store file-level metadata: macro definitions, conditional compilation branches, and package definitions found in a source file.

#### Scenario: FileMeta with macro definitions
- **WHEN** a file contains `` `define WIDTH 32 `` and `` `define MAX(a,b) ((a)>(b)?(a):(b)) ``
- **THEN** `FileMeta.defines` contains two `MacroDef` entries with `name`, `params`, `value` fields

#### Scenario: FileMeta with conditional branches
- **WHEN** a file contains `` `ifdef SIMULATION `` ... `` `else `` ... `` `endif ``
- **THEN** `FileMeta.conditionals` records both branches with source ranges

#### Scenario: FileMeta with package definitions
- **WHEN** a file contains `package my_pkg; typedef enum {IDLE, RUN} state_t; endpackage`
- **THEN** `FileMeta.package_defs` contains a `PackageDef` with `name="my_pkg"`

### Requirement: New supporting dataclass types
The system SHALL define new dataclass types to support the extended extraction capabilities, all inheriting `SerializableModel`.

- `PackageImportDef`: fields `package: str`, `symbol: str = "*"`, `wildcard: bool = True`
- `SvaDef`: fields `type: str`, `keyword: str`, `name: str`, `expression: str`, `property: str`, `clock: str`, `action: str`, `body: str`
- `MacroDef`: fields `name: str`, `params: list[str]`, `value: str`
- `ConditionalBranch`: fields `condition: str`, `branch_type: str`, `start_line: int`, `end_line: int`, `children: list[ConditionalBranch]`
- `PackageDef`: fields `name: str`, `file_path: str`, `typedefs: list[TypeDef]`, `parameters: list[ParamDef]`

#### Scenario: SvaDef for immediate assertion
- **WHEN** creating `SvaDef(type="immediate", keyword="assert", expression="req && ack", action="$error(...)")`
- **THEN** `to_dict()` and `from_dict()` round-trip preserves all fields

#### Scenario: MacroDef with parameters
- **WHEN** creating `MacroDef(name="MAX", params=["a","b"], value="((a)>(b)?(a):(b))")`
- **THEN** `to_dict()` and `from_dict()` round-trip preserves all fields

#### Scenario: Nested ConditionalBranch
- **WHEN** an `ifdef A` block contains a nested `ifdef B` block
- **THEN** `ConditionalBranch.children` contains the nested branch, and serialization round-trips correctly

### Requirement: ModuleDef SQLite row serialization extended
`ModuleDef.to_row()` and `ModuleDef.from_row()` SHALL handle the new nested fields (`package_imports`, `assertions`) as JSON columns.

#### Scenario: ModuleDef row round-trip with new fields
- **WHEN** a `ModuleDef` has `package_imports=[PackageImportDef(...)]` and `assertions=[SvaDef(...)]` and is serialized via `to_row()` then `from_row()`
- **THEN** `is_testbench`, `has_non_synth_constructs` are preserved, and nested lists round-trip correctly
