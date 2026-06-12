## 1. Data Model Extension

- [x] 1.1 Add new dataclasses to models.py: PackageImportDef, SvaDef, MacroDef, ConditionalBranch, PackageDef
- [x] 1.2 Extend ModuleDef with new fields: package_imports, assertions, is_testbench, has_non_synth_constructs
- [x] 1.3 Add FileMeta dataclass with defines, conditionals, package_defs fields
- [x] 1.4 Update ModuleDef.to_row() and from_row() for new nested fields (package_imports_json, assertions_json, is_testbench, has_non_synth_constructs)

## 2. Non-ANSI Port Enhancement

- [x] 2.1 Enhance port_extractor.py to extract width, type, and signed from non-ANSI port declarations in module body
- [x] 2.2 Ensure ANSI and non-ANSI port output have identical field completeness

## 3. Package/Import Parsing

- [x] 3.1 Create package_extractor.py to extract package definitions (typedefs, parameters)
- [x] 3.2 Add import declaration extraction to package_extractor.py
- [x] 3.3 Integrate package_extractor into IndexBuilder._parse_and_index_file()

## 4. SVA Assertion Extraction

- [x] 4.1 Create sva_extractor.py for immediate assertions (assert/assume/cover in procedural blocks)
- [x] 4.2 Add concurrent assertion extraction (assert property/assume property/cover property)
- [x] 4.3 Add property and sequence declaration extraction
- [x] 4.4 Integrate sva_extractor into IndexBuilder._parse_and_index_file()

## 5. Macro Extraction

- [x] 5.1 Create macro_extractor.py to extract `define macro definitions (name, params, value)
- [x] 5.2 Add macro usage recording within modules
- [x] 5.3 Add conditional compilation branch recording (`ifdef/`ifndef/`elsif/`else/`endif)
- [x] 5.4 Integrate macro_extractor into IndexBuilder._parse_and_index_file()

## 6. Filelist Parsing

- [x] 6.1 Create filelist_parser.py to parse .f files (files, incdirs, lib_files, lib_dirs)
- [x] 6.2 Support recursive -f include (max depth 5) and relative path resolution
- [x] 6.3 Integrate filelist parsing into ProjectScanner for automatic .f file expansion

## 7. Testbench Detection

- [x] 7.1 Add testbench detection in signal_extractor.py: detect initial blocks, system tasks ($display/$monitor), fork-join
- [x] 7.2 Add non-synthesizable construct detection: delay control (#N), force/release statements
- [x] 7.3 Set ModuleDef.is_testbench and has_non_synth_constructs flags accordingly

## 8. Tests

- [x] 8.1 Write tests for non-ANSI port extraction (ANSI/non-ANSI parity, signed ports, reg ports)
- [x] 8.2 Write tests for package_extractor (import parsing, package definitions, wildcard imports)
- [x] 8.3 Write tests for sva_extractor (immediate asserts, concurrent asserts, property/sequence)
- [x] 8.4 Write tests for macro_extractor (define extraction, param macros, ifdef branches)
- [x] 8.5 Write tests for filelist_parser (.f file parsing, recursive -f, relative paths)
- [x] 8.6 Write tests for testbench detection (initial blocks, system tasks, force/release, delay)
- [x] 8.7 Run full test suite and verify all tests pass
