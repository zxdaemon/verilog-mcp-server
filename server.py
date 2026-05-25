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

from database.index_store import IndexStore
from indexer.builder import IndexBuilder
from tools import register_level1, register_level2, register_level3

logger = logging.getLogger(__name__)

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
        "path": "/tmp/verilog_mcp_cache.json",
        "auto_load": True,
        "auto_save": True,
    },
}


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
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

    # 初始化索引存储
    cache_path = config.get("cache", {}).get("path")
    index_store = IndexStore(cache_path=cache_path)

    # 尝试加载缓存
    if config.get("cache", {}).get("auto_load", True):
        loaded = index_store.load()
        if loaded:
            logger.info(f"已从缓存加载 {index_store.module_count} 个模块")
        else:
            logger.info("无缓存文件，需要构建索引")

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
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "-p", "--paths",
        nargs="+",
        help="要索引的项目路径（覆盖配置）"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="启动时立即构建索引"
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

    # 如果指定 --build，构建索引
    if args.build:
        logger.info("--build 模式: 启动时构建索引")
        index_store = app._index_store
        builder = IndexBuilder(config, index_store)
        builder.build()

    # 启动 MCP 服务器（使用 stdio 传输）
    logger.info("启动 Verilog MCP 服务器 (stdio)...")
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
