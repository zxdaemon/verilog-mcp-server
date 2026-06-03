#!/usr/bin/env python3
"""
Verilog/SystemVerilog RTL 代码语义分析 MCP Server

基于 tree-sitter-language-pack + FastMCP 提供 RTL 代码的
模块搜索、端口列示、例化分析、信号搜索、层次树等功能。
"""

from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from .database.index_store import IndexStore
from .indexer.builder import IndexBuilder
from .tools import register_level1, register_level2, register_level3

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    """获取数据文件目录（兼容 PyInstaller frozen 模式）"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "verilog_mcp_server"
    return Path(__file__).parent


# 默认配置
DEFAULT_CONFIG = {
    "server": {
        "name": "verilog-analyzer",
        "log_level": "INFO",
    },
    "index": {
        "paths": [],
        "extensions": [".v", ".sv", ".svh"],
        "exclude_dirs": [
            "node_modules", ".git", "__pycache__",
            "build", "work", "tb", "test", "tests",
            "sim", "simulation",
        ],
        "exclude_files": ["*_top.sv", "*_top.v"],
        "language_map": {".v": "verilog", ".sv": "systemverilog", ".svh": "systemverilog"},
    },
    "cache": {
        "path": ".verilog_mcp/cache.db",
        "auto_load": True,
        "auto_save": True,
    },
}


def load_config(config_path: str = None) -> dict:
    """加载 YAML 配置文件"""
    if config_path is None:
        config_path = str(_get_data_dir() / "config.yaml")
    path = Path(config_path).expanduser().resolve()
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f)
        # 合并默认配置
        merged = DEFAULT_CONFIG.copy()
        if config:
            merged.update(config)
            for section in ("index", "cache"):
                if section in config:
                    merged[section].update(config[section])
        return merged
    return DEFAULT_CONFIG.copy()


def setup_logging(level: str = "INFO") -> None:
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _try_migrate_json_cache(index_store: IndexStore, db_path: str) -> None:
    """尝试从旧 JSON 缓存迁移到 SQLite"""
    json_path = db_path.replace(".db", ".json")
    if Path(json_path).exists() and index_store.module_count == 0:
        migrated = index_store.migrate_from_json(json_path)
        if migrated:
            logger.info(f"已从旧 JSON 缓存迁移到 SQLite: {json_path} → {db_path}")
            index_store.save()
        else:
            logger.info("JSON 迁移失败或无数据")


def create_app(config: dict) -> FastMCP:
    """
    创建并配置 MCP 应用
    
    Args:
        config: 配置字典
        
    Returns:
        FastMCP 应用实例
    """
    server_config = config.get("server", {})
    mcp = FastMCP(
        server_config.get("name", "verilog-analyzer"),
        log_level=server_config.get("log_level", "INFO"),
    )

    # 初始化索引存储（SQLite 后端）
    cache_path = config.get("cache", {}).get("path")
    db_path = cache_path if cache_path and cache_path.endswith(".db") else None
    index_store = IndexStore(db_path=db_path or cache_path)

    # 启动时自动迁移旧 JSON 缓存
    if db_path and config.get("cache", {}).get("auto_load", True):
        _try_migrate_json_cache(index_store, cache_path)

    # 注册 Level 1 搜索型 tools
    register_level1(mcp, index_store)

    # 注册 Level 2 关联分析 tools
    register_level2(mcp, index_store)

    # 注册 Level 3 智能分析 tools
    register_level3(mcp, index_store)

    # 注册管理 tool: 索引构建
    @mcp.tool()
    def rtl_build_index(paths: list[str] = None) -> str:
        """
        构建/重建 RTL 代码索引
        
        Args:
            paths: 可选，指定要扫描的项目路径列表（覆盖配置文件中的 paths）
            
        Returns:
            索引构建结果统计
        """
        if paths:
            config["index"]["paths"] = paths

        builder = IndexBuilder(config, index_store)
        store = builder.build()

        # 统计数据
        modules = store.get_all_modules()
        total_instances = sum(len(m.instances) for m in modules)
        total_signals = sum(len(m.signals) for m in modules)
        total_ports = sum(len(m.ports) for m in modules)

        return (
            f"✅ 索引构建完成\n"
            f"- 模块: {store.module_count}\n"
            f"- 端口: {total_ports}\n"
            f"- 信号: {total_signals}\n"
            f"- 例化: {total_instances}"
        )

    @mcp.tool()
    def rtl_update_index() -> str:
        """
        增量更新 RTL 代码索引

        自动检测文件变更（mtime + SHA256）、新增和删除的文件，
        仅重新解析变更部分，保留未变更的索引数据。

        Returns:
            增量更新结果统计
        """
        builder = IndexBuilder(config, index_store)
        before_count = index_store.module_count
        store = builder.build_incremental()
        after_count = store.module_count

        modules = store.get_all_modules()
        total_instances = sum(len(m.instances) for m in modules)
        total_signals = sum(len(m.signals) for m in modules)
        total_ports = sum(len(m.ports) for m in modules)

        return (
            f"✅ 索引增量更新完成\n"
            f"- 模块: {after_count}（更新前: {before_count}）\n"
            f"- 端口: {total_ports}\n"
            f"- 信号: {total_signals}\n"
            f"- 例化: {total_instances}"
        )

    @mcp.tool()
    def rtl_index_status() -> str:
        """
        查看当前索引状态（模块数、文件数等）
        
        Returns:
            索引统计信息
        """
        modules = index_store.get_all_modules()
        if not modules:
            return "当前索引为空，请先运行 rtl_build_index 构建索引"

        files = set(m.file_path for m in modules)
        total_instances = sum(len(m.instances) for m in modules)
        total_signals = sum(len(m.signals) for m in modules)
        total_ports = sum(len(m.ports) for m in modules)

        # 统计各语言分布
        lang_count: dict[str, int] = {}
        for m in modules:
            if m.file_path.endswith(".sv") or m.file_path.endswith(".svh"):
                lang = "SystemVerilog"
            else:
                lang = "Verilog"
            lang_count[lang] = lang_count.get(lang, 0) + 1

        lines = [
            "📊 **索引统计**",
            f"- 模块总数: {len(modules)}",
            f"- 文件总数: {len(files)}",
            f"- 端口总数: {total_ports}",
            f"- 信号总数: {total_signals}",
            f"- 例化总数: {total_instances}",
            f"- 语言分布: {', '.join(f'{k}: {v}' for k, v in lang_count.items())}",
        ]
        return "\n".join(lines)

    # 将 index_store 暴露为工具可访问的属性
    mcp._index_store = index_store

    return mcp


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="Verilog/SystemVerilog MCP 代码语义分析服务器"
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="配置文件路径 (默认: 包内 config.yaml)"
    )
    parser.add_argument(
        "-p", "--paths",
        nargs="+",
        help="要索引的项目路径（覆盖配置）"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="启动时构建索引（已有索引时增量更新）"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="启动时强制全量重建索引（忽略已有缓存）"
    )
    parser.add_argument(
        "--cache",
        help="缓存文件路径（覆盖配置）"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    if args.paths:
        config["index"]["paths"] = args.paths
    if args.cache:
        config["cache"]["path"] = args.cache

    # 设置日志
    log_level = args.log_level or config.get("server", {}).get("log_level", "INFO")
    setup_logging(log_level)

    # 创建应用
    app = create_app(config)

    # 构建索引
    if args.rebuild:
        logger.info("--rebuild 模式: 强制全量重建索引")
        index_store = app._index_store
        builder = IndexBuilder(config, index_store)
        builder.build()
    elif args.build:
        index_store = app._index_store
        builder = IndexBuilder(config, index_store)
        if index_store.module_count > 0:
            logger.info("--build 模式: 检测到已有索引，执行增量更新")
            builder.build_incremental()
        else:
            logger.info("--build 模式: 无已有索引，执行全量构建")
            builder.build()

    # 启动 MCP 服务器（使用 stdio 传输）
    logger.info("启动 Verilog MCP 服务器 (stdio)...")
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
