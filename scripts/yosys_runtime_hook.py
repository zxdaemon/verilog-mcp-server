"""PyInstaller runtime hook: 确保 yosys 二进制可执行，并设到 PATH"""
import os
import sys
import stat
import logging

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    # PyInstaller frozen 模式：yosys 被提取到 sys._MEIPASS/eda/bin/
    yosys_bundled = os.path.join(sys._MEIPASS, 'eda', 'bin', 'yosys')
    if os.path.isfile(yosys_bundled):
        try:
            # 确保可执行权限（PyInstaller 可能丢失 x 位）
            st = os.stat(yosys_bundled)
            if not (st.st_mode & stat.S_IXUSR):
                os.chmod(yosys_bundled, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            # 将 yosys 目录加入 PATH，使 subprocess 能找到
            yosys_dir = os.path.dirname(yosys_bundled)
            os.environ['PATH'] = yosys_dir + os.pathsep + os.environ.get('PATH', '')
            # 同时设置 YOSYS_BUNDLED_PATH 供 YosysAdapter 直接使用
            os.environ['YOSYS_BUNDLED_PATH'] = yosys_bundled
            logger.info(f"Yosys bundled binary ready: {yosys_bundled}")
        except Exception as e:
            logger.warning(f"Failed to set up bundled yosys: {e}")
