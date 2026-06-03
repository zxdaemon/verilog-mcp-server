"""DomainError 异常层次"""


class DomainError(RuntimeError):
    """所有业务异常的基类"""
    pass


class ModuleNotFoundError(DomainError):
    """模块不存在"""

    def __init__(self, module_name: str):
        super().__init__(f"模块 '{module_name}' 不存在")
        self.module_name = module_name


class SignalNotFoundError(DomainError):
    """信号不存在"""

    def __init__(self, signal_name: str, module_name: str | None = None):
        scope = f" @ {module_name}" if module_name else ""
        super().__init__(f"信号 '{signal_name}' 不存在{scope}")
        self.signal_name = signal_name
        self.module_name = module_name


class IndexNotBuiltError(DomainError):
    """索引未构建"""

    def __init__(self):
        super().__init__("索引为空，请先运行 rtl_build_index 构建索引")


class AnalysisError(DomainError):
    """分析引擎内部错误"""

    def __init__(self, message: str):
        super().__init__(message)
