library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity verification_tb is
end entity verification_tb;

architecture rtl of verification_tb is

  signal clk      : std_logic := '0';
  signal rst_n    : std_logic := '0';

  signal cyc      : std_logic;
  signal stb      : std_logic;
  signal we       : std_logic;
  signal addr     : std_logic_vector(31 downto 0);
  signal data_out : std_logic_vector(31 downto 0);

  constant EXPECTED_ADDR : std_logic_vector(31 downto 0) := x"0000003C";
  constant EXPECTED_DATA : std_logic_vector(31 downto 0) := x"00000005";

begin

  dut : entity work.verification_top
    port map (
      clk      => clk,
      rst_n    => rst_n,
      cyc      => cyc,
      stb      => stb,
      we       => we,
      addr     => addr,
      data_out => data_out
    );

  clk_process : process
  begin
    while true loop
      clk <= '0';
      wait for 5 ns;
      clk <= '1';
      wait for 5 ns;
    end loop;
  end process;

  reset_process : process
  begin
    rst_n <= '0';
    wait for 20 ns;
    rst_n <= '1';
    wait;
  end process;

  monitor_process : process
    variable cycle_count : natural := 0;
  begin
    wait until rising_edge(clk);
    cycle_count := cycle_count + 1;

    if rst_n = '1' then
      if cyc = '1'
        and stb = '1'
        and we = '1'
        and addr = EXPECTED_ADDR
        and data_out = EXPECTED_DATA
      then
        report "Expected output reached at cycle " & integer'image(cycle_count)
          severity note;
        stop;
      end if;
    end if;

    if cycle_count > 2000 then
      assert false
        report "Timeout waiting for expected output"
        severity failure;
    end if;
  end process;

end architecture rtl;