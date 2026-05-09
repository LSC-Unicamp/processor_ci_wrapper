library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity verification_top is
  port (
    clk      : in  std_logic;
    rst_n    : in  std_logic;

    cyc      : out std_logic;
    stb      : out std_logic;
    we       : out std_logic;
    addr     : out std_logic_vector(31 downto 0);
    data_out : out std_logic_vector(31 downto 0)
  );
end entity verification_top;

architecture rtl of verification_top is

  ----------------------------------------------------------------------------
  -- Core Wishbone Signals
  ----------------------------------------------------------------------------
  signal core_data_in  : std_logic_vector(31 downto 0);
  signal core_ack      : std_logic;

  signal core_cyc      : std_logic;
  signal core_stb      : std_logic;
  signal core_we       : std_logic;

  signal core_sel      : std_logic_vector(3 downto 0);
  signal core_addr     : std_logic_vector(31 downto 0);
  signal core_data_out : std_logic_vector(31 downto 0);

  ----------------------------------------------------------------------------
  -- Optional Second Memory Signals
  ----------------------------------------------------------------------------
{% if second_memory %}
  signal data_mem_cyc      : std_logic;
  signal data_mem_stb      : std_logic;
  signal data_mem_we       : std_logic;

  signal data_mem_sel      : std_logic_vector(3 downto 0);

  signal data_mem_addr     : std_logic_vector(31 downto 0);
  signal data_mem_data_out : std_logic_vector(31 downto 0);

  signal data_mem_data_in  : std_logic_vector(31 downto 0);
  signal data_mem_ack      : std_logic;
{% endif %}

begin

  ----------------------------------------------------------------------------
  -- Output Mapping
  ----------------------------------------------------------------------------
{% if second_memory %}
  cyc      <= data_mem_cyc;
  stb      <= data_mem_stb;
  we       <= data_mem_we;
  addr     <= data_mem_addr;
  data_out <= data_mem_data_out;
{% else %}
  cyc      <= core_cyc;
  stb      <= core_stb;
  we       <= core_we;
  addr     <= core_addr;
  data_out <= core_data_out;
{% endif %}

  ----------------------------------------------------------------------------
  -- Processor Top Instance
  ----------------------------------------------------------------------------
  ptop : entity work.processorci_top
    port map (
      sys_clk       => clk,
      rst_n         => rst_n,

      core_cyc      => core_cyc,
      core_stb      => core_stb,
      core_we       => core_we,

      core_addr     => core_addr,
      core_data_out => core_data_out,
      core_data_in  => core_data_in,
      core_ack      => core_ack

{% if second_memory %}
      ,
      data_mem_cyc      => data_mem_cyc,
      data_mem_stb      => data_mem_stb,
      data_mem_we       => data_mem_we,

      data_mem_addr     => data_mem_addr,
      data_mem_data_out => data_mem_data_out,
      data_mem_data_in  => data_mem_data_in,
      data_mem_ack      => data_mem_ack
{% endif %}
    );

  ----------------------------------------------------------------------------
  -- First Memory Instance
  ----------------------------------------------------------------------------
  MainMemory : entity work.Memory
    generic map (
      MEMORY_FILE => "/eda/processor_ci_connector/internal/memory.hex",
      MEMORY_SIZE => 4096
    )
    port map (
      clk    => clk,

      cyc_i  => core_cyc,
      stb_i  => core_stb,
      we_i   => core_we,

      addr_i => core_addr,
      data_i => core_data_out,
      data_o => core_data_in,

      ack_o  => core_ack
    );

{% if second_memory %}
  ----------------------------------------------------------------------------
  -- Second Memory Instance
  ----------------------------------------------------------------------------
  SecondMemory : entity work.Memory
    generic map (
      MEMORY_FILE => "",
      MEMORY_SIZE => 4096
    )
    port map (
      clk    => clk,

      cyc_i  => data_mem_cyc,
      stb_i  => data_mem_stb,
      we_i   => data_mem_we,

      addr_i => data_mem_addr,
      data_i => data_mem_data_out,
      data_o => data_mem_data_in,

      ack_o  => data_mem_ack
    );
{% endif %}

end architecture rtl;