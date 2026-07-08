# ProcessorCI Wrapper

Welcome to the **ProcessorCI Wrapper**.

The **Processor CI Wrapper** is a tool for processor connection and integration.
Given a RISC-V processor, it can pre-process its source code, extract its instance, and establish a connection with the **Processor CI Wrapper**, automating part of the continuous integration flow.

---

## Dependencies

For proper operation of the ProcessorCI Wrapper, the following dependencies are required:

* Verilator
* Python 3.8 or newer
* Pip
* Python Venv
* Ollama API

---

## Installation

To install the project dependencies, run:

```bash
pip install -r requirements.txt
```

---

## Usage

The **ProcessorCI Wrapper** is a command-line tool with an integrated parser.
All available options can be displayed with the following command:

```bash
python main.py --help
```

### Typical usage example

A standard execution is performed using:

```bash
python main.py -p <Processor Name> -P <Path to processor repository> -m <LLM Model>
```

---

## Ollama Server Configuration

If a local **Ollama** server is not available, you can configure the remote server address by exporting the `SERVER_URL` environment variable:

```bash
export SERVER_URL="<your server url and port>"
```

---

## ProcessorCI Configuration File

The **ProcessorCI Wrapper** requires a valid **Processor CI** JSON configuration file to operate correctly.
By default, the connector searches for this file in the directory:

```
/eda/processor_ci/config
```

This path can be modified using the `-c` flag:

```bash
python main.py -c <Path to config folder>
```

---

## Documentation and Support

The official documentation is available at:
[https://processorci.lsc.ic.unicamp.br](https://processorci.lsc.ic.unicamp.br)

Questions, suggestions, and issue reports can be submitted in the **Issues** section of the GitHub repository.
Contributions are welcome, and all Pull Requests will be reviewed and merged whenever possible.

---

## Contributing

To contribute improvements or fixes, please refer to the contribution guidelines available in:
[CONTRIBUTING.md](./CONTRIBUTING.md)

---

## License

This project is licensed under the [MIT License](./LICENSE), granting full freedom for use, modification, and distribution.

