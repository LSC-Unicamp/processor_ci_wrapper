library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;
use ieee.std_logic_textio.all;
use ieee.math_real.all;

entity Memory is
  generic (
    MEMORY_FILE : string  := "";
    MEMORY_SIZE : natural := 4096
  );
  port (
    clk    : in  std_logic;

    cyc_i  : in  std_logic;
    stb_i  : in  std_logic;
    we_i   : in  std_logic;

    addr_i : in  std_logic_vector(31 downto 0);
    data_i : in  std_logic_vector(31 downto 0);
    data_o : out std_logic_vector(31 downto 0);

    ack_o  : out std_logic
  );
end entity Memory;

architecture rtl of Memory is

  ----------------------------------------------------------------------------
  -- Utility function
  ----------------------------------------------------------------------------
  function clog2(n : natural) return natural is
    variable ret : natural := 0;
    variable val : natural := n - 1;
  begin
    while val > 0 loop
      ret := ret + 1;
      val := val / 2;
    end loop;
    return ret;
  end function;

  ----------------------------------------------------------------------------
  -- Memory configuration
  ----------------------------------------------------------------------------
  constant WORD_COUNT : natural := MEMORY_SIZE / 4;
  constant BIT_INDEX  : natural := clog2(MEMORY_SIZE) - 1;

  ----------------------------------------------------------------------------
  -- Memory type
  ----------------------------------------------------------------------------
  type memory_array_t is array (0 to WORD_COUNT-1)
    of std_logic_vector(31 downto 0);

  ----------------------------------------------------------------------------
  -- Memory initialization function (GHDL compatible)
  ----------------------------------------------------------------------------
  impure function init_memory return memory_array_t is
    file mem_file : text;
    variable line_v : line;
    variable tmp    : std_logic_vector(31 downto 0);
    variable mem    : memory_array_t := (others => (others => '0'));
    variable idx    : integer := 0;
  begin

    if MEMORY_FILE /= "" then

      file_open(mem_file, MEMORY_FILE, read_mode);

      while not endfile(mem_file) and idx < WORD_COUNT loop
        readline(mem_file, line_v);
        hread(line_v, tmp);
        mem(idx) := tmp;
        idx := idx + 1;
      end loop;

      file_close(mem_file);

    end if;

    return mem;
  end function;

  ----------------------------------------------------------------------------
  -- Memory storage
  ----------------------------------------------------------------------------
  signal memory : memory_array_t := init_memory;

begin

  ----------------------------------------------------------------------------
  -- Asynchronous Read
  ----------------------------------------------------------------------------
  data_o <= memory(
              to_integer(unsigned(addr_i(BIT_INDEX downto 2)))
            )
            when (cyc_i = '1' and stb_i = '1' and we_i = '0')
            else (others => '0');

  ----------------------------------------------------------------------------
  -- Asynchronous ACK
  ----------------------------------------------------------------------------
  ack_o <= cyc_i and stb_i;

  ----------------------------------------------------------------------------
  -- Synchronous Write
  ----------------------------------------------------------------------------
  process(clk)
  begin
    if rising_edge(clk) then

      if (cyc_i = '1') and
         (stb_i = '1') and
         (we_i  = '1') then

        memory(
          to_integer(unsigned(addr_i(BIT_INDEX downto 2)))
        ) <= data_i;

      end if;

    end if;
  end process;

end architecture rtl;