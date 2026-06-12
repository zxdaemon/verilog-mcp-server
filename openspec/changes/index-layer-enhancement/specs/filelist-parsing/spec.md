## ADDED Requirements

### Requirement: Basic .f file parsing
The system SHALL parse EDA file list (`.f`) files and extract file paths from `-v`, `-y`, `+incdir+`, `-f` directives, ignoring comments and blank lines.

#### Scenario: Simple file list
- **WHEN** a `.f` file contains:
  ```
  // comment
  +incdir+/path/to/include
  -v /path/to/lib.v
  -y /path/to/libdir
  rtl/module_a.v
  rtl/module_b.v
  ```
- **THEN** the parser returns `files=["rtl/module_a.v", "rtl/module_b.v"]`, `incdirs=["/path/to/include"]`, `lib_files=["/path/to/lib.v"]`, `lib_dirs=["/path/to/libdir"]`

#### Scenario: Recursive -f include
- **WHEN** a `.f` file contains `-f sub_filelist.f`
- **THEN** the parser recursively processes `sub_filelist.f` and merges results (up to max depth 5)

#### Scenario: Relative path resolution
- **WHEN** a `.f` file references files with relative paths
- **THEN** paths are resolved relative to the `.f` file's directory

### Requirement: ProjectScanner .f file integration
The project scanner SHALL detect `.f` files during scanning and expand them into individual RTL file paths.

#### Scenario: Project path is a .f file
- **WHEN** config paths include `project.f`
- **THEN** the scanner parses `project.f` and returns the expanded RTL file list
