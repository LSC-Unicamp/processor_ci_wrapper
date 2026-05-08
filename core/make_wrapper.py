import os
import re
import logging
from core import TEMPLATES_DIR
from core.defines import (
    CONTROLLER_SIGNALS_NON_OPEN,
    DATA_MEM_SIGNALS_NON_OPEN,
    TYPE_WORDS,
    OPERATORS,
    OUTPUT_SIGNALS,
)
from core.bus_defines import PROCESSOR_CI_WISHBONE_SIGNALS
from jinja2 import Environment, FileSystemLoader
from core.bus_defines import (
    ahb_adapter,
    ahb_data_adapter,
    axi4_adapter,
    axi4_data_adapter,
    axi4_lite_adapter,
    axi4_lite_data_adapter,
    ahb_adapter_vhd,
    ahb_data_adapter_vhd,
    axi4_lite_adapter_vhd,
    axi4_lite_data_adapter_vhd,
    axi4_adapter_vhd,
    axi4_data_adapter_vhd,
)

logger = logging.getLogger(__name__)


def is_identifier(tok):
    return bool(re.match(r'^[A-Za-z_]\w*$', tok))


def clean_token(tok):
    # remove leading/trailing whitespace
    tok = tok.strip()
    tok = tok.replace('(', '')
    tok = tok.replace(')', '')
    tok = tok.replace('[', '')
    tok = tok.replace(']', '')
    tok = tok.replace('{', '')
    tok = tok.replace('}', '')
    tok = tok.replace(';', '')
    return tok


def get_signals_to_create(expression: str):
    # split using operators as delimiters defineds in OPERATORS
    pattern = r'(' + '|'.join(re.escape(op) for op in OPERATORS) + r')'
    tokens = re.split(pattern, expression)

    tokens = [clean_token(tok) for tok in tokens]

    # remove whitespace and filter out empty tokens
    tokens = [tok.strip() for tok in tokens if is_identifier(tok)]
    return tokens


def create_signals_to_declare(signal_list, ports) -> str:
    """Gera declarações 'logic' para sinais com base em lista de sinais e portas (direction, name, width)."""
    # Mapeia nome da porta para largura
    port_widths = {p[1]: p[2] for p in ports}

    lines = []
    for signal in signal_list:
        width = port_widths.get(signal, 0)
        if width <= 1:
            lines.append(f'logic {signal};')
        else:
            lines.append(f'logic [{width-1}:0] {signal};')

    return '\n'.join(lines) + '\n'


def parse_parameters(params_block: str):
    """Extrai parâmetros de um bloco #( ... ) tolerando expressões complexas."""
    params = []
    if not params_block:
        return params

    # divide o bloco em "declarações de parâmetro" no nível superior
    param_entries = re.findall(
        r'parameter\s+[^,()]+(?:,[^,()]+)*', params_block, re.DOTALL
    )
    if not param_entries:  # fallback simples
        param_entries = params_block.split(',')

    for entry in param_entries:
        m = re.match(
            r'\s*parameter\s+([A-Za-z_]\w*)\s*=\s*(.+)', entry.strip()
        )
        if not m:
            continue
        name = m.group(1).strip()
        value = m.group(2).strip().rstrip(',')  # remove vírgulas de separação

        # balanceamento básico de {}
        if value.count('{') != value.count('}'):
            value = '0'
        elif '{' in value and '}' in value:
            # ainda pode ter concatenação complexa, protege
            if re.search(r'\{.*\{.*\}.*\}', value):  # nested braces
                value = '0'

        params.append((name, value))
    return params


def _split_top_level_commas(s: str):
    """Divide por vírgulas de nível superior (ignora vírgulas dentro de colchetes/parênteses/strings)."""
    parts, cur = [], []
    depth_paren = depth_brack = 0
    in_squote = in_dquote = esc = False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
            continue
        if ch == '\\':
            cur.append(ch)
            esc = True
            continue
        if ch == "'" and not in_dquote:
            in_squote = not in_squote
            cur.append(ch)
            continue
        if ch == '"' and not in_squote:
            in_dquote = not in_dquote
            cur.append(ch)
            continue
        if in_squote or in_dquote:
            cur.append(ch)
            continue
        if ch == '[':
            depth_brack += 1
            cur.append(ch)
            continue
        if ch == ']':
            depth_brack = max(0, depth_brack - 1)
            cur.append(ch)
            continue
        if ch == '(':
            depth_paren += 1
            cur.append(ch)
            continue
        if ch == ')':
            depth_paren = max(0, depth_paren - 1)
            cur.append(ch)
            continue
        if ch == ',' and depth_brack == 0 and depth_paren == 0:
            part = ''.join(cur).strip()
            if part:
                parts.append(part)
            cur = []
            continue
        cur.append(ch)
    last = ''.join(cur).strip()
    if last:
        parts.append(last)
    return parts


def generate_instance(
    code: str,
    mapping: dict,
    second_memory: bool = False,
    instance_name: str = 'u_instancia',
    use_adapter: bool = False,
):
    """
    Gera uma instância Verilog/SystemVerilog a partir de um `module` (com suporte a parâmetros).
    - mapping pode conter:
        * mapping[local_name] = module_port_name  (ex.: 'sys_clk':'clk')
        * mapping[module_port_name] = "<expr>"    (ex.: 'core_sel': "4'b1111")
      Valores None são ignorados.
    - Entradas sem match -> 1'b0
    - Entradas terminadas em _en ou _valid -> 1'b1
    - Debug/trace inputs -> 1'b0
    - Saídas/inout sem match -> ()
    """
    # localizar module <name> #( ... )? ( ... ) ;
    header_pat = re.compile(
        r'\bmodule\s+([A-Za-z_]\w*)'  # nome do módulo
        r'(?:\s+import\s+[^;]+;\s*)*'  # zero ou mais imports
        r'(?:\s*#\s*\((?P<params>.*?)\)\s*)?'  # bloco opcional de parâmetros #( ... )
        r'\s*\(\s*(?P<ports>.*?)\s*\)\s*;',  # bloco de portas ( ... );
        re.DOTALL,
    )
    m = header_pat.search(code)
    if not m:
        raise ValueError(
            'Unable to locate module header (module ... #( ... )? ( ... );).'
        )

    module_name = m.group(1)
    params_block = m.group('params') or ''
    ports_block = m.group('ports') or ''

    # -----------------------
    # parse parâmetros (parameter ...)
    # -----------------------
    params = parse_parameters(params_block)
    # params = []
    # if params_block:
    #     for pname, pval in re.findall(
    #         r'parameter\s+([A-Za-z_]\w*)\s*=\s*([^,)+]+)', params_block
    #     ):
    #         params.append((pname.strip(), pval.strip()))

    # -----------------------
    # parse portas
    # -----------------------
    chunks = _split_top_level_commas(ports_block)
    ports = []
    current_dir = None

    for chunk in chunks:
        s = chunk.strip()
        if not s:
            continue

        # Detecta direção
        dm = re.match(r'^(input|output|inout)\b(.*)$', s, re.IGNORECASE)
        if dm:
            current_dir = dm.group(1).lower()
            rest = dm.group(2).strip()
        else:
            if current_dir is None:
                continue
            rest = s

        # Captura range [msb:lsb] e nome da porta
        # Ex: logic [31:0] data_i, data_j
        # Regex captura opcional [msb:lsb] e identificador
        matches = re.findall(r'(\[[^\]]+\])?\s*([A-Za-z_]\w*)', rest)
        for range_str, name in matches:
            if name.lower() in TYPE_WORDS:
                continue
            # calcula largura
            if range_str:
                m = re.match(r'\[(\d+)\s*:\s*(\d+)\]', range_str)
                if m:
                    msb = int(m.group(1))
                    lsb = int(m.group(2))
                    width = abs(msb - lsb) + 1
                else:
                    width = 1
            else:
                width = 1
            ports.append((current_dir, name, width))

    # -----------------------
    # lógica de sinais não mapeados
    # -----------------------

    controller_signals_non_open = CONTROLLER_SIGNALS_NON_OPEN

    if second_memory:
        controller_signals_non_open.update(DATA_MEM_SIGNALS_NON_OPEN)

    assign_list = []
    create_list = []
    created_signals = set()

    controller_signals_non_open_keys = list(controller_signals_non_open.keys())
    mapping_keys = list(mapping.keys())

    if not use_adapter:
        for key in controller_signals_non_open_keys:
            if key not in mapping_keys:
                assign_list.append(
                    f'assign {key} = {controller_signals_non_open[key]};'
                )
            elif (
                mapping[key] is None
                or mapping[key] == ''
                or mapping[key] == 'null'
                or mapping[key] == 'None'
            ):
                assign_list.append(
                    f'assign {key} = {controller_signals_non_open[key]};'
                )
            # Sinal fruto de alucinação, não existe na lista de portas
            elif mapping[key] not in {name for _, name, _ in ports}:
                mapping[key] = None
                assign_list.append(
                    f'assign {key} = {controller_signals_non_open.get(key, 0)};'
                )

        if (
            'data_mem_cyc' in mapping_keys
            and 'data_mem_stb' in mapping_keys
            and second_memory
        ):
            if (
                mapping['data_mem_cyc'] == mapping['data_mem_stb']
                and mapping['data_mem_cyc'] is not None
                and mapping['data_mem_cyc'] != 'null'
                and isinstance(mapping['data_mem_cyc'], str)
                and is_identifier(mapping['data_mem_cyc'])
            ):
                assign_list.append('assign data_mem_cyc = 1;')

        if 'core_cyc' in mapping_keys and 'core_stb' in mapping_keys:
            if (
                mapping['core_cyc'] == mapping['core_stb']
                and mapping['core_cyc'] is not None
                and mapping['core_cyc'] != 'null'
                and isinstance(mapping['core_cyc'], str)
                and is_identifier(mapping['core_cyc'])
            ):
                assign_list.append('assign core_cyc = 1;')

        # caso a llm coloque os mesmos sinais para core e data_mem
        if (
            second_memory
            and 'core_cyc' in mapping_keys
            and 'core_stb' in mapping_keys
            and 'data_mem_cyc' in mapping_keys
            and 'data_mem_stb' in mapping_keys
        ):
            if (
                (
                    mapping['core_cyc'] == mapping['data_mem_cyc']
                    or mapping['core_stb'] == mapping['data_mem_stb']
                )
                and mapping['core_cyc'] is not None
                and mapping['core_cyc'] != 'null'
                and isinstance(mapping['core_cyc'], str)
                and is_identifier(mapping['core_cyc'])
                and mapping['core_stb'] is not None
                and mapping['core_stb'] != 'null'
                and isinstance(mapping['core_stb'], str)
                and is_identifier(mapping['core_stb'])
            ):
                assign_list.append('assign core_stb = 1;')

        # caso a llm coloque os mesmos sinais para core_we e data_we
        if 'core_we' in mapping_keys and 'data_mem_we' in mapping_keys:
            if (
                mapping['core_we'] == mapping['data_mem_we']
                and mapping['core_we'] is not None
                and mapping['core_we'] != 'null'
                and isinstance(mapping['core_we'], str)
                and is_identifier(mapping['core_we'])
            ):
                assign_list.append('assign core_we = 0;')

    # -----------------------
    # interpretar mapping
    # -----------------------
    reverse_map = {}
    const_map = {}

    for key, val in mapping.items():
        if val is None:
            continue
        if isinstance(val, str) and is_identifier(val):
            reverse_map[val] = key
        else:
            if isinstance(key, str) and is_identifier(key):
                const_map[key] = val
                signals_to_create = get_signals_to_create(val)
                signals_to_create = [
                    s for s in signals_to_create if s not in created_signals
                ]
                if signals_to_create:
                    decl = create_signals_to_declare(signals_to_create, ports)
                    created_signals.update(signals_to_create)
                    create_list.append(decl)

                if not key in OUTPUT_SIGNALS:
                    assign_list.append(f'assign {key} = {val};')
                else:
                    for s in signals_to_create:
                        assign_list.append(f'assign {s} = _{key};')

    # -----------------------
    # gerar instância (formatação alinhada)
    # -----------------------
    port_names = [p for (_, p, _) in ports]
    max_port_len = max((len(p) for p in port_names), default=0)
    max_param_len = max((len(p[0]) for p in params), default=0)

    lines = []
    # parâmetros
    if params:
        lines.append(f'{module_name} #(')
        for name, val in params:
            lines.append(f'    .{name:<{max_param_len}} ({val}),')
        lines[-1] = lines[-1].rstrip(',')
        lines.append(f') {instance_name} (')
    else:
        lines.append(f'{module_name} {instance_name} (')

    # portas
    for direction, port, width in ports:
        if direction == 'input' and (
            'clk' in port.lower() or 'clock' in port.lower()
        ):
            conn = 'clk_core'
        elif direction == 'input' and (
            'rst_n' in port.lower()
            or 'reset_n' in port.lower()
            or 'rstn' in port.lower()
            or 'resetn' in port.lower()
            or 'nrst' in port.lower()
            or 'nreset' in port.lower()
            or 'rstb' in port.lower()
            or 'resetb' in port.lower()
            or 'brst' in port.lower()
            or 'breset' in port.lower()
            or 'rst_b' in port.lower()
            or 'reset_b' in port.lower()
            or 'rstz' in port.lower()
            or 'resetz' in port.lower()
            or 'zrst' in port.lower()
            or 'zreset' in port.lower()
            or 'rst_z' in port.lower()
            or 'reset_z' in port.lower()
        ):
            conn = '~rst_core'
        elif direction == 'input' and (
            'rst' in port.lower() or 'reset' in port.lower()
        ):
            conn = 'rst_core'
        elif port in reverse_map:
            if (
                direction == 'input'
                and is_identifier(reverse_map[port])
                and reverse_map[port] not in PROCESSOR_CI_WISHBONE_SIGNALS
            ):
                conn = '0'
            elif port in created_signals:
                conn = port
                if direction == 'input':
                    if reverse_map[port] in OUTPUT_SIGNALS:
                        assign_list.append(
                            f'assign {port} = _{reverse_map[port]};'
                        )
                    else:
                        assign_list.append(
                            f'assign {port} = {reverse_map[port]};'
                        )
                else:
                    assign_list.append(f'assign {reverse_map[port]} = {port};')
            else:
                if reverse_map[port] in OUTPUT_SIGNALS:
                    conn = f'_{reverse_map[port]}'
                else:
                    conn = reverse_map[port]
        elif port in const_map:
            conn = const_map[port]
        elif port in created_signals:
            conn = port
        elif direction == 'input':
            pl = port.lower()
            if 'dbg_' in pl or 'trace_' in pl or 'trc_' in pl or 'jtag' in pl:
                conn = '0'
            elif (
                pl.endswith('_en')
                or pl.endswith('_valid')
                or 'poweron' in pl
                or 'start_' in pl
            ):
                conn = '1'
            else:
                conn = '0'
        else:
            conn = ''  # outputs/inout -> vazio

        if conn != '':
            lines.append(f'    .{port:<{max_port_len}} ({conn}),')
        else:
            lines.append(f'    .{port:<{max_port_len}} (),')

    if lines:
        lines[-1] = lines[-1].rstrip(',')
    lines.append(');')

    return '\n'.join(lines), '\n'.join(assign_list), '\n'.join(create_list)


def generate_instance_vhdl(
    code: str,
    mapping: dict,
    second_memory: bool = False,
    instance_name: str = 'u_processor',
    use_adapter: bool = False,
):
    """
    Generates a VHDL component instantiation from an entity declaration.
    
    Args:
        code: VHDL entity code (entity ... port (...) ...)
        mapping: Port mapping dictionary
        second_memory: Whether dual memory is enabled
        instance_name: Instance name for the component
        use_adapter: Whether bus adapters are used
    
    Returns:
        tuple: (instance_code, signal_assignments, signal_declarations)
    """
    # Locate entity ... port ( ... )
    entity_pat = re.compile(
        r'\bentity\s+([A-Za-z_]\w*)\s+is\b.*?'
        r'port\s*\(\s*(?P<ports>.*?)\s*\);',
        re.DOTALL | re.IGNORECASE,
    )
    m = entity_pat.search(code)
    if not m:
        raise ValueError(
            'Unable to locate VHDL entity declaration (entity ... port (...) ...)'
        )
    
    entity_name = m.group(1)
    ports_block = m.group('ports') or ''
    
    # Parse VHDL ports
    ports = []
    chunks = _split_top_level_commas(ports_block)
    current_dir = None
    
    for chunk in chunks:
        s = chunk.strip()
        if not s:
            continue
        
        # Match VHDL port syntax: name : direction type
        # Example: clk : in std_logic;
        # Example: data : out std_logic_vector(31 downto 0);
        port_match = re.match(
            r'^\s*([A-Za-z_]\w*)\s*:\s*(in|out|inout)\b\s+(.+)$',
            s,
            re.IGNORECASE,
        )
        if port_match:
            name = port_match.group(1)
            direction = port_match.group(2).lower()
            type_str = port_match.group(3).strip().rstrip(';')
            
            # Extract bit width from type string
            # std_logic => width 1
            # std_logic_vector(31 downto 0) => width 32
            width = 1
            if 'vector' in type_str.lower():
                vec_match = re.search(
                    r'\((\d+)\s+downto\s+(\d+)\)',
                    type_str,
                    re.IGNORECASE,
                )
                if vec_match:
                    msb = int(vec_match.group(1))
                    lsb = int(vec_match.group(2))
                    width = abs(msb - lsb) + 1
            
            ports.append((direction, name, width))
    
    # Apply same signal mapping logic as Verilog
    controller_signals_non_open = CONTROLLER_SIGNALS_NON_OPEN
    if second_memory:
        controller_signals_non_open.update(DATA_MEM_SIGNALS_NON_OPEN)
    
    assign_list = []
    create_list = []
    created_signals = set()
    
    # Generate port map
    port_names = [p[1] for p in ports]
    max_port_len = max((len(p) for p in port_names), default=0)
    
    lines = []
    lines.append(f'{instance_name} : {entity_name}')
    lines.append('  port map (')
    
    for i, (direction, port, width) in enumerate(ports):
        conn = ''
        is_last = i == len(ports) - 1
        
        # Clock detection
        if direction == 'in' and ('clk' in port.lower() or 'clock' in port.lower()):
            conn = 'clk_core'
        # Reset detection
        elif direction == 'in' and (
            'rst_n' in port.lower()
            or 'reset_n' in port.lower()
            or 'rstn' in port.lower()
            or 'resetn' in port.lower()
            or 'nrst' in port.lower()
            or 'nreset' in port.lower()
            or 'rstb' in port.lower()
            or 'resetb' in port.lower()
            or 'brst' in port.lower()
            or 'breset' in port.lower()
            or 'rst_b' in port.lower()
            or 'reset_b' in port.lower()
            or 'rstz' in port.lower()
            or 'resetz' in port.lower()
            or 'zrst' in port.lower()
            or 'zreset' in port.lower()
            or 'rst_z' in port.lower()
            or 'reset_z' in port.lower()
        ):
            conn = 'not rst_core'
        elif direction == 'in' and (
            'rst' in port.lower() or 'reset' in port.lower()
        ):
            conn = 'rst_core'
        elif port in mapping:
            if mapping[port] is None or mapping[port] == '' or mapping[port] == 'null':
                conn = ''
            else:
                conn = str(mapping[port])
        elif direction == 'in':
            pl = port.lower()
            if 'dbg_' in pl or 'trace_' in pl or 'trc_' in pl or 'jtag' in pl:
                conn = 'open'
            elif (
                pl.endswith('_en')
                or pl.endswith('_valid')
                or 'poweron' in pl
                or 'start_' in pl
            ):
                conn = "'1'"
            else:
                conn = "'0'"
        else:
            conn = ''
        
        if conn:
            comma = ',' if not is_last else ' '
            lines.append(f'    {port:<{max_port_len}} => {conn}{comma}')
        else:
            comma = ',' if not is_last else ' '
            lines.append(f'    {port:<{max_port_len}} => open{comma}')
    
    lines.append('  );')
    
    return '\n'.join(lines), '', ''


def generate_wrapper(
    cpu_name: str,
    instance_code: str,
    bus_type: str,
    second_memory: bool,
    output_dir='outputs',
    signal_mappings: str = '',
    create_signals: str = '',
    is_vhdl: bool = False,
):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    
    # Choose template based on HDL type
    template_name = 'wrapper_vhdl.j2' if is_vhdl else 'wrapper_sv.j2'
    template = env.get_template(template_name)

    logger.info(f'Bus type: {bus_type}, Second memory: {second_memory}, HDL: {"VHDL" if is_vhdl else "SystemVerilog"}')

    adapter = ''

    if is_vhdl:
        # Select VHDL adapters
        if bus_type == 'AHB':
            adapter = ahb_adapter_vhd
            if second_memory:
                adapter += '\n' + ahb_data_adapter_vhd
        elif bus_type == 'AXI':
            adapter = axi4_adapter_vhd
            if second_memory:
                adapter += '\n' + axi4_data_adapter_vhd
        elif bus_type == 'AXI-Lite':
            adapter = axi4_lite_adapter_vhd
            if second_memory:
                adapter += '\n' + axi4_lite_data_adapter_vhd
    else:
        # Select Verilog adapters
        if bus_type == 'AHB':
            adapter = ahb_adapter
            if second_memory:
                adapter += '\n' + ahb_data_adapter
        elif bus_type == 'AXI':
            adapter = axi4_adapter
            if second_memory:
                adapter += '\n' + axi4_data_adapter
        elif bus_type == 'AXI-Lite':
            adapter = axi4_lite_adapter
            if second_memory:
                adapter += '\n' + axi4_lite_data_adapter

    output = template.render(
        {
            'processor_instance': instance_code,
            'bus_type': bus_type,
            'second_memory': second_memory,
            'bus_adapter': adapter,
            'signal_mappings': signal_mappings,
            'create_signals': create_signals,
        }
    )

    os.makedirs(output_dir, exist_ok=True)

    # Choose output extension based on HDL type
    output_ext = 'vhd' if is_vhdl else 'sv'
    output_path = f'{output_dir}/{cpu_name}.{output_ext}'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
