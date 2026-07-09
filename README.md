# ProcessorCI Wrapper

ProcessorCI Wrapper generates and assists with processor wrapper integration.
Given a processor repository and a ProcessorCI configuration, it can inspect HDL
source, order files, resolve interfaces, and produce wrapper code that connects
the processor to ProcessorCI verification and test infrastructure.

## Repository Layout

```text
core/             Wrapper generation and HDL processing helpers
internal/         ProcessorCI bus adapters, memory models, and test assets
templates/        Jinja templates for SystemVerilog and VHDL wrappers
main.py           CLI entrypoint
run-all.sh        Batch helper script
docs/             Layout and maintenance notes
requirements.txt  Python dependencies
```

## Installation

```bash
git clone https://github.com/LSC-Unicamp/processor_ci_wrapper.git
cd processor_ci_wrapper
python3 -m venv env
. env/bin/activate
pip install -r requirements.txt
```

External dependencies may include:

- Python 3.8 or newer.
- Verilator or other HDL tools for validation-oriented workflows.
- OLLAMA when model-assisted interface resolution is enabled.

## Inputs

The wrapper flow uses:

- Processor name.
- Path to the processor repository.
- ProcessorCI JSON configuration directory.
- Optional LLM model name.
- Optional `SERVER_URL` environment variable for a remote OLLAMA server.

By default, configs are searched under `/eda/processor_ci/config`. Override this
with `-c`.

## Quick Start

Show all options:

```bash
python main.py --help
```

Generate or assist a wrapper for a processor:

```bash
python main.py \
  -p <processor_name> \
  -P /path/to/processor/repository \
  -c /path/to/config/folder \
  -m <ollama_model>
```

Use a remote OLLAMA server:

```bash
export SERVER_URL="http://server:port"
python main.py -p <processor_name> -P /path/to/repo -m <ollama_model>
```

## Outputs

Outputs depend on the selected mode and processor language. The main generated
artifacts are wrapper files derived from:

- `templates/wrapper_sv.j2`
- `templates/wrapper_vhdl.j2`

The generated wrapper should connect the processor core to ProcessorCI memory,
clock, reset, and bus interfaces. Review generated code before using it in CI.

## Development

Keep `main.py` as the public CLI entrypoint. Implementation changes should live
under `core/`, and reusable HDL/template assets should stay under `internal/` or
`templates/`.

See [docs/README.md](docs/README.md) for more notes about data boundaries.

## Contributing

Issues and pull requests are welcome. Include a small processor/config example
when changing interface resolution or generated wrapper structure.

## License

This project is licensed under the [MIT License](LICENSE).
