import os
import sys
import json
import colorlog
import logging
import argparse
from core.hdl_process import process_verilog, process_vhdl, simulate_to_check
from core.interface_resolve import (
    extract_interface_and_memory_ports,
    connect_interfaces,
)
from core.make_wrapper import generate_instance, generate_instance_vhdl, generate_wrapper
from core.order_files import _order_sv_files, _order_vhdl_files

DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'
PROCESSOR_CI_PATH = os.getenv('PROCESSOR_CI_PATH', '/eda/processor_ci')


def detect_hdl_type(files: list[str]) -> str:
    """
    Detect if the project is VHDL or Verilog based on file extensions.
    Returns 'vhdl' or 'verilog'.
    """
    has_vhdl = any(f.endswith(('.vhd', '.vhdl')) for f in files)
    has_verilog = any(f.endswith(('.sv', '.v', '.vh')) for f in files)
    
    # If both types present, VHDL takes precedence (as it's the conversion target)
    if has_vhdl:
        return 'vhdl'
    elif has_verilog:
        return 'verilog'
    else:
        return 'verilog'  # default


def build_wrapper(
    config: str,
    processor: str,
    context: int,
    model: str,
    processor_path: str,
    output: str,
    convert: bool,
    format: bool,
    override_hdl_type: bool = False
) -> None:
    logging.info('Reading processor configuration...')

    config_path = os.path.join(config, f'{processor}.json')
    config_data = {}
    with open(config_path, 'r', encoding='utf-8') as file:
        config_data = json.load(file)

    files = config_data.get('files') or config_data.get('sim_files') or []
    include_dirs = config_data.get('include_dirs', [])
    top_module = config_data.get('top_module', processor)
    extra_flags = config_data.get('extra_flags', [])

    # Detect HDL type early
    if override_hdl_type:
        is_vhdl = False
        logging.info('Override: Forcing SystemVerilog as HDL type.')
    else:
        is_vhdl = detect_hdl_type(files) == 'vhdl'
        logging.info(f'Detected HDL type: {"VHDL" if is_vhdl else "Verilog"}')

    logging.info('Processing HDL code...')

    if is_vhdl:
        header, other_files, include_flags, files = process_vhdl(
            processor,
            top_module,
            files,
            include_dirs,
            extra_flags,
            processor_path,
            context=context,
            get_files_in_project=True,
        )
    else:
        header, other_files, include_flags, files = process_verilog(
            processor,
            top_module,
            files,
            include_dirs,
            extra_flags,
            processor_path,
            context=context,
            convert_to_verilog2005=convert,
            format_code=format,
            get_files_in_project=True,
        )

    files = [os.path.relpath(f, start=processor_path) for f in files]
    config_files = config_data.get('files') or config_data.get('sim_files') or []
    files = set(files + config_files)
    # check if files are verilog or vhdl
    if any(f.endswith('.vhd') or f.endswith('.vhdl') for f in files):
        files = [f for f in files if f.endswith('.vhd') or f.endswith('.vhdl')]
        files = _order_vhdl_files(files, repo_root=processor_path)
    else:
        files = [f for f in files if f.endswith('.sv') or f.endswith('.v')]
        files = _order_sv_files(files, repo_root=processor_path)

    # Save processed files in config json with relative paths
    config_data['files'] = files
    with open(config_path, 'w', encoding='utf-8') as file:
        json.dump(config_data, file, indent=4)

    logging.debug(f'Extracted header:\n{header}')

    interface_and_ports = None

    logging.info('Extracting interfaces and memory ports...')

    ok = False
    tentativas = 0
    # Tenta 3 vezes obter um json valido
    while not ok and tentativas < 3:
        tentativas += 1
        logging.debug(f'Attempt {tentativas} of 3...')
        ok, interface_and_ports = extract_interface_and_memory_ports(
            header, model, is_vhdl=is_vhdl
        )

    if tentativas == 3 and not ok:
        logging.error('Error parsing JSON')
        sys.exit(1)

    logging.info(f'Detected interface: {interface_and_ports}')

    logging.info('Connecting interfaces...')

    tentativas = 0
    connections = None

    while connections is None and tentativas < 3:
        tentativas += 1
        logging.debug(f'Attempt {tentativas} of 3...')
        connections = connect_interfaces(interface_and_ports, header, model, is_vhdl=is_vhdl)

    if tentativas == 3 and connections is None:
        logging.error('Error parsing JSON')
        sys.exit(1)

    logging.debug(f'Interface connections: {connections}')

    second_memory = interface_and_ports.get('memory_interface', '') == 'Dual'
    use_adapter = interface_and_ports.get('bus_type', '') not in [
        'Wishbone',
        'Custom',
        'Avalon',
    ]

    logging.info('Generating instance...')

    if is_vhdl:
        instance, assign_list, create_signals, component_declarations, use_clauses = generate_instance_vhdl(
            header,
            connections,
            second_memory=second_memory,
            instance_name='u_processor',
            use_adapter=use_adapter,
        )
    else:
        instance, assign_list, create_signals = generate_instance(
            header,
            connections,
            second_memory=second_memory,
            instance_name='Processor',
            use_adapter=use_adapter,
        )

    logging.info('Generating wrapper...')

    generate_wrapper(
        processor,
        (instance, assign_list, create_signals, component_declarations, use_clauses) if is_vhdl else instance,
        interface_and_ports['bus_type'],
        second_memory,
        output,
        assign_list,
        create_signals,
        is_vhdl=is_vhdl,
    )

    logging.info('Starting simulation for verification...')

    simulate_to_check(
        processor,
        other_files,
        include_flags,
        output,
        second_memory=second_memory,
        is_vhdl=is_vhdl,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Processor CI Conector',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        '-c',
        '--config',
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help='Path to the configuration directory',
    )
    parser.add_argument(
        '-p',
        '--processor',
        type=str,
        help='Processor name (e.g., Grande-Risco-5)',
        required=True,
    )
    parser.add_argument(
        '-n',
        '--context',
        type=int,
        default=10,
        help='Number of context lines after the module definition',
    )
    parser.add_argument(
        '-m',
        '--model',
        type=str,
        default='qwen3:14b',
        help='LLM model to use',
    )
    parser.add_argument(
        '-P',
        '--processor-path',
        type=str,
        required=True,
        help='Path to the processor source code',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Display detailed logs',
    )
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default='outputs',
        help='Output directory',
    )
    parser.add_argument(
        '--convert-to-verilog2005',
        action='store_true',
        help='Convert source code to Verilog 2005 using sv2v',
    )
    parser.add_argument(
        '-f',
        '--format-code',
        action='store_true',
        help='Format code to a human-readable style using Verible',
    )
    parser.add_argument(
        '-sv',
        '--system_verilog',
        action='store_true',
        help='Overrides the VHDL detection and forces the use of SystemVerilog',
    )

    args = parser.parse_args()

    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s [%(name)s] %(levelname)s:%(reset)s %(message)s',
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red,bg_white',
        },
    )
    handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        handlers=[handler],
    )

    logging.debug('Detailed logging enabled.')

    build_wrapper(
        config=args.config,
        processor=args.processor,
        context=args.context,
        model=args.model,
        processor_path=args.processor_path,
        output=args.output,
        convert=args.convert_to_verilog2005,
        format=args.format_code,
        override_hdl_type=args.system_verilog
    )


if __name__ == '__main__':
    main()
