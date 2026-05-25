// Moore-type FSM: 3-state traffic light controller
// Binary encoding: RED=2'b00, YELLOW=2'b01, GREEN=2'b10
module traffic_light (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       car_sensor,
    output reg  [1:0] light
);
    reg  [1:0] state, next_state;
    localparam RED    = 2'b00;
    localparam YELLOW = 2'b01;
    localparam GREEN  = 2'b10;

    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= RED;
        else
            state <= next_state;
    end

    // Next state logic
    always @(*) begin
        case (state)
            RED:    next_state = car_sensor ? GREEN : RED;
            YELLOW: next_state = RED;
            GREEN:  next_state = YELLOW;
            default: next_state = RED;
        endcase
    end

    // Output logic
    always @(*) begin
        case (state)
            RED:    light = 2'b01;
            YELLOW: light = 2'b10;
            GREEN:  light = 2'b100;
            default: light = 2'b01;
        endcase
    end
endmodule

// Mealy-type FSM: edge detector
module edge_detector (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       data_in,
    output reg        rising_edge,
    output reg        falling_edge
);
    reg  [1:0] state;
    localparam IDLE = 2'b00;
    localparam HIGH = 2'b01;
    localparam LOW  = 2'b10;

    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= IDLE;
        else begin
            case (state)
                IDLE: begin
                    if (data_in) state <= HIGH;
                    else         state <= LOW;
                end
                HIGH: begin
                    if (!data_in) state <= LOW;
                    else          state <= HIGH;
                end
                LOW: begin
                    if (data_in) state <= HIGH;
                    else         state <= LOW;
                end
                default: state <= IDLE;
            endcase
        end
    end

    // Output logic - Mealy: output depends on state AND input
    always @(*) begin
        rising_edge  = 1'b0;
        falling_edge = 1'b0;
        case (state)
            IDLE: begin
                rising_edge  = data_in;
                falling_edge = !data_in;
            end
            HIGH: begin
                falling_edge = !data_in;
            end
            LOW: begin
                rising_edge = data_in;
            end
        endcase
    end
endmodule

// One-hot FSM: arbiter
module arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [2:0] request,
    output reg  [2:0] grant
);
    reg  [2:0] state;
    // one-hot encoding
    localparam IDLE  = 3'b001;
    localparam GRANT_A = 3'b010;
    localparam GRANT_B = 3'b100;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= IDLE;
        else begin
            case (state)
                IDLE: begin
                    if (request[0])     state <= GRANT_A;
                    else if (request[1]) state <= GRANT_B;
                    else                state <= IDLE;
                end
                GRANT_A: begin
                    if (request[0]) state <= GRANT_A;
                    else            state <= IDLE;
                end
                GRANT_B: begin
                    if (request[1]) state <= GRANT_B;
                    else            state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end

    always @(*) begin
        grant = 3'b000;
        case (state)
            IDLE:    grant = 3'b000;
            GRANT_A: grant = 3'b001;
            GRANT_B: grant = 3'b010;
        endcase
    end
endmodule
