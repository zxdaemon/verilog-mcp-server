## ADDED Requirements

### Requirement: Macro definition extraction
The system SHALL extract `define macro definitions including name, optional parameter list, and value text.

#### Scenario: Simple value macro
- **WHEN** a file contains `` `define WIDTH 32 ``
- **THEN** `FileMeta.defines` includes `name="WIDTH"`, `params=[]`, `value="32"`

#### Scenario: Parameterized macro
- **WHEN** a file contains `` `define MAX(a,b) ((a) > (b) ? (a) : (b)) ``
- **THEN** `FileMeta.defines` includes `name="MAX"`, `params=["a", "b"]`, `value="((a) > (b) ? (a) : (b))"`

#### Scenario: Multi-line macro
- **WHEN** a macro definition spans multiple lines using `\`
- **THEN** the value text preserves the continuation, stored as a single string

### Requirement: Macro usage recording
The system SHALL record macro usage occurrences within modules.

#### Scenario: Macro used in module
- **WHEN** a module contains `` wire [`WIDTH-1:0] data; ``
- **THEN** the macro usage `` `WIDTH `` is recorded with its location

### Requirement: Conditional compilation branch recording
The system SHALL record `ifdef/`ifndef/`elsif/`else/`endif structures without evaluating conditions.

#### Scenario: Simple ifdef block
- **WHEN** a file contains `` `ifdef SIMULATION `` ... `` `else `` ... `` `endif ``
- **THEN** `FileMeta.conditionals` records both branches with their source ranges

#### Scenario: Nested ifdef
- **WHEN** a file contains nested `ifdef blocks (`ifdef A ... `ifdef B ... `endif ... `endif)
- **THEN** nesting depth is correctly tracked
