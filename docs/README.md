# ProcessorCI Wrapper Documentation

## Responsibilities

ProcessorCI Wrapper owns wrapper generation and interface connection assistance.
It should not own processor discovery, execution testing, or trace comparison;
those responsibilities belong to other ProcessorCI repositories.

## Directory Boundaries

- `core/`: Python implementation.
- `templates/`: wrapper templates. Template changes can affect generated output
  for many processors, so keep them reviewed and documented.
- `internal/`: bus adapters, memory models, verification tops, and supporting
  files copied or referenced by generated wrappers.
- `main.py`: public CLI entrypoint.

## Input Contract

Wrapper generation assumes a ProcessorCI-style config with the processor name,
folder, file list, include directories, repository URL, top module, extra flags,
and language version.

When adding a new input field, document:

- Whether it is required.
- Which template or core module consumes it.
- How old configs behave without it.

## Validation Checklist

```bash
python main.py --help
```

For generated wrappers, manually review the output and run the relevant HDL
toolchain checks in the consuming repository.
