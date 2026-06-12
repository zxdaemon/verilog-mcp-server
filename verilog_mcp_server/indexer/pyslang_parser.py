"""
pyslang 解析器封装 — 提供与现有 verilog_parser.py 风格一致的解析接口

pyslang 是 slang 编译器前端的 Python 绑定，提供完整的 elaboration 能力：
- 预处理（宏展开、条件编译选择）
- 参数求值
- generate 展开
- 类型检查

使用方式：
    parser = PyslangParser(include_dirs=["/path"], defines={"DEBUG": "1"})
    compilation = parser.parse_files(["/path/top.sv"])
    design_root = parser.elaborate(compilation)
    diagnostics = parser.get_diagnostics(compilation)
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Optional

try:
    import pyslang

    PYSLANG_AVAILABLE = True
except ImportError:
    PYSLANG_AVAILABLE = False
    pyslang = None  # type: ignore

logger = logging.getLogger(__name__)


class PyslangParser:
    """封装 pyslang 的解析和 elaboration 流程

    Args:
        include_dirs: include 搜索路径列表
        defines: 预定义宏字典 {name: value}
        top_module: 指定顶层模块名（可选）
    """

    def __init__(
        self,
        include_dirs: Optional[list[str]] = None,
        defines: Optional[dict[str, str]] = None,
        top_module: str = "",
    ):
        if not PYSLANG_AVAILABLE:
            raise RuntimeError("pyslang 未安装，无法创建 PyslangParser")

        self.include_dirs = include_dirs or []
        self.defines = defines or {}
        self.top_module = top_module

    def parse_files(self, file_paths: list[str]) -> Optional["pyslang.ast.Compilation"]:
        """解析多个文件并返回 Compilation 对象

        pyslang 的 Compilation 接受整个设计的文件列表，内部自动处理
        跨文件引用（`include、import、实例化）。

        Args:
            file_paths: RTL 文件路径列表

        Returns:
            Compilation 对象，解析失败时返回 None
        """
        if not file_paths:
            logger.warning("无文件可解析")
            return None

        # 构建预处理器选项
        preproc_opts = pyslang.parsing.PreprocessorOptions()
        preproc_opts.additionalIncludePaths = [Path(p) for p in self.include_dirs]

        # 添加预定义宏
        for name, value in self.defines.items():
            preproc_opts.predefines.append(f"{name}={value}")

        # 构建编译选项
        comp_opts = pyslang.ast.CompilationOptions()
        comp_opts.maxGenerateSteps = 1_000_000
        comp_opts.maxInstanceDepth = 1_000
        comp_opts.maxInstanceArray = 1_000_000

        if self.top_module:
            comp_opts.topModules = {self.top_module}

        bag = pyslang.Bag()
        bag.compilationOptions = comp_opts
        bag.preprocessorOptions = preproc_opts

        # 创建 Compilation
        compilation = pyslang.ast.Compilation(bag)

        # 逐文件创建 SyntaxTree 并加入 Compilation
        successful = 0
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                logger.warning(f"文件不存在，跳过: {fp}")
                continue
            try:
                tree = pyslang.syntax.SyntaxTree.fromFile(str(path))
                if tree:
                    compilation.addSyntaxTree(tree)
                    successful += 1
            except Exception as e:
                logger.warning(f"解析文件失败 {fp}: {e}")

        if successful == 0:
            logger.error("所有文件解析失败")
            return None

        logger.info(f"pyslang 解析完成: {successful}/{len(file_paths)} 文件")
        return compilation

    def elaborate(
        self, compilation: "pyslang.ast.Compilation", top_module: str = ""
    ) -> Optional["pyslang.ast.RootSymbol"]:
        """获取 elaborated design root

        Args:
            compilation: Compilation 对象
            top_module: 指定顶层模块（覆盖构造时传入的）

        Returns:
            RootSymbol（elaborated design root），失败时返回 None
        """
        if compilation is None:
            return None

        try:
            root = compilation.getRoot()
            if root:
                logger.info(f"pyslang elaboration 完成: {len(root.topInstances)} 个顶层实例")
            return root
        except Exception as e:
            logger.error(f"pyslang elaboration 失败: {e}")
            return None

    def get_diagnostics(self, compilation: "pyslang.ast.Compilation") -> list[dict]:
        """提取 Compilation 中的错误/警告信息

        Args:
            compilation: Compilation 对象

        Returns:
            诊断信息列表，每项包含 severity、message、location、code
        """
        if compilation is None:
            return []

        diagnostics = compilation.getAllDiagnostics()
        result = []

        engine = pyslang.DiagnosticEngine(compilation.sourceManager)
        severity_map = {
            pyslang.DiagnosticSeverity.Error: "error",
            pyslang.DiagnosticSeverity.Warning: "warning",
            pyslang.DiagnosticSeverity.Note: "note",
            pyslang.DiagnosticSeverity.Fatal: "fatal",
            pyslang.DiagnosticSeverity.Ignored: "ignored",
        }

        for diag in diagnostics:
            try:
                loc = diag.location
                loc_str = ""
                if loc:
                    try:
                        loc_str = f"{loc.bufferName}:{loc.line}:{loc.column}"
                    except AttributeError:
                        loc_str = str(loc)

                msg = engine.getMessage(diag.code)
                # 格式化消息参数
                try:
                    if diag.args and msg:
                        msg = msg.format(*diag.args)
                except Exception:
                    pass

                severity = engine.getSeverity(diag.code, loc) if loc else pyslang.DiagnosticSeverity.Warning

                result.append({
                    "severity": severity_map.get(severity, "unknown"),
                    "message": msg or str(diag.code),
                    "location": loc_str,
                    "code": str(diag.code),
                    "is_error": severity
                    in (pyslang.DiagnosticSeverity.Error, pyslang.DiagnosticSeverity.Fatal),
                })
            except Exception as e:
                logger.debug(f"处理诊断信息时出错: {e}")
                result.append({
                    "severity": "unknown",
                    "message": str(diag.code),
                    "location": "",
                    "code": str(diag.code),
                    "is_error": diag.isError() if hasattr(diag, "isError") else False,
                })

        return result


def is_pyslang_available() -> bool:
    """检查 pyslang 是否可用"""
    return PYSLANG_AVAILABLE


def get_pyslang_version() -> str:
    """获取 pyslang 版本号，未安装时返回空字符串"""
    if not PYSLANG_AVAILABLE:
        return ""
    return getattr(pyslang, "__version__", "unknown")
