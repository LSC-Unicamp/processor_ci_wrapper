module axi4_to_wishbone_simple #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32,
    parameter ID_WIDTH   = 4
)(
    input  logic clk,
    input  logic rst_n,

    // AXI Write Address Channel
    input  logic [ID_WIDTH-1:0]    AXI_AWID,
    input  logic [ADDR_WIDTH-1:0]  AXI_AWADDR,
    input  logic                   AXI_AWVALID,
    output logic                   AXI_AWREADY,

    // AXI Write Data Channel
    input  logic [DATA_WIDTH-1:0]  AXI_WDATA,
    input  logic [(DATA_WIDTH/8)-1:0] AXI_WSTRB,
    input  logic                   AXI_WVALID,
    output logic                   AXI_WREADY,

    // AXI Write Response Channel
    output logic [ID_WIDTH-1:0]    AXI_BID,
    output logic [1:0]             AXI_BRESP,
    output logic                   AXI_BVALID,
    input  logic                   AXI_BREADY,

    // AXI Read Address Channel
    input  logic [ID_WIDTH-1:0]    AXI_ARID,
    input  logic [ADDR_WIDTH-1:0]  AXI_ARADDR,
    input  logic                   AXI_ARVALID,
    output logic                   AXI_ARREADY,

    // AXI Read Data Channel
    output logic [ID_WIDTH-1:0]    AXI_RID,
    output logic [DATA_WIDTH-1:0]  AXI_RDATA,
    output logic [1:0]             AXI_RRESP,
    output logic                   AXI_RVALID,
    input  logic                   AXI_RREADY,

    // Wishbone Interface
    output logic                   WB_CYC,
    output logic                   WB_STB,
    output logic                   WB_WE,
    output logic [ADDR_WIDTH-1:0]  WB_ADDR,
    output logic [DATA_WIDTH-1:0]  WB_WDATA,
    output logic [(DATA_WIDTH/8)-1:0] WB_SEL,
    input  logic [DATA_WIDTH-1:0]  WB_RDATA,
    input  logic                   WB_ACK
);

    // Estados
    typedef enum logic [2:0] {
        IDLE,
        WB_WRITE,
        WB_WRITE_RESP,
        WB_READ,
        WB_READ_RESP
    } state_t;

    state_t state, next_state;

    // Registradores internos
    logic [ADDR_WIDTH-1:0] addr_reg;
    logic [DATA_WIDTH-1:0] wdata_reg;
    logic [DATA_WIDTH-1:0] rdata_reg;
    logic [(DATA_WIDTH/8)-1:0] wstrb_reg;
    logic [ID_WIDTH-1:0] id_reg;
    logic is_write;

    // FSM principal
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end

    always_comb begin
        // Defaults
        AXI_BVALID  = 0;
        AXI_BRESP   = 2'b00;
        AXI_BID     = id_reg;

        AXI_RVALID  = 0;
        AXI_RRESP   = 2'b00;
        AXI_RDATA   = (state == WB_READ_RESP) ? rdata_reg : WB_RDATA;
        AXI_RID     = id_reg;

        WB_CYC  = 0;
        WB_STB  = 0;
        WB_WE   = 0;
        WB_ADDR = addr_reg;
        WB_WDATA = wdata_reg;
        WB_SEL = wstrb_reg;

        next_state = state;

        case (state)
            IDLE: begin
                if (AXI_AWVALID && AXI_WVALID) begin
                    next_state = WB_WRITE;
                end else if (AXI_ARVALID) begin
                    next_state = WB_READ;
                end
            end

            WB_WRITE: begin
                WB_CYC = 1;
                WB_STB = 1;
                WB_WE  = 1;
                if (WB_ACK) begin
                    next_state = WB_WRITE_RESP;
                end
            end

            WB_WRITE_RESP: begin
                AXI_BVALID = 1;
                if (AXI_BREADY) begin
                    next_state = IDLE;
                end
            end

            WB_READ: begin
                WB_CYC = 1;
                WB_STB = 1;
                if (WB_ACK) begin
                    next_state = WB_READ_RESP;
                end
            end

            WB_READ_RESP: begin
                AXI_RVALID = 1;
                if (AXI_RREADY) begin
                    next_state = IDLE;
                end
            end
        endcase
    end

    // Captura de endereço/dados
    always_ff @(posedge clk or negedge rst_n) begin
        AXI_ARREADY <= 0;
        AXI_AWREADY <= 0;
        AXI_WREADY  <= 0;
        
        if (!rst_n) begin
            addr_reg <= 0;
            wdata_reg <= 0;
            rdata_reg <= 0;
            wstrb_reg <= 0;
            id_reg <= 0;
        end else begin
            if (state == WB_READ && WB_ACK) begin
                rdata_reg <= WB_RDATA;
            end
            if (state == IDLE) begin
                if (AXI_AWVALID && AXI_WVALID) begin
                    addr_reg  <= AXI_AWADDR;
                    wdata_reg <= AXI_WDATA;
                    wstrb_reg <= AXI_WSTRB;
                    id_reg    <= AXI_AWID;
                    AXI_AWREADY <= 1;
                    AXI_WREADY  <= 1;
                end else if (AXI_ARVALID) begin
                    addr_reg  <= AXI_ARADDR;
                    id_reg    <= AXI_ARID;
                    AXI_ARREADY <= 1;
                end
            end
        end
    end

endmodule
