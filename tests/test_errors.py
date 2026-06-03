"""测试 DomainError 异常层次"""

from verilog_mcp_server.database.errors import (
    DomainError, ModuleNotFoundError, SignalNotFoundError,
    IndexNotBuiltError, AnalysisError,
)


def test_module_not_found_error():
    err = ModuleNotFoundError("top")
    assert isinstance(err, DomainError)
    assert err.module_name == "top"
    assert "top" in str(err)


def test_signal_not_found_error():
    err = SignalNotFoundError("clk", module_name="counter")
    assert isinstance(err, DomainError)
    assert err.signal_name == "clk"
    assert err.module_name == "counter"
    assert "counter" in str(err)


def test_signal_not_found_error_no_module():
    err = SignalNotFoundError("data")
    assert err.module_name is None
    assert "data" in str(err)


def test_index_not_built_error():
    err = IndexNotBuiltError()
    assert isinstance(err, DomainError)
    assert "rtl_build_index" in str(err)


def test_analysis_error():
    err = AnalysisError("分析失败")
    assert isinstance(err, DomainError)
    assert str(err) == "分析失败"


def test_all_inherit_from_domain_error():
    assert issubclass(ModuleNotFoundError, DomainError)
    assert issubclass(SignalNotFoundError, DomainError)
    assert issubclass(IndexNotBuiltError, DomainError)
    assert issubclass(AnalysisError, DomainError)
