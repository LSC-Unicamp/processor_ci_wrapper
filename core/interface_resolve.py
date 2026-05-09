import re
import ast
import json
import logging
from core import send_prompt
from core.prompts import (
    wishbone_prompt_verilog,
    ahb_prompt_verilog,
    axi_prompt_verilog,
    wishbone_prompt_vhdl,
    ahb_prompt_vhdl,
    axi_prompt_vhdl,
    find_interface_prompt,
)

logger = logging.getLogger(__name__)


def filter_connections_from_response(response):
    def clean_json_block(block: str):
        """Remove comentários e vírgulas inválidas do bloco JSON."""
        # Remove comentários tipo // e /* ... */
        block = re.sub(r'//.*', '', block)
        block = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
        # Remove vírgulas sobrando antes de } ou ]
        block = re.sub(r',\s*([}\]])', r'\1', block)
        return block.strip()

    def extract_balanced_braces(text, start_index):
        """Extrai um bloco com chaves balanceadas a partir do primeiro '{'."""
        brace_count = 0
        for i, ch in enumerate(text[start_index:], start=start_index):
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    return text[start_index : i + 1]
        return None  # não encontrou fechamento

    # Encontrar início do JSON
    match = re.search(r'Connections\s*:\s*{', response)
    if match:
        start_index = response.find('{', match.start())
    else:
        start_index = response.find('{')
        if start_index == -1:
            logger.warning('Could not find JSON object in response.')
            return None

    # Extrair o bloco com chaves balanceadas
    block = extract_balanced_braces(response, start_index)
    if not block:
        logger.error('Unbalanced braces in response.')
        return None

    # Limpar conteúdo básico
    block = clean_json_block(block)

    # Proteger expressões HDL { ... } que não são objetos JSON
    def protect_hdl_expr(m):
        expr = m.group(0)
        # Se já está entre aspas (ex: "{2'b0, X}"), não tocar
        before = block[: m.start()]
        after = block[m.end() :]
        if before.endswith('"') and after.startswith('"'):
            return expr  # já protegido
        # Se não tem ':' (não é JSON), transformar em string
        if ':' not in expr:
            return f'"{expr}"'
        return expr

    block = re.sub(r'\{[^:{}]+\}', protect_hdl_expr, block)

    # Corrigir aspas duplicadas tipo ""foo""
    block = re.sub(r'""([^"]+)""', r'"\1"', block)

    # Fazer parse final
    try:
        connections = json.loads(block)
    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse Connections JSON: {e}\n{block}')
        return None

    # Confere se o json está plano. Não pode estar aninhado.
    if any(isinstance(v, (dict, list, tuple)) for v in connections.values()):
        logger.error('Wrong JSON format; Connections is nested.')
        return None

    return connections


def connect_interfaces(
    interface_info, processor_interface, model='qwen2.5:32b', is_vhdl=False
):
    # Select prompts based on HDL type
    if is_vhdl:
        wishbone_prompt = wishbone_prompt_vhdl
        ahb_prompt = ahb_prompt_vhdl
        axi_prompt = axi_prompt_vhdl
    else:
        wishbone_prompt = wishbone_prompt_verilog
        ahb_prompt = ahb_prompt_verilog
        axi_prompt = axi_prompt_verilog

    if interface_info['bus_type'] == 'Wishbone':
        prompt = wishbone_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    elif interface_info['bus_type'] == 'AHB':
        prompt = ahb_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    elif interface_info['bus_type'] == 'AXI':
        prompt = axi_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    else:
        logging.debug('Defaulting to Wishbone.')
        prompt = wishbone_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )

    logger.debug(f'Consulting model {model} for interface connections...')

    success, response = send_prompt(prompt, model=model)

    logger.debug(f'Ollama response for connection: \n{response}\n\n')

    if not success:
        logger.error('Error communicating with the server.')
        return None

    return filter_connections_from_response(response)


def filter_processor_interface_from_response(response: str) -> str:
    """
    It is expected a response with the following json format:
    {
        "bus_type": One of [AHB, AXI, Avalon, Wishbone, Custom],
        "memory_interface": Single or Dual,
    }
    This function extracts and returns only the JSON part of the response.
    """
    # --- 1. Find last {...} block ---
    start = response.rfind('{')
    end = response.rfind('}')
    if start == -1 or end == -1 or end < start:
        # raise ValueError('No JSON object found in response.')
        return False, {}
    candidate = response[start : end + 1]

    # --- 2. Small fixes for common LLM mistakes ---
    candidate = re.sub(
        r',\s*([}\]])', r'\1', candidate
    )  # remove trailing commas
    candidate = candidate.replace("'", '"')  # single → double quotes
    candidate = re.sub(
        r'([,{]\s*)(\w+)(\s*):', r'\1"\2"\3:', candidate
    )  # quote keys
    candidate = re.sub(
        r'//.*$', '', candidate, flags=re.MULTILINE
    )  # remove JavaScript-style comments

    # --- 3. Try parsing ---
    try:
        parsed = json.loads(candidate)
        logger.debug(f'Successfully parsed with json.loads: {parsed}')
    except json.JSONDecodeError:
        logger.debug(
            'Failed to parse JSON with json.loads, trying ast.literal_eval...'
        )
        try:
            # fallback: try Python dict style with ast.literal_eval
            parsed = ast.literal_eval(candidate)
            logger.debug(
                f'Successfully parsed with ast.literal_eval: {parsed}'
            )
        except (ValueError, SyntaxError):
            logger.debug(f'Failed to parse JSON from response: {candidate}')
            return False, {}

    # --- 4. Keep only expected keys ---
    allowed_keys = {'bus_type', 'memory_interface'}
    filtered = {k: parsed[k] for k in allowed_keys if k in parsed}

    return True, filtered


def extract_interface_and_memory_ports(core_declaration, model='qwen2.5:32b', is_vhdl=False):

    prompt = find_interface_prompt.format(core_declaration=core_declaration)

    logger.debug(
        f'Consulting model {model} to identify the processor interface...'
    )

    success, response = send_prompt(prompt, model=model)

    logger.debug(f'Ollama response for interface extraction: \n{response}\n\n')

    if not success:
        logger.error('Error communicating with the server.')
        return None

    ok, json_info = filter_processor_interface_from_response(response)
    return ok, json_info
