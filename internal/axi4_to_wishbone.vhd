library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity axi4_to_wishbone_simple is
  generic (
    ADDR_WIDTH : natural := 32;
    DATA_WIDTH : natural := 32;
    ID_WIDTH   : natural := 4
  );
  port (
    clk   : in  std_logic;
    rst_n : in  std_logic;

    --------------------------------------------------------------------------
    -- AXI Write Address Channel
    --------------------------------------------------------------------------
    AXI_AWID    : in  std_logic_vector(ID_WIDTH-1 downto 0);
    AXI_AWADDR  : in  std_logic_vector(ADDR_WIDTH-1 downto 0);
    AXI_AWVALID : in  std_logic;
    AXI_AWREADY : out std_logic;

    --------------------------------------------------------------------------
    -- AXI Write Data Channel
    --------------------------------------------------------------------------
    AXI_WDATA   : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    AXI_WSTRB   : in  std_logic_vector((DATA_WIDTH/8)-1 downto 0);
    AXI_WVALID  : in  std_logic;
    AXI_WREADY  : out std_logic;

    --------------------------------------------------------------------------
    -- AXI Write Response Channel
    --------------------------------------------------------------------------
    AXI_BID     : out std_logic_vector(ID_WIDTH-1 downto 0);
    AXI_BRESP   : out std_logic_vector(1 downto 0);
    AXI_BVALID  : out std_logic;
    AXI_BREADY  : in  std_logic;

    --------------------------------------------------------------------------
    -- AXI Read Address Channel
    --------------------------------------------------------------------------
    AXI_ARID    : in  std_logic_vector(ID_WIDTH-1 downto 0);
    AXI_ARADDR  : in  std_logic_vector(ADDR_WIDTH-1 downto 0);
    AXI_ARVALID : in  std_logic;
    AXI_ARREADY : out std_logic;

    --------------------------------------------------------------------------
    -- AXI Read Data Channel
    --------------------------------------------------------------------------
    AXI_RID     : out std_logic_vector(ID_WIDTH-1 downto 0);
    AXI_RDATA   : out std_logic_vector(DATA_WIDTH-1 downto 0);
    AXI_RRESP   : out std_logic_vector(1 downto 0);
    AXI_RVALID  : out std_logic;
    AXI_RREADY  : in  std_logic;

    --------------------------------------------------------------------------
    -- Wishbone Interface
    --------------------------------------------------------------------------
    WB_CYC    : out std_logic;
    WB_STB    : out std_logic;
    WB_WE     : out std_logic;
    WB_ADDR   : out std_logic_vector(ADDR_WIDTH-1 downto 0);
    WB_WDATA  : out std_logic_vector(DATA_WIDTH-1 downto 0);
    WB_SEL    : out std_logic_vector((DATA_WIDTH/8)-1 downto 0);
    WB_RDATA  : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    WB_ACK    : in  std_logic
  );
end entity axi4_to_wishbone_simple;

architecture rtl of axi4_to_wishbone_simple is

  --------------------------------------------------------------------------
  -- FSM States
  --------------------------------------------------------------------------
  type state_t is (
    IDLE,
    WB_WRITE,
    WB_WRITE_RESP,
    WB_READ,
    WB_READ_RESP
  );

  signal state      : state_t;
  signal next_state : state_t;

  --------------------------------------------------------------------------
  -- Internal Registers
  --------------------------------------------------------------------------
  signal addr_reg  : std_logic_vector(ADDR_WIDTH-1 downto 0);
  signal wdata_reg : std_logic_vector(DATA_WIDTH-1 downto 0);
  signal wstrb_reg : std_logic_vector((DATA_WIDTH/8)-1 downto 0);
  signal id_reg    : std_logic_vector(ID_WIDTH-1 downto 0);

begin

  --------------------------------------------------------------------------
  -- FSM State Register
  --------------------------------------------------------------------------
  process(clk, rst_n)
  begin
    if rst_n = '0' then
      state <= IDLE;
    elsif rising_edge(clk) then
      state <= next_state;
    end if;
  end process;

  --------------------------------------------------------------------------
  -- FSM Combinational Logic
  --------------------------------------------------------------------------
  process(all)
  begin

    ------------------------------------------------------------------------
    -- Defaults
    ------------------------------------------------------------------------
    AXI_BVALID <= '0';
    AXI_BRESP  <= "00";
    AXI_BID    <= id_reg;

    AXI_RVALID <= '0';
    AXI_RRESP  <= "00";
    AXI_RDATA  <= WB_RDATA;
    AXI_RID    <= id_reg;

    WB_CYC   <= '0';
    WB_STB   <= '0';
    WB_WE    <= '0';
    WB_ADDR  <= addr_reg;
    WB_WDATA <= wdata_reg;
    WB_SEL   <= wstrb_reg;

    next_state <= state;

    ------------------------------------------------------------------------
    -- FSM
    ------------------------------------------------------------------------
    case state is

      ----------------------------------------------------------------------
      when IDLE =>
        if (AXI_AWVALID = '1') and (AXI_WVALID = '1') then
          next_state <= WB_WRITE;

        elsif AXI_ARVALID = '1' then
          next_state <= WB_READ;
        end if;

      ----------------------------------------------------------------------
      when WB_WRITE =>

        WB_CYC <= '1';
        WB_STB <= '1';
        WB_WE  <= '1';

        if WB_ACK = '1' then
          next_state <= WB_WRITE_RESP;
        end if;

      ----------------------------------------------------------------------
      when WB_WRITE_RESP =>

        AXI_BVALID <= '1';

        if AXI_BREADY = '1' then
          next_state <= IDLE;
        end if;

      ----------------------------------------------------------------------
      when WB_READ =>

        WB_CYC <= '1';
        WB_STB <= '1';

        if WB_ACK = '1' then
          next_state <= WB_READ_RESP;
        end if;

      ----------------------------------------------------------------------
      when WB_READ_RESP =>

        AXI_RVALID <= '1';

        if AXI_RREADY = '1' then
          next_state <= IDLE;
        end if;

    end case;
  end process;

  --------------------------------------------------------------------------
  -- Address/Data Capture Logic
  --------------------------------------------------------------------------
  process(clk, rst_n)
  begin

    if rst_n = '0' then

      AXI_ARREADY <= '0';
      AXI_AWREADY <= '0';
      AXI_WREADY  <= '0';

      addr_reg  <= (others => '0');
      wdata_reg <= (others => '0');
      wstrb_reg <= (others => '0');
      id_reg    <= (others => '0');

    elsif rising_edge(clk) then

      ----------------------------------------------------------------------
      -- Default deassertions
      ----------------------------------------------------------------------
      AXI_ARREADY <= '0';
      AXI_AWREADY <= '0';
      AXI_WREADY  <= '0';

      if state = IDLE then

        --------------------------------------------------------------------
        -- Write transaction capture
        --------------------------------------------------------------------
        if (AXI_AWVALID = '1') and (AXI_WVALID = '1') then

          addr_reg  <= AXI_AWADDR;
          wdata_reg <= AXI_WDATA;
          wstrb_reg <= AXI_WSTRB;
          id_reg    <= AXI_AWID;

          AXI_AWREADY <= '1';
          AXI_WREADY  <= '1';

        --------------------------------------------------------------------
        -- Read transaction capture
        --------------------------------------------------------------------
        elsif AXI_ARVALID = '1' then

          addr_reg <= AXI_ARADDR;
          id_reg   <= AXI_ARID;

          AXI_ARREADY <= '1';

        end if;
      end if;
    end if;
  end process;

end architecture rtl;