## ADDED Requirements

### Requirement: Immediate assertion extraction
The system SHALL extract immediate assertions (`assert`, `assume`, `cover`) from procedural blocks and store them with expression text and action block text.

#### Scenario: Simple immediate assert
- **WHEN** an always block contains `assert (req && ack) else $error("protocol violation");`
- **THEN** `ModuleDef.assertions` includes an entry with `type="immediate"`, `keyword="assert"`, `expression="req && ack"`, `action="$error(\"protocol violation\")"`

#### Scenario: Immediate assume in procedural code
- **WHEN** an always block contains `assume (valid_in);`
- **THEN** an assertion entry has `keyword="assume"`, `expression="valid_in"`

### Requirement: Concurrent assertion extraction
The system SHALL extract concurrent assertions (`assert property`, `assume property`, `cover property`) from module-level scope.

#### Scenario: Concurrent assert property
- **WHEN** module scope contains `assert property (@(posedge clk) req |=> ack);`
- **THEN** an assertion entry has `type="concurrent"`, `keyword="assert"`, `clock="@(posedge clk)"`, `property="req |=> ack"`

#### Scenario: Cover property
- **WHEN** module scope contains `cover property (@(posedge clk) $rose(start));`
- **THEN** an assertion entry has `keyword="cover"`, `type="concurrent"`

### Requirement: Property and sequence declaration extraction
The system SHALL extract named `property` and `sequence` declarations.

#### Scenario: Named sequence
- **WHEN** a module contains `sequence handshake; req ##1 ack; endsequence`
- **THEN** `ModuleDef.assertions` includes an entry with `type="sequence"`, `name="handshake"`, `body="req ##1 ack"`
