"""
SQLite 后端存储 — 替代 JSON 整体读写
"""

from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional

from .models import ModuleDef, TypeDef

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
"""


class SQLiteBackend:
    """SQLite 存储后端，提供模块、信号、文件映射的 CRUD 操作"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        logger.info(f"SQLite 后端已初始化: {db_path}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Module Operations ──

    def save_module(self, module: ModuleDef) -> None:
        """INSERT OR REPLACE 模块到 modules 表"""
        row = module.to_row()
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
        self._conn.commit()

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
        self._conn.commit()


def _row_to_dict(row: tuple) -> dict:
    """将 SQLite 行转为 dict，供 ModuleDef.from_row() 使用"""
    return {
        "name": row[0],
        "file_path": row[1],
        "line_start": row[2],
        "line_end": row[3],
        "ports_json": row[4],
        "params_json": row[5],
        "signals_json": row[6],
        "instances_json": row[7],
        "always_blocks_json": row[8],
        "assignments_json": row[9],
    }
