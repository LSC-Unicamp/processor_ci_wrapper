library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity ahb_to_wishbone is
  generic (
    ADDR_WIDTH : natural := 32;
    DATA_WIDTH : natural := 32
  );
  port (
    HCLK      : in  std_logic;
    HRESETn   : in  std_logic;

    -- AHB Interface
    HADDR     : in  std_logic_vector(ADDR_WIDTH-1 downto 0);
    HTRANS    : in  std_logic_vector(1 downto 0);
    HWRITE    : in  std_logic;
    HSIZE     : in  std_logic_vector(2 downto 0);
    HBURST    : in  std_logic_vector(2 downto 0);
    HPROT     : in  std_logic_vector(3 downto 0);
    HLOCK     : in  std_logic;
    HWDATA    : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    HREADY    : in  std_logic;
    HRDATA    : out std_logic_vector(DATA_WIDTH-1 downto 0);
    HREADYOUT : out std_logic;
    HRESP     : out std_logic_vector(1 downto 0);

    -- Wishbone Interface
    wb_cyc    : out std_logic;
    wb_stb    : out std_logic;
    wb_we     : out std_logic;
    wb_wstrb  : out std_logic_vector(3 downto 0);
    wb_adr    : out std_logic_vector(ADDR_WIDTH-1 downto 0);
    wb_dat_w  : out std_logic_vector(DATA_WIDTH-1 downto 0);
    wb_dat_r  : in  std_logic_vector(DATA_WIDTH-1 downto 0);
    wb_ack    : in  std_logic
  );
end entity ahb_to_wishbone;

architecture rtl of ahb_to_wishbone is

  -- Internal state
  signal ahb_active : std_logic;
  signal burst_cnt  : unsigned(2 downto 0);
  signal burst_en   : std_logic;
  signal base_addr  : std_logic_vector(ADDR_WIDTH-1 downto 0);
  signal beat_size  : std_logic_vector(2 downto 0);

  -- AHB access condition
  signal ahb_access : std_logic;
  signal ready      : std_logic;

  -- Burst type check
  signal is_burst : std_logic;

  -- Write strobe
  signal wstrb : std_logic_vector(3 downto 0);

  --------------------------------------------------------------------------
  -- Function: get_burst_len
  --------------------------------------------------------------------------
  function get_burst_len(
    burst : std_logic_vector(2 downto 0)
  ) return unsigned is
  begin
    case burst is
      when "000" => return to_unsigned(1, 3);   -- SINGLE
      when "001" => return to_unsigned(4, 3);   -- INCR4
      when "010" => return to_unsigned(8, 3);   -- INCR8
      when "011" => return to_unsigned(16, 3);  -- INCR16
      when others => return to_unsigned(1, 3);  -- INCR
    end case;
  end function;

  --------------------------------------------------------------------------
  -- Function: next_burst_addr
  --------------------------------------------------------------------------
  function next_burst_addr(
    addr : std_logic_vector(ADDR_WIDTH-1 downto 0);
    size : std_logic_vector(2 downto 0)
  ) return std_logic_vector is
    variable addr_u : unsigned(ADDR_WIDTH-1 downto 0);
  begin
    addr_u := unsigned(addr) + shift_left(to_unsigned(1, ADDR_WIDTH), to_integer(unsigned(size)));
    return std_logic_vector(addr_u);
  end function;

begin

  --------------------------------------------------------------------------
  -- Combinational assignments
  --------------------------------------------------------------------------
  ahb_access <= (HTRANS(1) or HWRITE) and HREADY;

  is_burst <= '1' when HBURST /= "000" else '0';

  HRESP <= "00"; -- OKAY

  HREADYOUT <= ((not ahb_active) or ready) and HRESETn;

  wb_dat_w <= HWDATA;

  --------------------------------------------------------------------------
  -- Main Sequential Logic
  --------------------------------------------------------------------------
  process(HCLK, HRESETn)
  begin
    if HRESETn = '0' then

      wb_cyc     <= '0';
      wb_stb     <= '0';
      wb_we      <= '0';
      wb_adr     <= (others => '0');

      ahb_active <= '0';
      burst_cnt  <= (others => '0');
      burst_en   <= '0';
      base_addr  <= (others => '0');
      beat_size  <= (others => '0');
      ready      <= '0';

      HRDATA     <= (others => '0');

    elsif rising_edge(HCLK) then

      -- Default deassertions
      ready  <= '0';
      wb_cyc <= '0';
      wb_stb <= '0';

      if (ahb_access = '1') and (ahb_active = '0') then

        -- Start transaction
        wb_adr <= std_logic_vector(unsigned(HADDR) and unsigned(not x"00000003"));
        wb_we  <= HWRITE;
        wb_wstrb <= wstrb;

        wb_cyc <= '1';
        wb_stb <= '1';

        ahb_active <= '1';

        -- Save base and setup burst
        base_addr <= HADDR;
        beat_size <= HSIZE;
        burst_cnt <= get_burst_len(HBURST);
        burst_en  <= is_burst;

      elsif (ahb_active = '1') and (wb_ack = '1') then

        -- Burst continuation
        if (burst_en = '1') and (burst_cnt > 1) then

          wb_cyc <= '1';
          wb_stb <= '1';
          wb_we  <= HWRITE;

          wb_adr <= next_burst_addr(wb_adr, beat_size);

          burst_cnt <= burst_cnt - 1;

          ahb_active <= '1';

        else

          ahb_active <= '0';
          burst_en   <= '0';
          ready      <= '1';

          HRDATA <= wb_dat_r;

        end if;
      end if;
    end if;
  end process;

  --------------------------------------------------------------------------
  -- Write Strobe Translation
  --------------------------------------------------------------------------
  process(all)
  begin
    wstrb <= "0000";

    case HSIZE is

      when "000" =>  -- 1 byte
        case HADDR(1 downto 0) is
          when "00" => wstrb <= "0001";
          when "01" => wstrb <= "0010";
          when "10" => wstrb <= "0100";
          when "11" => wstrb <= "1000";
          when others => wstrb <= "0000";
        end case;

      when "001" =>  -- 2 bytes
        case HADDR(1 downto 0) is
          when "00" => wstrb <= "0011";
          when "10" => wstrb <= "1100";
          when others => wstrb <= "0000";
        end case;

      when "010" =>  -- 4 bytes
        wstrb <= "1111";

      when others =>
        wstrb <= "0000";

    end case;
  end process;

end architecture rtl;