library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity AXI4Lite_to_Wishbone is
  generic (
    ADDR_WIDTH : natural := 32;
    DATA_WIDTH : natural := 32
  );
  port (
    ACLK     : in  std_logic;
    ARESETN  : in  std_logic;

    --------------------------------------------------------------------------
    -- AXI4-Lite Slave Interface
    --------------------------------------------------------------------------
    AWADDR   : in  std_logic_vector(ADDR_WIDTH-1 downto 0);
    AWPROT   : in  std_logic_vector(2 downto 0);
    AWVALID  : in  std_logic;
    AWREADY  : out std_logic;

    WDATA    : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    WSTRB    : in  std_logic_vector((DATA_WIDTH/8)-1 downto 0);
    WVALID   : in  std_logic;
    WREADY   : out std_logic;

    BRESP    : out std_logic_vector(1 downto 0);
    BVALID   : out std_logic;
    BREADY   : in  std_logic;

    ARADDR   : in  std_logic_vector(ADDR_WIDTH-1 downto 0);
    ARPROT   : in  std_logic_vector(2 downto 0);
    ARVALID  : in  std_logic;
    ARREADY  : out std_logic;

    RDATA    : out std_logic_vector(DATA_WIDTH-1 downto 0);
    RRESP    : out std_logic_vector(1 downto 0);
    RVALID   : out std_logic;
    RREADY   : in  std_logic;

    --------------------------------------------------------------------------
    -- Wishbone Master Interface
    --------------------------------------------------------------------------
    wb_adr_o : out std_logic_vector(ADDR_WIDTH-1 downto 0);
    wb_dat_o : out std_logic_vector(DATA_WIDTH-1 downto 0);
    wb_we_o  : out std_logic;
    wb_stb_o : out std_logic;
    wb_cyc_o : out std_logic;
    wb_sel_o : out std_logic_vector((DATA_WIDTH/8)-1 downto 0);

    wb_dat_i : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    wb_ack_i : in  std_logic;
    wb_err_i : in  std_logic
  );
end entity AXI4Lite_to_Wishbone;

architecture rtl of AXI4Lite_to_Wishbone is

  --------------------------------------------------------------------------
  -- State Machine
  --------------------------------------------------------------------------
  type state_t is (
    IDLE,
    WRITE,
    READ
  );

  signal state : state_t;

begin

  --------------------------------------------------------------------------
  -- Main Sequential Process
  --------------------------------------------------------------------------
  process(ACLK, ARESETN)
  begin

    if ARESETN = '0' then

      state <= IDLE;

      AWREADY  <= '0';
      WREADY   <= '0';
      BVALID   <= '0';

      ARREADY  <= '0';
      RVALID   <= '0';

      BRESP    <= (others => '0');
      RRESP    <= (others => '0');

      RDATA    <= (others => '0');

      wb_adr_o <= (others => '0');
      wb_dat_o <= (others => '0');
      wb_sel_o <= (others => '0');

      wb_cyc_o <= '0';
      wb_stb_o <= '0';
      wb_we_o  <= '0';

    elsif rising_edge(ACLK) then

      case state is

        --------------------------------------------------------------------
        -- IDLE STATE
        --------------------------------------------------------------------
        when IDLE =>

          AWREADY <= '1';
          ARREADY <= '1';

          WREADY  <= '0';

          BVALID  <= '0';
          RVALID  <= '0';

          ------------------------------------------------------------------
          -- WRITE TRANSACTION
          ------------------------------------------------------------------
          if (AWVALID = '1') and (AWREADY = '1') then

            wb_adr_o <= AWADDR;
            wb_we_o  <= '1';

            wb_dat_o <= WDATA;
            wb_sel_o <= WSTRB;

            wb_cyc_o <= '1';
            wb_stb_o <= '1';

            AWREADY <= '0';
            WREADY  <= '1';

            state <= WRITE;

          ------------------------------------------------------------------
          -- READ TRANSACTION
          ------------------------------------------------------------------
          elsif (ARVALID = '1') and (ARREADY = '1') then

            wb_adr_o <= ARADDR;

            wb_we_o  <= '0';

            wb_cyc_o <= '1';
            wb_stb_o <= '1';

            ARREADY <= '0';

            state <= READ;

          end if;

        --------------------------------------------------------------------
        -- WRITE STATE
        --------------------------------------------------------------------
        when WRITE =>

          if (WVALID = '1') and (WREADY = '1') then
            WREADY <= '0';
          end if;

          if wb_ack_i = '1' then

            wb_cyc_o <= '0';
            wb_stb_o <= '0';

            BVALID <= '1';

            if wb_err_i = '1' then
              BRESP <= "10"; -- SLVERR
            else
              BRESP <= "00"; -- OKAY
            end if;

            state <= IDLE;

          end if;

        --------------------------------------------------------------------
        -- READ STATE
        --------------------------------------------------------------------
        when READ =>

          if wb_ack_i = '1' then

            wb_cyc_o <= '0';
            wb_stb_o <= '0';

            RDATA <= wb_dat_i;

            if wb_err_i = '1' then
              RRESP <= "10"; -- SLVERR
            else
              RRESP <= "00"; -- OKAY
            end if;

            RVALID <= '1';

            state <= IDLE;

          end if;

        --------------------------------------------------------------------
        -- DEFAULT
        --------------------------------------------------------------------
        when others =>

          state <= IDLE;

      end case;
    end if;
  end process;

end architecture rtl;