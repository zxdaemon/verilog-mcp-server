"""
SQLite 后端存储 — 替代 JSON 整体读写
"""

from __future__ import annotations

import atexit
import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional

from .models import (
    ModuleDef,
    TypeDef,
    ElaboratedInstanceDef,
    ResolvedSignalDef,
    MacroExpansionInfo,
    ElaborationReport,
)

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS modules (
    name TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    ports_json TEXT,
    params_json TEXT,
    signals_json TEXT,
    instances_json TEXT,
    always_blocks_json TEXT,
    assignments_json TEXT
);

CREATE TABLE IF NOT EXISTS files (
    file_path TEXT NOT NULL,
    module_name TEXT NOT NULL,
    PRIMARY KEY (file_path, module_name)
);

CREATE TABLE IF NOT EXISTS signal_index (
    signal_name TEXT NOT NULL,
    module_name TEXT NOT NULL,
    PRIMARY KEY (signal_name, module_name)
);

CREATE TABLE IF NOT EXISTS types (
    name TEXT PRIMARY KEY,
    kind TEXT,
    members_json TEXT,
    source_text TEXT,
    file_path TEXT,
    line INTEGER
);

CREATE TABLE IF NOT EXISTS file_meta (
    file_path TEXT PRIMARY KEY,
    mtime REAL,
    sha256 TEXT
);

CREATE INDEX IF NOT EXISTS idx_signal_name ON signal_index(signal_name);
CREATE INDEX IF NOT EXISTS idx_modules_file_path ON modules(file_path);

CREATE TABLE IF NOT EXISTS elaborated_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_name TEXT NOT NULL,
    module_type TEXT NOT NULL,
    hierarchical_path TEXT NOT NULL,
    parent_module TEXT,
    is_generated INTEGER DEFAULT 0,
    generate_condition TEXT,
    generate_source TEXT,
    file_path TEXT,
    line INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resolved_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    module_name TEXT NOT NULL,
    var_type TEXT DEFAULT 'wire',
    original_width TEXT,
    resolved_width TEXT,
    resolved_bit_width INTEGER DEFAULT 0,
    is_signed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS macro_expansions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    definition TEXT,
    definition_file TEXT,
    definition_line INTEGER DEFAULT 0,
    expansion_count INTEGER DEFAULT 0,
    expansion_locations_json TEXT
);

CREATE TABLE IF NOT EXISTS elaboration_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL DEFAULT (strftime('%s', 'now')),
    top_modules_json TEXT,
    total_instances INTEGER DEFAULT 0,
    generated_instances INTEGER DEFAULT 0,
    non_generated_instances INTEGER DEFAULT 0,
    unique_module_types INTEGER DEFAULT 0,
    resolved_signals INTEGER DEFAULT 0,
    tree_sitter_module_count INTEGER DEFAULT 0,
    pyslang_module_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    diagnostics_json TEXT,
    hierarchy_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_elab_inst_path ON elaborated_instances(hierarchical_path);
CREATE INDEX IF NOT EXISTS idx_elab_inst_module ON elaborated_instances(module_type);
CREATE INDEX IF NOT EXISTS idx_resolved_sig_module ON resolved_signals(module_name);
CREATE INDEX IF NOT EXISTS idx_macro_name ON macro_expansions(name);
"""


class SQLiteBackend:
    """SQLite 存储后端，提供模块、信号、文件映射的 CRUD 操作"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        atexit.register(self.close)
        logger.info(f"SQLite 后端已初始化: {db_path}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Module Operations ──

    def save_module(self, module: ModuleDef) -> None:
        """INSERT OR REPLACE 模块到 modules 表（事务保护）"""
        row = module.to_row()
        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO modules
                   (name, file_path, line_start, line_end,
                    ports_json, params_json, signals_json,
                    instances_json, always_blocks_json, assignments_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["name"], row["file_path"], row["line_start"], row["line_end"],
                    row["ports_json"], row["params_json"], row["signals_json"],
                    row["instances_json"], row["always_blocks_json"], row["assignments_json"],
                ),
            )
            # 更新 files 映射
            self._conn.execute(
                "INSERT OR IGNORE INTO files (file_path, module_name) VALUES (?, ?)",
                (module.file_path, module.name),
            )
            # 更新 signal_index
            self._update_signal_index(module)

    def load_module(self, name: str) -> Optional[ModuleDef]:
        """从 modules 表读取单个模块"""
        cur = self._conn.execute(
            "SELECT * FROM modules WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return ModuleDef.from_row(_row_to_dict(row))

    def load_all_modules(self) -> list[ModuleDef]:
        """读取所有模块"""
        cur = self._conn.execute("SELECT * FROM modules")
        return [ModuleDef.from_row(_row_to_dict(row)) for row in cur.fetchall()]

    def load_module_names(self) -> list[str]:
        """读取所有模块名"""
        cur = self._conn.execute("SELECT name FROM modules")
        return [row[0] for row in cur.fetchall()]

    def delete_module(self, name: str) -> None:
        """删除单个模块及其关联索引"""
        # 先获取模块信息以清理关联表
        cur = self._conn.execute(
            "SELECT file_path FROM modules WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        if not row:
            return
        file_path = row[0]

        self._conn.execute("DELETE FROM modules WHERE name = ?", (name,))
        self._conn.execute(
            "DELETE FROM files WHERE file_path = ? AND module_name = ?",
            (file_path, name),
        )
        self._conn.execute(
            "DELETE FROM signal_index WHERE module_name = ?", (name,)
        )
        self._conn.commit()

    def delete_modules_by_file(self, file_path: str) -> None:
        """删除某文件的所有模块"""
        cur = self._conn.execute(
            "SELECT name FROM modules WHERE file_path = ?", (file_path,)
        )
        names = [row[0] for row in cur.fetchall()]
        if not names:
            return

        self._conn.execute(
            "DELETE FROM modules WHERE file_path = ?", (file_path,)
        )
        self._conn.execute(
            "DELETE FROM files WHERE file_path = ?", (file_path,)
        )
        for name in names:
            self._conn.execute(
                "DELETE FROM signal_index WHERE module_name = ?", (name,)
            )
        self._conn.commit()

    def search_modules(self, pattern: str) -> list[ModuleDef]:
        """模糊搜索模块名"""
        cur = self._conn.execute(
            "SELECT * FROM modules WHERE name LIKE ? ORDER BY name",
            (f"%{pattern}%",),
        )
        return [ModuleDef.from_row(_row_to_dict(row)) for row in cur.fetchall()]

    def get_module_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM modules")
        return cur.fetchone()[0]

    # ── File Mapping ──

    def get_modules_for_file(self, file_path: str) -> list[str]:
        """获取某文件的所有模块名"""
        cur = self._conn.execute(
            "SELECT module_name FROM files WHERE file_path = ?", (file_path,)
        )
        return [row[0] for row in cur.fetchall()]

    def get_all_files(self) -> list[str]:
        """获取所有文件路径"""
        cur = self._conn.execute("SELECT DISTINCT file_path FROM files")
        return [row[0] for row in cur.fetchall()]

    # ── Signal Index ──

    def search_signal_index(self, signal_name: str, module_name: Optional[str] = None) -> list[tuple[str, str]]:
        """搜索信号索引，返回 [(module_name, signal_name), ...]"""
        if module_name:
            cur = self._conn.execute(
                "SELECT module_name, signal_name FROM signal_index WHERE signal_name = ? AND module_name = ?",
                (signal_name, module_name),
            )
        else:
            cur = self._conn.execute(
                "SELECT module_name, signal_name FROM signal_index WHERE signal_name = ?",
                (signal_name,),
            )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def search_signal_index_fuzzy(self, pattern: str, module_name: Optional[str] = None) -> list[tuple[str, str]]:
        """模糊搜索信号索引"""
        if module_name:
            cur = self._conn.execute(
                "SELECT module_name, signal_name FROM signal_index WHERE signal_name LIKE ? AND module_name = ?",
                (f"%{pattern}%", module_name),
            )
        else:
            cur = self._conn.execute(
                "SELECT module_name, signal_name FROM signal_index WHERE signal_name LIKE ?",
                (f"%{pattern}%",),
            )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def _update_signal_index(self, module: ModuleDef) -> None:
        """更新模块的信号索引"""
        # 先删除旧条目
        self._conn.execute(
            "DELETE FROM signal_index WHERE module_name = ?", (module.name,)
        )
        # 插入信号
        entries = set()
        for sig in module.signals:
            entries.add((sig.name, module.name))
        for port in module.ports:
            entries.add((port.name, module.name))
        if entries:
            self._conn.executemany(
                "INSERT OR IGNORE INTO signal_index (signal_name, module_name) VALUES (?, ?)",
                list(entries),
            )

    # ── Type Operations ──

    def save_type(self, type_def: TypeDef) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO types (name, kind, members_json, source_text, file_path, line)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                type_def.name, type_def.kind,
                json.dumps(type_def.members, ensure_ascii=False),
                type_def.source_text, type_def.file_path, type_def.line,
            ),
        )
        self._conn.commit()

    def load_type(self, name: str) -> Optional[TypeDef]:
        cur = self._conn.execute("SELECT * FROM types WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            return None
        return TypeDef(
            name=row[0], kind=row[1],
            members=json.loads(row[2]) if row[2] else [],
            source_text=row[3] or "", file_path=row[4] or "", line=row[5] or 0,
        )

    def load_all_types(self) -> list[TypeDef]:
        cur = self._conn.execute("SELECT * FROM types")
        return [
            TypeDef(
                name=row[0], kind=row[1],
                members=json.loads(row[2]) if row[2] else [],
                source_text=row[3] or "", file_path=row[4] or "", line=row[5] or 0,
            )
            for row in cur.fetchall()
        ]

    # ── File Meta (mtime / sha256) ──

    def get_file_meta(self, file_path: str) -> Optional[dict]:
        cur = self._conn.execute(
            "SELECT mtime, sha256 FROM file_meta WHERE file_path = ?", (file_path,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"mtime": row[0], "sha256": row[1]}

    def set_file_meta(self, file_path: str, mtime: float, sha256: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO file_meta (file_path, mtime, sha256) VALUES (?, ?, ?)",
            (file_path, mtime, sha256),
        )
        self._conn.commit()

    def delete_file_meta(self, file_path: str) -> None:
        self._conn.execute(
            "DELETE FROM file_meta WHERE file_path = ?", (file_path,)
        )
        self._conn.commit()

    def get_all_file_metas(self) -> dict[str, dict]:
        cur = self._conn.execute("SELECT file_path, mtime, sha256 FROM file_meta")
        return {row[0]: {"mtime": row[1], "sha256": row[2]} for row in cur.fetchall()}

    # ── Bulk Operations ──

    def clear_all(self) -> None:
        """清除所有数据"""
        self._conn.execute("DELETE FROM modules")
        self._conn.execute("DELETE FROM files")
        self._conn.execute("DELETE FROM signal_index")
        self._conn.execute("DELETE FROM types")
        self._conn.execute("DELETE FROM file_meta")
        self._conn.execute("DELETE FROM elaborated_instances")
        self._conn.execute("DELETE FROM resolved_signals")
        self._conn.execute("DELETE FROM macro_expansions")
        self._conn.execute("DELETE FROM elaboration_reports")
        self._conn.commit()

    # ── Elaborated Instance Operations ──

    def save_elaborated_instance(self, inst: ElaboratedInstanceDef) -> None:
        self._conn.execute(
            """INSERT INTO elaborated_instances
               (instance_name, module_type, hierarchical_path, parent_module,
                is_generated, generate_condition, generate_source, file_path, line)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                inst.instance_name, inst.module_type, inst.hierarchical_path,
                inst.parent_module, 1 if inst.is_generated else 0,
                inst.generate_condition, inst.generate_source,
                inst.file_path, inst.line,
            ),
        )
        self._conn.commit()

    def get_elaborated_instances_by_module(self, module_type: str) -> list[ElaboratedInstanceDef]:
        cur = self._conn.execute(
            "SELECT * FROM elaborated_instances WHERE module_type = ?",
            (module_type,),
        )
        return [_row_to_elab_instance(_row_to_dict(r)) for r in cur.fetchall()]

    def get_all_elaborated_instances(self) -> list[ElaboratedInstanceDef]:
        cur = self._conn.execute("SELECT * FROM elaborated_instances")
        return [_row_to_elab_instance(_row_to_dict(r)) for r in cur.fetchall()]

    def clear_elaborated_instances(self) -> None:
        self._conn.execute("DELETE FROM elaborated_instances")
        self._conn.commit()

    # ── Resolved Signal Operations ──

    def save_resolved_signal(self, sig: ResolvedSignalDef) -> None:
        self._conn.execute(
            """INSERT INTO resolved_signals
               (name, module_name, var_type, original_width, resolved_width,
                resolved_bit_width, is_signed)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sig.name, sig.module_name, sig.var_type, sig.original_width,
                sig.resolved_width, sig.resolved_bit_width, 1 if sig.is_signed else 0,
            ),
        )
        self._conn.commit()

    def get_resolved_signals_by_module(self, module_name: str) -> list[ResolvedSignalDef]:
        cur = self._conn.execute(
            "SELECT * FROM resolved_signals WHERE module_name = ?",
            (module_name,),
        )
        return [_row_to_resolved_signal(_row_to_dict(r)) for r in cur.fetchall()]

    def get_all_resolved_signals(self) -> list[ResolvedSignalDef]:
        cur = self._conn.execute("SELECT * FROM resolved_signals")
        return [_row_to_resolved_signal(_row_to_dict(r)) for r in cur.fetchall()]

    def clear_resolved_signals(self) -> None:
        self._conn.execute("DELETE FROM resolved_signals")
        self._conn.commit()

    # ── Macro Expansion Operations ──

    def save_macro_expansion(self, macro: MacroExpansionInfo) -> None:
        self._conn.execute(
            """INSERT INTO macro_expansions
               (name, definition, definition_file, definition_line,
                expansion_count, expansion_locations_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                macro.name, macro.definition, macro.definition_file,
                macro.definition_line, macro.expansion_count,
                json.dumps(macro.expansion_locations, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def get_macro_expansions(self) -> list[MacroExpansionInfo]:
        cur = self._conn.execute("SELECT * FROM macro_expansions")
        return [_row_to_macro_expansion(_row_to_dict(r)) for r in cur.fetchall()]

    def clear_macro_expansions(self) -> None:
        self._conn.execute("DELETE FROM macro_expansions")
        self._conn.commit()

    # ── Elaboration Report Operations ──

    def save_elaboration_report(self, report: ElaborationReport) -> int:
        cur = self._conn.execute(
            """INSERT INTO elaboration_reports
               (top_modules_json, total_instances, generated_instances,
                non_generated_instances, unique_module_types, resolved_signals,
                tree_sitter_module_count, pyslang_module_count, error_count,
                warning_count, diagnostics_json, hierarchy_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                json.dumps(report.top_modules, ensure_ascii=False),
                report.total_instances, report.generated_instances,
                report.non_generated_instances, report.unique_module_types,
                report.resolved_signals, report.tree_sitter_module_count,
                report.pyslang_module_count, report.error_count,
                report.warning_count,
                json.dumps(report.diagnostics, ensure_ascii=False),
                json.dumps(report.hierarchy, ensure_ascii=False),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_latest_elaboration_report(self) -> Optional[ElaborationReport]:
        cur = self._conn.execute(
            "SELECT * FROM elaboration_reports ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_elab_report(_row_to_dict(row))

    def get_all_elaboration_reports(self) -> list[ElaborationReport]:
        cur = self._conn.execute(
            "SELECT * FROM elaboration_reports ORDER BY id DESC"
        )
        return [_row_to_elab_report(_row_to_dict(r)) for r in cur.fetchall()]

    def clear_elaboration_reports(self) -> None:
        self._conn.execute("DELETE FROM elaboration_reports")
        self._conn.commit()


def _row_to_dict(row: tuple) -> dict:
    """将 SQLite 行转为 dict，自动推断列名"""
    if hasattr(row, "keys") and callable(row.keys):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def _row_to_elab_instance(row: dict) -> ElaboratedInstanceDef:
    return ElaboratedInstanceDef(
        instance_name=row.get("instance_name", ""),
        module_type=row.get("module_type", ""),
        hierarchical_path=row.get("hierarchical_path", ""),
        parent_module=row.get("parent_module", ""),
        is_generated=bool(row.get("is_generated", 0)),
        generate_condition=row.get("generate_condition", ""),
        generate_source=row.get("generate_source", ""),
        file_path=row.get("file_path", ""),
        line=row.get("line", 0) or 0,
    )


def _row_to_resolved_signal(row: dict) -> ResolvedSignalDef:
    return ResolvedSignalDef(
        name=row.get("name", ""),
        module_name=row.get("module_name", ""),
        var_type=row.get("var_type", "wire"),
        original_width=row.get("original_width", ""),
        resolved_width=row.get("resolved_width", ""),
        resolved_bit_width=row.get("resolved_bit_width", 0) or 0,
        is_signed=bool(row.get("is_signed", 0)),
    )


def _row_to_macro_expansion(row: dict) -> MacroExpansionInfo:
    return MacroExpansionInfo(
        name=row.get("name", ""),
        definition=row.get("definition", ""),
        definition_file=row.get("definition_file", ""),
        definition_line=row.get("definition_line", 0) or 0,
        expansion_count=row.get("expansion_count", 0) or 0,
        expansion_locations=json.loads(row.get("expansion_locations_json") or "[]"),
    )


def _row_to_elab_report(row: dict) -> ElaborationReport:
    return ElaborationReport(
        top_modules=json.loads(row.get("top_modules_json") or "[]"),
        total_instances=row.get("total_instances", 0) or 0,
        generated_instances=row.get("generated_instances", 0) or 0,
        non_generated_instances=row.get("non_generated_instances", 0) or 0,
        unique_module_types=row.get("unique_module_types", 0) or 0,
        resolved_signals=row.get("resolved_signals", 0) or 0,
        tree_sitter_module_count=row.get("tree_sitter_module_count", 0) or 0,
        pyslang_module_count=row.get("pyslang_module_count", 0) or 0,
        error_count=row.get("error_count", 0) or 0,
        warning_count=row.get("warning_count", 0) or 0,
        diagnostics=json.loads(row.get("diagnostics_json") or "[]"),
        hierarchy=json.loads(row.get("hierarchy_json") or "{}"),
    )
