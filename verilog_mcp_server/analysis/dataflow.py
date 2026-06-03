"""
信号跨模块追踪引擎 (Dataflow Trace Engine)

重新导出模块 — 实现拆分到 fan_in.py 和 fan_out.py。
"""

from .fan_in import TraceNode, TraceResult, _count_nodes, _max_depth_of
from .fan_out import DataflowTracer

__all__ = ["DataflowTracer", "TraceNode", "TraceResult"]
