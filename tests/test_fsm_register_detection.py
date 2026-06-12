"""
Tests for register-based FSM detection (non-case patterns)
"""
import pytest

from verilog_mcp_server.database.index_store import IndexStore
from verilog_mcp_server.database.models import (
    ModuleDef, PortDef, SignalDef, AlwaysBlockInfo, DriverInfo, LoadInfo,
)
from verilog_mcp_server.analysis.fsm_detector import FSMDetector


@pytest.fixture
def one_hot_fsm_module():
    """One-hot encoded FSM with direct register assignments"""
    store = IndexStore()

    mod = ModuleDef(
        name="one_hot_fsm",
        file_path="fsm.sv",
        line_start=1,
        line_end=30,
        ports=[
            PortDef(name="clk", direction="input", var_type="wire"),
            PortDef(name="rst_n", direction="input", var_type="wire"),
            PortDef(name="go", direction="input", var_type="wire"),
            PortDef(name="done", direction="output", var_type="wire"),
        ],
        signals=[
            SignalDef(
                name="state", var_type="reg", width_range="[3:0]",
                drivers=[DriverInfo(type="always_block", source="state <= next_state", file_path="fsm.sv", line=5)],
                loads=[LoadInfo(type="always_block", target="case (state)", file_path="fsm.sv", line=12)],
            ),
            SignalDef(name="next_state", var_type="reg", width_range="[3:0]"),
        ],
        always_blocks=[
            # Sequential block
            AlwaysBlockInfo(
                sensitivity_list="posedge clk or negedge rst_n",
                block_type="sequential",
                statements=[
                    "if (!rst_n) state <= 4'b0001;",
                    "else state <= next_state;",
                ],
            ),
            # Combinational block with if-else (no case)
            AlwaysBlockInfo(
                sensitivity_list="@(*)",
                block_type="combinational",
                statements=[
                    "next_state = state;",
                    "done = 1'b0;",
                    "if (state == 4'b0001) begin",
                    "    if (go) next_state = 4'b0010;",
                    "end else if (state == 4'b0010) begin",
                    "    next_state = 4'b0100;",
                    "end else if (state == 4'b0100) begin",
                    "    done = 1'b1;",
                    "    next_state = 4'b0001;",
                    "end",
                ],
            ),
        ],
    )
    store.add_module(mod)
    return store


@pytest.fixture
def binary_if_else_fsm():
    """Binary encoded FSM with if-else chain"""
    store = IndexStore()

    mod = ModuleDef(
        name="binary_fsm",
        file_path="fsm.sv",
        line_start=1,
        line_end=25,
        ports=[
            PortDef(name="clk", direction="input", var_type="wire"),
            PortDef(name="rst", direction="input", var_type="wire"),
            PortDef(name="start", direction="input", var_type="wire"),
        ],
        signals=[
            SignalDef(
                name="state_reg", var_type="reg", width_range="[1:0]",
                drivers=[DriverInfo(type="always_block", source="state_reg <= 2'b01", file_path="fsm.sv", line=5)],
            ),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk",
                block_type="sequential",
                statements=[
                    "if (rst) state_reg <= 2'b00;",
                    "else begin",
                    "    if (state_reg == 2'b00 && start)",
                    "        state_reg <= 2'b01;",
                    "    else if (state_reg == 2'b01)",
                    "        state_reg <= 2'b10;",
                    "    else if (state_reg == 2'b10)",
                    "        state_reg <= 2'b00;",
                    "end",
                ],
            ),
        ],
    )
    store.add_module(mod)
    return store


@pytest.fixture
def counter_not_fsm():
    """Counter — should NOT be detected as FSM"""
    store = IndexStore()

    mod = ModuleDef(
        name="counter",
        file_path="counter.sv",
        line_start=1,
        line_end=15,
        ports=[
            PortDef(name="clk", direction="input", var_type="wire"),
            PortDef(name="rst", direction="input", var_type="wire"),
        ],
        signals=[
            SignalDef(name="cnt", var_type="reg", width_range="[7:0]"),
        ],
        always_blocks=[
            AlwaysBlockInfo(
                sensitivity_list="posedge clk",
                block_type="sequential",
                statements=[
                    "if (rst) cnt <= 8'd0;",
                    "else cnt <= cnt + 8'd1;",
                ],
            ),
        ],
    )
    store.add_module(mod)
    return store


class TestOneHotFSM:
    def test_detects_one_hot_fsm(self, one_hot_fsm_module):
        detector = FSMDetector(one_hot_fsm_module)
        result = detector.detect_fsms("one_hot_fsm")

        assert result.fsm_count >= 1
        fsm = result.fsms[0]
        assert fsm.state_register == "state"
        # Should detect the states from the if-else branches
        assert len(fsm.states) >= 2


class TestBinaryIfElseFSM:
    def test_detects_binary_fsm(self, binary_if_else_fsm):
        detector = FSMDetector(binary_if_else_fsm)
        result = detector.detect_fsms("binary_fsm")

        assert result.fsm_count >= 1
        fsm = result.fsms[0]
        assert fsm.state_register == "state_reg"


class TestCounterNotFSM:
    def test_counter_not_detected(self, counter_not_fsm):
        detector = FSMDetector(counter_not_fsm)
        result = detector.detect_fsms("counter")

        # Counter should not be detected as FSM (arithmetic increment)
        # The filter should exclude it
        assert result.fsm_count == 0


class TestNoRegression:
    def test_existing_case_fsm_still_works(self):
        """Verify case-based FSM detection still works"""
        store = IndexStore()
        mod = ModuleDef(
            name="case_fsm",
            file_path="fsm.sv",
            line_start=1,
            line_end=30,
            ports=[
                PortDef(name="clk", direction="input", var_type="wire"),
                PortDef(name="rst_n", direction="input", var_type="wire"),
            ],
            signals=[
                SignalDef(
                    name="state", var_type="reg", width_range="[1:0]",
                    drivers=[DriverInfo(type="always_block", source="state <= next_state", file_path="fsm.sv", line=5)],
                    loads=[LoadInfo(type="always_block", target="case (state)", file_path="fsm.sv", line=12)],
                ),
                SignalDef(name="next_state", var_type="reg", width_range="[1:0]"),
            ],
            always_blocks=[
                AlwaysBlockInfo(
                    sensitivity_list="posedge clk or negedge rst_n",
                    block_type="sequential",
                    statements=[
                        "if (!rst_n) state <= IDLE;",
                        "else state <= next_state;",
                    ],
                ),
                AlwaysBlockInfo(
                    sensitivity_list="@(*)",
                    block_type="combinational",
                    statements=[
                        "case (state)",
                        "    IDLE: next_state = READY;",
                        "    READY: next_state = BUSY;",
                        "    BUSY: next_state = IDLE;",
                        "endcase",
                    ],
                ),
            ],
        )
        store.add_module(mod)

        detector = FSMDetector(store)
        result = detector.detect_fsms("case_fsm")

        assert result.fsm_count >= 1
        fsm = result.fsms[0]
        assert fsm.state_register == "state"
