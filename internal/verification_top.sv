`timescale 1ns / 1ps

`undef TRACE_EXECUTION
`define SYNTHESIS 1

module verification_top (
    input logic clk,  // Clock de sistema
    input logic rst_n, // Reset do sistema

    output logic cyc,
    output logic stb,
    output logic we,
    output logic [3:0] sel,
    output logic [31:0] addr,
    output logic [31:0] data_out,
    output logic [31:0] data_in
);

logic [31:0] core_data_in;  // Dados de saída (para leitura)
logic        core_ack;      // Confirmação da transação
logic        core_cyc;      // Indica uma transação ativa
logic        core_stb;      // Indica uma solicitação ativa
logic        core_we;       // 1 = Write, 0 = Read

logic [3:0]  core_sel;      // Seletores de byte
logic [31:0] core_addr;     // Endereço
logic [31:0] core_data_out; // Dados de entrada (para escrita)

`ifdef ENABLE_SECOND_MEMORY
logic        data_mem_cyc;
logic        data_mem_stb;
logic        data_mem_we;
logic [3:0]  data_mem_sel;
logic [31:0] data_mem_addr;
logic [31:0] data_mem_data_out;

logic [31:0] data_mem_data_in;
logic        data_mem_ack;
`endif

`ifdef ENABLE_SECOND_MEMORY
assign cyc      = data_mem_cyc;
assign stb      = data_mem_stb;
assign we       = data_mem_we;
assign sel      = data_mem_sel;
assign addr     = data_mem_addr;
assign data_out = data_mem_data_out;
assign data_in  = data_mem_data_in;
`else
assign cyc      = core_cyc;
assign stb      = core_stb;
assign we       = core_we;
assign sel      = core_sel;
assign addr     = core_addr;
assign data_out = core_data_out;
assign data_in  = core_data_in;
`endif

processorci_top ptop (
    .sys_clk           (clk),     
    .rst_n             (rst_n),   

    .core_cyc          (core_cyc),
    .core_stb          (core_stb),
    .core_we           (core_we),
    .core_sel          (core_sel),
    .core_addr         (core_addr),
    .core_data_out     (core_data_out),
    .core_data_in      (core_data_in),
    .core_ack          (core_ack)

    `ifdef ENABLE_SECOND_MEMORY
    ,
    .data_mem_cyc      (data_mem_cyc),
    .data_mem_stb      (data_mem_stb),
    .data_mem_we       (data_mem_we),
    .data_mem_sel      (data_mem_sel),
    .data_mem_addr     (data_mem_addr),
    .data_mem_data_out (data_mem_data_out),
    .data_mem_data_in  (data_mem_data_in),
    .data_mem_ack      (data_mem_ack)
    `endif
);

// Instância da primeira memória
Memory #(
    .MEMORY_FILE ("processor_ci_connector/internal/memory.hex"), // Arquivo de memória inicial
    .MEMORY_SIZE (4096)
) Memory (
    .clk    (clk),
    
    .cyc_i  (core_cyc),
    .stb_i  (core_stb),
    .we_i   (core_we),
    .sel_i  (core_sel),
    
    .addr_i (core_addr),
    .data_i (core_data_out),
    .data_o (core_data_in),

    .ack_o  (core_ack)
);

`ifdef ENABLE_SECOND_MEMORY
// Instância da segunda memória
Memory #(
    .MEMORY_FILE (""),
    .MEMORY_SIZE (4096)
) SecondMemory (
    .clk    (clk),
    
    .cyc_i  (data_mem_cyc),
    .stb_i  (data_mem_stb),
    .we_i   (data_mem_we),
    .sel_i  (data_mem_sel),

    .addr_i (data_mem_addr),
    .data_i (data_mem_data_out),
    .data_o (data_mem_data_in),

    .ack_o  (data_mem_ack)
);
`endif

endmodule
