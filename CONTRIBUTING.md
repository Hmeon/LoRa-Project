# Contributing

Thanks for helping improve LoRaLink-MLLC.

## Development setup
- Python: 3.10+
- Install (editable + dev tools): `python -m pip install -e .[dev]`
- Optional extras:
  - UART: `python -m pip install -e .[uart]`
  - BAM tools: `python -m pip install -e .[bam]`
  - Plotting: `python -m pip install -e .[viz]`

## Quality gates
- Lint: `ruff check .`
- Tests: `python -m pytest`

## Documentation expectations
- Treat `docs/01_design_doc_experiment_plan.md` as the source of truth for packet format, logs, and experiment phases.
- If behavior changes, update `docs/patch_notes.md` and any affected runbooks under `docs/`.

## Repo hygiene / security
- Do not commit real device addresses, credentials, or private datasets.
- Generated outputs belong under `out/` (ignored by git).
