"""
索引构建器 — 协调各提取器，完成完整索引
"""

from __future__ import annotations
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from .project_scanner import ProjectScanner
from .verilog_parser import parse_file
from .module_extractor import ModuleExtractor
from .port_extractor import PortExtractor
from .instance_extractor import InstanceExtractor
from .signal_extractor import SignalExtractor
from .type_extractor import TypeExtractor
from .package_extractor import PackageExtractor
from .sva_extractor import SvaExtractor
from .macro_extractor import MacroExtractor
from .function_task_extractor import FunctionTaskExtractor
from .pyslang_parser import PyslangParser, is_pyslang_available
from .pyslang_extractor import PyslangExtractor
from ..database.index_store import IndexStore
from ..eda.yosys_adapter import YosysAdapter
from ..eda.cache import EdaCache

logger = logging.getLogger(__name__)


class IndexBuilder:
    """协调扫描、解析、提取流程，构建完整索引"""

    def __init__(self, config: dict, index_store: IndexStore):
        self.config = config
        self.index_store = index_store
        self.scanner = ProjectScanner(config.get("index", {}))
        self.module_extractor = ModuleExtractor()
        self.port_extractor = PortExtractor()
        self.instance_extractor = InstanceExtractor()
        self.instance_extractor._index_store = index_store
        self.signal_extractor = SignalExtractor()
        self.type_extractor = TypeExtractor()
        self.package_extractor = PackageExtractor()
        self.sva_extractor = SvaExtractor()
        self.macro_extractor = MacroExtractor()
        self.function_task_extractor = FunctionTaskExtractor()
        self.pyslang_extractor = PyslangExtractor()

    def build(self, incremental: bool = False, yosys_enabled: bool = False) -> IndexStore:
        """构建索引

        Args:
            incremental: True 时自动检测变更文件并增量构建，False 时全量重建
            yosys_enabled: True 时在构建完成后运行 Yosys 综合分析
        """
        if incremental:
            return self.build_incremental()

        logger.info("开始构建索引...")
        self.index_store.clear()

        files, filelist_incdirs, filelist_defines = self.scanner.scan()
        total_files = len(files)
        parsed_count = 0
        module_count = 0

        # 并行解析（文件数 >= 10 时启用）
        max_workers = self.config.get("index", {}).get("max_workers", None)
        parsed_results = self._parse_files(files, max_workers=max_workers)

        for i, (fp, tree, source_text) in enumerate(parsed_results):
            parsed_count += 1

            # 文件级: 提取 package 定义和宏
            for pkg in self.package_extractor.extract_package_defs(tree, source_text, fp):
                self.index_store.add_package(pkg)
                for td in pkg.typedefs:
                    self.index_store.add_type(td)

            modules = self.module_extractor.extract(tree, source_text, fp)
            if not modules:
                continue

            for mod, module_node in modules:
                mod.ports = self.port_extractor.extract_from_module(module_node, source_text)
                mod.package_imports = self.package_extractor.extract_imports_from_module(
                    module_node, source_text)
                mod.assertions = self.sva_extractor.extract_from_module(
                    module_node, source_text)
                for func in self.function_task_extractor.extract_from_module(module_node, source_text, fp):
                    self.index_store.add_function(func)
                mod.is_testbench, mod.has_non_synth_constructs = \
                    self.signal_extractor.detect_testbench(module_node, source_text)
                body_node = module_node
                mod.signals = self.signal_extractor.extract_signals(body_node, source_text)
                mod.instances = self.instance_extractor.extract_from_module_body(body_node, source_text, fp)
                mod.assignments = self.signal_extractor.extract_assignments(body_node, source_text, fp)
                mod.always_blocks = self.signal_extractor.extract_always_blocks(body_node, source_text)

                drivers_map, loads_map = self.signal_extractor.extract_drivers_and_loads(
                    body_node, source_text, fp)
                for sig in mod.signals:
                    sig.drivers = drivers_map.get(sig.name, [])
                    sig.loads = loads_map.get(sig.name, [])

                for td in self.type_extractor.extract_types(body_node, source_text, fp):
                    self.index_store.add_type(td)

                self.index_store.add_module(mod)
                module_count += 1

            # 更新文件元信息
            self._update_file_meta(fp)

            if (i + 1) % 50 == 0:
                logger.info(f"索引进度: {i+1}/{total_files} 文件, {module_count} 模块")

        logger.info(f"索引完成: {parsed_count}/{total_files} 文件, {module_count} 模块")

        if self.config.get("cache", {}).get("auto_save", True):
            self.index_store.save()

        # ── pyslang elaboration 步骤 ──
        self._run_pyslang_elaboration(file_paths=files, filelist_incdirs=filelist_incdirs, filelist_defines=filelist_defines)

        # ── Yosys 综合分析步骤 ──
        if yosys_enabled:
            self._run_yosys_analysis(file_paths=files)

        return self.index_store

    def _parse_files(self, files, max_workers=None) -> list[tuple[str, object, str]]:
        """解析文件列表，支持并行（>=10 文件时自动并行）"""
        from .verilog_parser import parse_single_file

        PARALLEL_THRESHOLD = 10
        file_strs = [str(f) for f in files]

        # tree-sitter (PyO3/Rust) 的 Parser/Tree 对象有线程亲和性限制，
        # 不可跨线程使用。这里始终串行解析。
        if True or len(file_strs) < PARALLEL_THRESHOLD:
            # 串行解析
            results = []
            for fp in file_strs:
                r = parse_single_file(fp)
                if r:
                    results.append(r)
            return results

        # 以下并行代码保留但永不执行（因 tree-sitter 线程限制）
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import multiprocessing

        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 8)

        logger.info(f"并行解析 {len(file_strs)} 文件 (workers={max_workers})")
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(parse_single_file, fp): fp for fp in file_strs}
            for future in as_completed(futures):
                r = future.result()
                if r:
                    results.append(r)

        logger.info(f"并行解析完成: {len(results)}/{len(file_strs)} 文件")
        return results

    def _run_pyslang_elaboration(self, file_paths: list = None, force: bool = False,
                                 filelist_incdirs: list[str] = None,
                                 filelist_defines: dict[str, str] = None) -> None:
        """运行 pyslang elaboration 并提取增强数据

        Args:
            file_paths: RTL 文件路径列表。为 None 时自动扫描。
            force: 是否强制重新运行（忽略缓存）
            filelist_incdirs: .f 文件中收集的 include 路径
            filelist_defines: .f 文件中收集的宏定义
        """
        pyslang_config = self.config.get("pyslang", {})
        if not pyslang_config.get("enabled", True):
            logger.debug("pyslang 已禁用，跳过 elaboration")
            return

        if not is_pyslang_available():
            logger.info("pyslang 未安装，跳过 elaboration（tree-sitter 索引不受影响）")
            return

        if file_paths is None:
            file_paths, filelist_incdirs, filelist_defines = self.scanner.scan()

        file_strs = [str(fp) for fp in file_paths]
        if not file_strs:
            return

        # 合并 include dirs: config 优先 + filelist 补充
        config_incdirs = pyslang_config.get("include_dirs", [])
        merged_incdirs = list(config_incdirs)
        for d in (filelist_incdirs or []):
            if d not in merged_incdirs:
                merged_incdirs.append(d)

        # 合并 defines: config 覆盖 filelist
        merged_defines = dict(filelist_defines or {})
        merged_defines.update(pyslang_config.get("defines", {}))

        try:
            parser = PyslangParser(
                include_dirs=merged_incdirs,
                defines=merged_defines,
                top_module=pyslang_config.get("top_module", ""),
            )

            compilation = parser.parse_files(file_strs)
            if not compilation:
                logger.warning("pyslang 解析失败，无 elaboration 数据")
                return

            design_root = parser.elaborate(compilation)
            if not design_root:
                logger.warning("pyslang elaboration 失败")
                return

            diagnostics = parser.get_diagnostics(compilation)

            # 提取 elaborated 实例
            instances = self.pyslang_extractor.extract_elaborated_instances(design_root)
            if instances:
                self.index_store.save_elab_instances(instances)

            # 提取 resolved 信号
            signals = self.pyslang_extractor.extract_resolved_signals(design_root)
            if signals:
                self.index_store.save_resolved_signals(signals)

            # 构建并保存报告
            ts_module_count = self.index_store.module_count
            report = self.pyslang_extractor.build_report(
                design_root, ts_module_count, diagnostics
            )
            self.index_store.save_elab_report(report)

            logger.info(
                f"pyslang elaboration 完成: {report.total_instances} 实例, "
                f"{report.generated_instances} generate 展开, "
                f"{report.resolved_signals} 信号, "
                f"{report.error_count} 错误, {report.warning_count} 警告"
            )

        except Exception as e:
            logger.warning(f"pyslang elaboration 异常: {e}")
            # 不阻塞 tree-sitter 索引

    # ── Incremental Build ──

    def build_incremental(self, changed_files: Optional[list[str]] = None) -> IndexStore:
        """增量构建索引，仅重新解析变更文件

        Args:
            changed_files: 指定要重新解析的文件列表。为 None 时自动检测变更。
        """
        logger.info("开始增量构建索引...")

        if not changed_files:
            changed_files = self._detect_changed_files()

        # 同时处理新增和删除的文件
        new_files = self._detect_new_files()
        deleted_files = self._detect_deleted_files()

        all_changed = list(set(changed_files + new_files))

        if not all_changed and not deleted_files:
            logger.info("无文件变更，跳过增量构建")
            return self.index_store
        total_ops = len(all_changed) + len(deleted_files)
        logger.info(f"增量构建: {len(all_changed)} 文件需重新解析, {len(deleted_files)} 文件已删除")

        # 删除已不存在的文件
        for fp in deleted_files:
            self.index_store.remove_file(fp)
            logger.debug(f"已删除文件索引: {fp}")

        # 重新解析变更文件
        module_count = 0
        for i, file_path in enumerate(all_changed):
            self.index_store.remove_file(file_path)
            self._parse_and_index_file(file_path)
            if (i + 1) % 50 == 0:
                logger.info(f"增量进度: {i+1}/{len(all_changed)} 文件")

        # 更新文件元信息
        for fp in all_changed:
            self._update_file_meta(fp)

        logger.info(f"增量构建完成: {len(all_changed)} 文件重新解析, {len(deleted_files)} 文件删除")

        if self.config.get("cache", {}).get("auto_save", True):
            self.index_store.save()

        # ── 增量构建时条件触发 pyslang elaboration ──
        if self._should_trigger_pyslang(all_changed):
            logger.info("变更涉及接口/结构，触发 pyslang elaboration")
            all_files, incdirs, defines = self.scanner.scan()
            self._run_pyslang_elaboration(file_paths=all_files, filelist_incdirs=incdirs, filelist_defines=defines)
        else:
            logger.debug("变更不涉及接口/结构，跳过 pyslang elaboration")

        return self.index_store

    def _should_trigger_pyslang(self, changed_files: list[str]) -> bool:
        """判断变更文件是否应触发 pyslang elaboration 重跑

        轻量变更（assign 语句改值、内部逻辑改表达式）不触发
        接口变更（端口增删、parameter 值变化、generate 条件、模块例化增删）触发
        """
        if not changed_files:
            return False

        # 简单启发式：检查文件内容关键词
        pyslang_keywords = (
            b"parameter", b"localparam", b"generate", b"genvar",
            b"defparam", b"module", b"endmodule", b"instance",
            b"`define", b"`ifdef", b"`ifndef", b"`include",
        )
        for fp in changed_files:
            try:
                with open(fp, "rb") as f:
                    content = f.read(32768)  # 读取前 32KB
                    lower = content.lower()
                    for kw in pyslang_keywords:
                        if kw in lower:
                            return True
            except OSError:
                continue
        return False

    def _detect_changed_files(self) -> list[str]:
        """通过 mtime + SHA256 检测变更文件"""
        if not self.index_store._db:
            return []

        scanned, _, _ = self.scanner.scan()
        stored_metas = self.index_store._db.get_all_file_metas()
        changed = []

        for file_path in scanned:
            fp = str(file_path)
            stored = stored_metas.get(fp)
            if stored is None:
                # 新文件
                changed.append(fp)
                continue
            try:
                current_mtime = os.path.getmtime(fp)
                if current_mtime != stored["mtime"]:
                    current_sha = self._compute_file_hash(fp)
                    if current_sha != stored["sha256"]:
                        changed.append(fp)
            except OSError:
                changed.append(fp)

        return changed

    def _detect_new_files(self) -> list[str]:
        """检测扫描结果中存在但数据库中不存在的文件"""
        if not self.index_store._db:
            return []

        scanned = {str(fp) for fp in self.scanner.scan()[0]}
        stored = set(self.index_store._db.get_all_file_metas().keys())
        return list(scanned - stored)

    def _detect_deleted_files(self) -> list[str]:
        """检测数据库中存在但文件系统中已不存在的文件"""
        if not self.index_store._db:
            return []

        stored = self.index_store._db.get_all_file_metas()
        return [fp for fp in stored if not Path(fp).exists()]

    def _update_file_meta(self, file_path: str) -> None:
        """更新文件的 mtime 和 SHA256 到数据库"""
        if not self.index_store._db:
            return
        try:
            mtime = os.path.getmtime(file_path)
            sha = self._compute_file_hash(file_path)
            self.index_store._db.set_file_meta(file_path, mtime, sha)
        except OSError:
            pass

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """计算文件 SHA256"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _parse_and_index_file(self, file_path: str) -> int:
        """解析单个文件并将其模块添加到索引，返回模块数"""
        result = parse_file(file_path)
        if result is None:
            return 0

        tree, source_text = result

        # 文件级: 提取 package 定义
        for pkg in self.package_extractor.extract_package_defs(tree, source_text, file_path):
            self.index_store.add_package(pkg)
            for td in pkg.typedefs:
                self.index_store.add_type(td)

        modules = self.module_extractor.extract(tree, source_text, file_path)
        if not modules:
            return 0

        count = 0
        for mod, module_node in modules:
            mod.ports = self.port_extractor.extract_from_module(module_node, source_text)
            mod.package_imports = self.package_extractor.extract_imports_from_module(
                module_node, source_text)
            mod.assertions = self.sva_extractor.extract_from_module(
                module_node, source_text)
            for func in self.function_task_extractor.extract_from_module(module_node, source_text, file_path):
                self.index_store.add_function(func)
            body_node = module_node
            mod.signals = self.signal_extractor.extract_signals(body_node, source_text)
            mod.instances = self.instance_extractor.extract_from_module_body(body_node, source_text, file_path)
            mod.assignments = self.signal_extractor.extract_assignments(body_node, source_text, file_path)
            mod.always_blocks = self.signal_extractor.extract_always_blocks(body_node, source_text)

            drivers_map, loads_map = self.signal_extractor.extract_drivers_and_loads(
                body_node, source_text, file_path)
            for sig in mod.signals:
                sig.drivers = drivers_map.get(sig.name, [])
                sig.loads = loads_map.get(sig.name, [])

            for td in self.type_extractor.extract_types(body_node, source_text, file_path):
                self.index_store.add_type(td)

            self.index_store.add_module(mod)
            count += 1

        return count

    def _run_yosys_analysis(self, file_paths: list = None) -> None:
        """运行 Yosys 综合分析并提取数据"""
        yosys_config = self.config.get("yosys", {})
        top_module = self.config.get("pyslang", {}).get("top_module", "")
        if not top_module:
            logger.warning("Yosys 分析需要指定 --top，已跳过")
            return
        if file_paths is None:
            file_paths, _, _ = self.scanner.scan()
        file_strs = [str(fp) for fp in file_paths]
        if not file_strs:
            return

        adapter = YosysAdapter(config=yosys_config)
        if not adapter.is_available():
            logger.warning("Yosys 未安装或不可用，跳过综合分析")
            return

        cache_dir = yosys_config.get("output_dir", ".verilog_mcp/yosys_outputs")
        cache = EdaCache(cache_dir)
        cache_key = cache.check(file_strs, top_module)
        if cache_key:
            try:
                self._import_yosys_results(cache.load(cache_key))
                logger.info("Yosys 分析: 缓存命中")
                return
            except Exception as e:
                logger.warning(f"Yosys 缓存加载失败: {e}")

        logger.info(f"运行 Yosys 综合分析 (top={top_module})...")
        if not adapter.run(file_strs, top_module, cache_dir):
            logger.warning("Yosys 运行失败")
            return
        try:
            results = adapter.parse_output(cache_dir)
            self._import_yosys_results(results)
            cache.save(cache.compute_files_hash(list(file_strs) + [f"__top__:{top_module}"]), results)
            logger.info("Yosys 综合分析完成")
        except Exception as e:
            logger.warning(f"Yosys 解析异常: {e}")

    def _import_yosys_results(self, results: dict) -> None:
        """将 Yosys 解析结果导入 index_store"""
        from ..database.models import YosysFsmDef, YosysCombLoopDef, YosysGatedClockDef, YosysStatDef
        for fsm_data in results.get("fsms", []):
            self.index_store.add_yosys_fsm(YosysFsmDef.from_dict(fsm_data))
        for loop_data in results.get("comb_loops", []):
            self.index_store.add_yosys_comb_loop(YosysCombLoopDef.from_dict(loop_data))
        for clock_data in results.get("gated_clocks", []):
            self.index_store.add_yosys_gated_clock(YosysGatedClockDef.from_dict(clock_data))
        for stat_data in results.get("stats", []):
            self.index_store.add_yosys_stat(YosysStatDef.from_dict(stat_data))

