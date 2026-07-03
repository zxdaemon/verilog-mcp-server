"""PyInstaller runtime hook: 重定向 tree-sitter-language-pack 缓存到打包目录"""
import os
import sys

if getattr(sys, '_MEIPASS', None):
    bundled_cache = os.path.join(sys._MEIPASS, 'tree-sitter-cache')
    if os.path.isdir(bundled_cache):
        try:
            from tree_sitter_language_pack._native import configure, PackConfig
            configure(PackConfig(cache_dir=bundled_cache))
        except Exception:
            pass
