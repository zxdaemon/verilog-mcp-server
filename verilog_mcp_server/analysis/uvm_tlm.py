"""
UVM TLM 连接分析器 — 分析 TLM 端口声明和 connect 关系
"""

from __future__ import annotations
import logging

from ..database.models import UvmTlmPortDef
from ..indexer.uvm_extractor import UvmExtractor

logger = logging.getLogger(__name__)


class UvmTlmAnalyzer:
    """分析 TLM port 声明和连接拓扑"""

    def __init__(self):
        self._extractor = UvmExtractor()

    def analyze_file(self, tree, source_text: str, file_path: str,
                     classes: list) -> list[UvmTlmPortDef]:
        """分析单个文件中的 TLM 端口和连接

        Returns:
            list[UvmTlmPortDef]: 带连接关系的 TLM 端口定义
        """
        ports: list[UvmTlmPortDef] = []
        root_node = tree.root_node

        # 1. 查找 TLM 端口声明
        port_decls = self._extractor.find_tlm_port_declarations(root_node, source_text)

        # 建立类名映射（用于匹配 port 到组件）
        class_name_map = {c.name: c for c in classes} if classes else {}

        # 2. 查找 TLM connect 调用
        connections = self._extractor.find_tlm_connections(root_node, source_text)

        # 3. 匹配端口声明到连接
        for pd in port_decls:
            port_name = pd["port_name"]
            port_type = pd["port_type"]

            # 查找匹配的 connect
            connected_to = ""
            for conn in connections:
                # conn["source_port"] 如 "agt.mon_ap.connect"
                source = conn["source_port"].replace(".connect", "")
                if source.endswith("." + port_name) or source == port_name:
                    connected_to = conn["target_port"]
                    break

            ports.append(UvmTlmPortDef(
                port_name=port_name,
                port_type=port_type,
                parent_component="",
                connected_to=connected_to,
                file_path=file_path,
                line=pd.get("line", 0),
            ))

        # 4. 对于有连接但未找到声明的，也添加
        for conn in connections:
            source = conn["source_port"].replace(".connect", "")
            port_name = source.split(".")[-1] if "." in source else source

            already = any(p.port_name == port_name for p in ports)
            if not already:
                ports.append(UvmTlmPortDef(
                    port_name=port_name,
                    port_type="unknown",
                    parent_component="",
                    connected_to=conn["target_port"],
                    file_path=file_path,
                    line=conn.get("line", 0),
                ))

        return ports

    def build_connection_graph(self, ports: list[UvmTlmPortDef]) -> dict:
        """构建 TLM 连接图

        Returns:
            {
                "nodes": [{id, label, type}],
                "edges": [{from, to}]
            }
        """
        nodes = {}
        edges = []

        for port in ports:
            port_id = f"{port.parent_component}.{port.port_name}" if port.parent_component else port.port_name
            if port_id not in nodes:
                nodes[port_id] = {
                    "id": port_id,
                    "label": f"{port.port_name}\\n({port.port_type})",
                    "type": self._classify_port(port.port_type),
                }

            if port.connected_to:
                target_id = port.connected_to
                if target_id not in nodes:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": target_id,
                        "type": "unknown",
                    }
                edges.append({
                    "from": port_id,
                    "to": target_id,
                })

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    @staticmethod
    def _classify_port(port_type: str) -> str:
        if "imp" in port_type:
            return "implementation"
        elif "export" in port_type:
            return "export"
        elif "analysis" in port_type:
            return "analysis"
        elif "put" in port_type:
            return "put"
        elif "get" in port_type:
            return "get"
        elif "peek" in port_type:
            return "peek"
        elif "master" in port_type:
            return "master"
        elif "slave" in port_type:
            return "slave"
        elif "transport" in port_type:
            return "transport"
        return "port"

    def format_connections_text(self, ports: list[UvmTlmPortDef]) -> str:
        """格式化 TLM 连接为文本"""
        lines = []
        lines.append(f"TLM Connections ({len(ports)} ports):")
        lines.append("-" * 50)
        for p in ports:
            conn = f" -> {p.connected_to}" if p.connected_to else " (unconnected)"
            lines.append(f"  {p.port_name} [{p.port_type}]{conn}")
        return "\n".join(lines)
