module MemorySync #(
    parameter MEMORY_FILE = "",
    parameter MEMORY_SIZE = 4096
)(
    input  logic        clk,
    input  logic        rst_n,

    input  logic        cyc_i,
    input  logic        stb_i,
    input  logic        we_i,

    input  logic [31:0] addr_i,
    input  logic [31:0] data_i,
    input  logic [2:0]  size_i,

    output logic [31:0] data_o,
    output logic        ack_o
);

    // =========================================================
    // Memory declaration
    // =========================================================

    localparam WORD_COUNT = MEMORY_SIZE / 4;
    localparam ADDR_WIDTH =
        (WORD_COUNT <= 1) ? 1 : $clog2(WORD_COUNT);

    (* ram_style = "block" *)
    logic [31:0] memory [0:WORD_COUNT-1];

    initial begin
        if (MEMORY_FILE != "")
            $readmemh(MEMORY_FILE, memory);
    end

    // =========================================================
    // Request detection
    // =========================================================

    logic req;
    logic req_d;
    logic req_rise;

    assign req = cyc_i && stb_i;
    assign req_rise = req && !req_d;

    // =========================================================
    // Transaction registers
    // =========================================================

    logic                  write_reg;
    logic [31:0]           write_data_reg;

    logic [ADDR_WIDTH-1:0] word_addr;
    logic [1:0]            byte_offset;
    logic [2:0]            size_reg;

    logic                  cross_word;

    logic [31:0] word0;
    logic [31:0] word1;

    logic [31:0] modified_word0;
    logic [31:0] modified_word1;

    // =========================================================
    // SINGLE MEMORY PORT INTERFACE
    // =========================================================

    logic                  mem_rd_en;
    logic                  mem_wr_en;

    logic [ADDR_WIDTH-1:0] mem_addr;
    logic [31:0]           mem_wdata;
    logic [31:0]           mem_rdata;

    logic [ADDR_WIDTH-1:0] next_word_addr;

    assign next_word_addr = word_addr + 1'b1;

    // =========================================================
    // Memory address and operation selection
    // =========================================================

    typedef enum logic [2:0] {
        M_IDLE,
        M_READ0,
        M_READ1,
        M_WRITE0,
        M_WRITE1
    } mstate_t;

    mstate_t mstate;

    always_comb begin

        mem_rd_en = 1'b0;
        mem_wr_en = 1'b0;

        mem_addr  = '0;
        mem_wdata = '0;

        unique case (mstate)

            M_IDLE: begin
                if (req_rise) begin
                    mem_rd_en = 1'b1;
                    mem_addr  = addr_i[ADDR_WIDTH+1:2];
                end
            end

            M_READ0: begin
                if (cross_word) begin
                    mem_rd_en = 1'b1;
                    mem_addr  = next_word_addr;
                end
            end

            M_WRITE0: begin
                mem_wr_en = 1'b1;
                mem_addr  = word_addr;
                mem_wdata = modified_word0;
            end

            M_WRITE1: begin
                mem_wr_en = 1'b1;
                mem_addr  = next_word_addr;
                mem_wdata = modified_word1;
            end

            default: begin
                // No memory operation.
            end

        endcase

    end

    // =========================================================
    // PHYSICAL MEMORY ACCESS
    //
    // Only one read expression and one write expression.
    // No reset on the BRAM output register.
    // Read and write are mutually exclusive.
    // =========================================================

    always_ff @(posedge clk) begin

        if (mem_wr_en) begin

            memory[mem_addr] <= mem_wdata;

        end else if (mem_rd_en) begin

            mem_rdata <= memory[mem_addr];

        end

    end

    // =========================================================
    // Access size and boundary detection
    // =========================================================

    logic [2:0] access_bytes;
    logic [3:0] access_end;

    always_comb begin
        unique case (size_i[1:0])
            2'b00:   access_bytes = 3'd1;
            2'b01:   access_bytes = 3'd2;
            default: access_bytes = 3'd4;
        endcase
    end

    assign access_end =
        {2'b00, addr_i[1:0]} + {1'b0, access_bytes};

    // =========================================================
    // Store mask and alignment
    // =========================================================

    logic [63:0] base_mask;
    logic [63:0] store_mask;
    logic [63:0] store_data;

    always_comb begin

        unique case (size_reg[1:0])
            2'b00:   base_mask = 64'h00000000000000FF;
            2'b01:   base_mask = 64'h000000000000FFFF;
            default: base_mask = 64'h00000000FFFFFFFF;
        endcase

        store_mask =
            base_mask << (byte_offset * 8);

        store_data =
            {32'b0, write_data_reg} << (byte_offset * 8);

    end

    // =========================================================
    // Read assembly
    // =========================================================

    logic [63:0] read_pair;

    assign read_pair = {mem_rdata, word0};

    // =========================================================
    // Store word generation
    // =========================================================

    always_comb begin

        modified_word0 =
            (word0 & ~store_mask[31:0]) |
            (store_data[31:0] & store_mask[31:0]);

        modified_word1 =
            (word1 & ~store_mask[63:32]) |
            (store_data[63:32] & store_mask[63:32]);

    end

    // =========================================================
    // FSM
    // =========================================================

    always_ff @(posedge clk) begin

        if (!rst_n) begin

            mstate <= M_IDLE;
            req_d  <= 1'b0;

            ack_o  <= 1'b0;
            data_o <= 32'b0;

        end else begin

            req_d <= req;

            ack_o <= 1'b0;

            unique case (mstate)

                // ---------------------------------------------
                // IDLE
                // ---------------------------------------------

                M_IDLE: begin

                    if (req_rise) begin

                        write_reg      <= we_i;
                        write_data_reg <= data_i;

                        word_addr <= addr_i[ADDR_WIDTH+1:2];

                        byte_offset <= addr_i[1:0];
                        size_reg    <= size_i;

                        cross_word <= (access_end > 4'd4);

                        mstate <= M_READ0;

                    end

                end

                // ---------------------------------------------
                // First word has been read
                // ---------------------------------------------

                M_READ0: begin

                    word0 <= mem_rdata;

                    if (cross_word) begin

                        // Second word read is initiated by the
                        // memory interface.

                        mstate <= M_READ1;

                    end else begin

                        if (write_reg) begin

                            mstate <= M_WRITE0;

                        end else begin

                            data_o <=
                                mem_rdata >> (byte_offset * 8);

                            ack_o  <= 1'b1;
                            mstate <= M_IDLE;

                        end

                    end

                end

                // ---------------------------------------------
                // Second word has been read
                // =============================================

                M_READ1: begin

                    if (write_reg) begin

                        word1 <= mem_rdata;
                        mstate <= M_WRITE0;

                    end else begin

                        data_o <=
                            read_pair >> (byte_offset * 8);

                        ack_o  <= 1'b1;
                        mstate <= M_IDLE;

                    end

                end

                // ---------------------------------------------
                // First word write
                // =============================================

                M_WRITE0: begin

                    word0 <= modified_word0;

                    if (cross_word) begin

                        mstate <= M_WRITE1;

                    end else begin

                        ack_o  <= 1'b1;
                        mstate <= M_IDLE;

                    end

                end

                // ---------------------------------------------
                // Second word write
                // =============================================

                M_WRITE1: begin

                    word1 <= modified_word1;

                    ack_o  <= 1'b1;
                    mstate <= M_IDLE;

                end

                default: begin
                    mstate <= M_IDLE;
                end

            endcase

        end

    end

endmodule
