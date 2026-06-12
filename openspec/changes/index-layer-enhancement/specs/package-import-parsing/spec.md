## ADDED Requirements

### Requirement: Package import declaration extraction
The system SHALL extract `import` declarations from module scope and store them per-module as a list of imported package names.

#### Scenario: Simple package import
- **WHEN** a module contains `import my_pkg::*;`
- **THEN** `ModuleDef.package_imports` includes `my_pkg` with `wildcard=true`

#### Scenario: Specific symbol import
- **WHEN** a module contains `import my_pkg::my_type;`
- **THEN** `ModuleDef.package_imports` includes an entry with `package="my_pkg"`, `symbol="my_type"`, `wildcard=false`

#### Scenario: Multiple imports
- **WHEN** a module contains both `import pkg_a::*;` and `import pkg_b::helper;`
- **THEN** both imports are extracted with correct wildcard flags

### Requirement: Package definition extraction
The system SHALL extract package definitions including their name, file location, and contents (type declarations, parameter declarations).

#### Scenario: Package with typedef
- **WHEN** a file contains `package my_pkg; typedef enum {IDLE, RUN} state_t; endpackage`
- **THEN** a `PackageDef` is stored with `name="my_pkg"`, containing the typedef

#### Scenario: Package with parameter
- **WHEN** a file contains `package config_pkg; parameter WIDTH = 32; endpackage`
- **THEN** a `PackageDef` is stored with `name="config_pkg"`, `parameters` includes `WIDTH=32`
