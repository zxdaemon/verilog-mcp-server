"""测试 Level 3 分析工具"""

from database.index_store import IndexStore
from database.models import ModuleDef, PortDef, SignalDef, AlwaysBlockInfo


def make_fsm_store() -> IndexStore:
    """创建带 FSM 模块的测试 IndexStore"""
    store = IndexStore()
    store.add_module(ModuleDef(
        name="traffic_light", file_path="tl.v", line_start=1, line_end=50,
        ports=[
            PortDef(name="clk", direction="input"),
            PortDef(name="rst_n", direction="input"),
            PortDef(name="light", direction="output", var_type="reg"),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk or negedge rst_n",
                block_type="sequential",
                statements=[
                    'if (!rst_n) state <= RED;',
                    'else state <= next_state;',
                ],
            ),
            AlwaysBlockInfo(
                sensitivity_list="*",
                block_type="combinational",
                statements=[
                    'case (state)',
                    "  RED: next_state = car_sensor ? GREEN : RED;",
                    "  GREEN: next_state = YELLOW;",
                    "  YELLOW: next_state = RED;",
                    "  default: next_state = RED;",
                    'endcase',
                ],
            ),
        ],
    ))
    return store


class TestAlwaysClassification:
    def test_classify(self):
        from analysis.always_classify import AlwaysClassifier
        store = make_fsm_store()
        classifier = AlwaysClassifier(store)
        result = classifier.classify("traffic_light")
        assert len(result.sequential_blocks) >= 1
        # The FSM block is sequential with a clock
        for b in result.sequential_blocks:
            assert "posedge" in b.sensitivity or "negedge" in b.sensitivity
