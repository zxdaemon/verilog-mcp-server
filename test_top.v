// ============================================================
// Top-level module with sub-modules for testing the parser
// ============================================================

module adder (
    input  wire [31:0] a,
    input  wire [31:0] b,
    output wire [31:0] sum
);
    assign sum = a + b;
endmodule

module counter (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    output reg  [15:0] count
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 16'h0;
        else if (enable)
            count <= count + 1'b1;
    end
endmodule

module top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] data_a,
    input  wire [31:0] data_b,
    output wire [31:0] result
);
    // Internal signals
    wire [31:0] sum_result;
    wire [15:0] counter_val;
    reg  [31:0] pipeline_reg;
    
    // Module instances
    adder u_adder (
        .a(data_a),
        .b(data_b),
        .sum(sum_result)
    );
    
    counter u_counter (
        .clk(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .count(counter_val)
    );
    
    // Pipeline register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            pipeline_reg <= 32'h0;
        else
            pipeline_reg <= sum_result;
    end
    
    // Output assignment
    assign result = pipeline_reg;

endmodule
