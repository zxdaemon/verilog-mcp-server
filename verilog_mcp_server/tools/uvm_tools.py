"""
UVM MCP Tools — UVM 组件层次、TLM 连接、Config DB 追踪
"""

from __future__ import annotations

from ..database.index_store import IndexStore
from ..analysis.uvm_hierarchy import UvmHierarchyBuilder
from ..analysis.uvm_tlm import UvmTlmAnalyzer
from ..analysis.uvm_config_db import UvmConfigDbTracer


def register_tools(mcp, index_store: IndexStore):
    """注册 UVM 分析 tools"""

    hierarchy_builder = UvmHierarchyBuilder(index_store)
    tlm_analyzer = UvmTlmAnalyzer()
    config_tracer = UvmConfigDbTracer()

    @mcp.tool()
    def rtl_uvm_hierarchy(top_component: str = "") -> str:
        """
        显示 UVM 组件层次树

        扫描所有 UVM 组件类，从顶层 test 开始构建组件树。
        分析 build_phase 中的 type_id::create 调用建立父子关系。

        Args:
            top_component: 可选，指定顶层 test 组件名。为空时自动使用 tb_top_module（若已配置），
                          否则列出所有 test 候选。

        Returns:
            UVM 组件层次树文本
        """
        if not top_component:
            top_component = index_store.tb_top_module
        tests = hierarchy_builder.get_test_components()

        if not tests:
            # 列出所有 UVM 组件
            all_uvm = index_store.get_uvm_component_classes()
            if not all_uvm:
                return "未找到 UVM 组件类（不含 is_uvm_component 标记的 class）"

            lines = [f"找到 {len(all_uvm)} 个 UVM 组件类（无 test 顶层）:\n"]
            for c in all_uvm:
                lines.append(f"### {c.name}")
                lines.append(f"- extends: {c.extends}")
                lines.append(f"- uvm_base_class: {c.uvm_base_class}")
                lines.append(f"- 文件: `{c.file_path}` 行 {c.line}")
                lines.append(f"- 成员: {len(c.member_vars)} 个, 方法: {len(c.methods)} 个")
                lines.append("")
            return "\n".join(lines)

        if top_component:
            tests = [t for t in tests if t.component_type == top_component]
            if not tests:
                return f"未找到 test 组件 '{top_component}'"

        lines = []
        for test in tests[:5]:
            lines.append(f"## UVM Test: {test.component_type}")
            lines.append(f"- 文件: `{test.file_path}` 行 {test.line}")
            lines.append(f"- UVM 基类: uvm_test")
            lines.append("")

            # 注: 完整层次构建需要 re-parse 类所在的文件
            # 当前显示所有 UVM 组件类以便进一步分析
            all_uvm = index_store.get_uvm_component_classes()
            if all_uvm:
                lines.append(f"环境中有 {len(all_uvm)} 个 UVM 组件类可构建层次")
                lines.append("")
                for c in all_uvm[:15]:
                    children_hint = ""
                    if c.methods:
                        build_methods = [m for m in c.methods
                                         if m.get("name", "").startswith("build")]
                        if build_methods:
                            children_hint = f" (含 {len(build_methods)} 个 build 方法)"
                    lines.append(f"  - {c.name} [{c.extends}]{children_hint}")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_uvm_component_detail(component_name: str) -> str:
        """
        显示 UVM 组件详细信息

        包含类定义、成员变量、方法列表、UVM 基类信息。

        Args:
            component_name: 组件类名

        Returns:
            组件详细信息文本
        """
        cls_def = index_store.get_class(component_name)
        if not cls_def:
            # 尝试搜索
            results = index_store.search_classes(component_name)
            if results:
                cls_def = results[0]
            else:
                return f"未找到类 '{component_name}'"

        lines = [f"## {cls_def.name}"]
        if cls_def.extends:
            lines.append(f"- extends: {cls_def.extends}")
        if cls_def.type_params:
            lines.append(f"- 类型参数: {', '.join(cls_def.type_params)}")
        if cls_def.is_uvm_component:
            lines.append(f"- UVM 基类: {cls_def.uvm_base_class}")
        lines.append(f"- 文件: `{cls_def.file_path}` 行 {cls_def.line}")
        lines.append("")

        if cls_def.member_vars:
            lines.append(f"### 成员变量 ({len(cls_def.member_vars)}):")
            for v in cls_def.member_vars:
                lines.append(f"  - {v.get('type', '?')} {v.get('name', '?')}")
            lines.append("")

        if cls_def.methods:
            lines.append(f"### 方法 ({len(cls_def.methods)}):")
            for m in cls_def.methods:
                mods = f" [{', '.join(m.get('modifiers', []))}]" if m.get('modifiers') else ""
                ret = f" → {m.get('return_type', '')}" if m.get('return_type') else ""
                lines.append(f"  - {m.get('method_type', 'function')}{ret} {m.get('name', '?')}{mods}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def rtl_uvm_tlm_connections(component_name: str = "") -> str:
        """
        搜索 UVM TLM 端口连接信息

        列出 TLM 端口声明类型和 connect 关系。

        Args:
            component_name: 可选，限定搜索范围到指定组件

        Returns:
            TLM 连接信息文本
        """
        ports = index_store.get_uvm_tlm_connections()

        if component_name:
            ports = [p for p in ports if p.parent_component == component_name
                     or p.port_name == component_name]
            if not ports:
                return f"未找到组件 '{component_name}' 的 TLM 连接"

        if not ports:
            return "索引中暂无 TLM 端口连接信息。\nTLM 数据在 class 文件被索引时自动提取。"

        return tlm_analyzer.format_connections_text(ports)

    @mcp.tool()
    def rtl_uvm_config_trace(field_name: str = "") -> str:
        """
        追踪 uvm_config_db set/get 调用

        显示 config_db 条目的 set/get 配对情况，检测未配对的条目。

        Args:
            field_name: 可选，限定到指定字段名

        Returns:
            config_db 追踪报告文本
        """
        entries = index_store.get_uvm_config_entries()

        if field_name:
            entries = [e for e in entries if e.field_name == field_name]
            if not entries:
                return f"未找到字段 '{field_name}' 的 config_db 条目"

        if not entries:
            return "索引中暂无 uvm_config_db 条目。\nConfig DB 数据在 class 文件被索引时自动提取。"

        return config_tracer.format_report(entries)
