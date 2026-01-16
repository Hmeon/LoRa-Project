# Repository Guidelines

## Project Structure & Module Organization
- `loralink_mllc/` is the runtime package (codecs, protocol framing, radio interfaces, scheduler, TX/RX nodes, experiments).
- `docs/` holds design references, protocol/PHY notes, and paper dissections; `docs/assets/` is for diagrams and plots.
- `configs/examples/` contains minimal JSON templates for mock runs and runtime placeholders.
- `tests/` contains pytest-based unit and smoke tests.
- `scripts/` and `src/` exist but are currently empty placeholders.

## Build, Test, and Development Commands
- `python -m pip install -e .[dev]` installs the package in editable mode with dev tools.
- `python -m loralink_mllc.cli --help` shows CLI entry points.
- `python -m loralink_mllc.cli phase0 --sweep configs/examples/sweep.json --out out/c50.json` runs a mock C50 sweep.
- `python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/examples/raw.json --latent configs/examples/latent.json --out out/report.json` runs a mock A/B report.
- `python -m pytest` runs the test suite.
- `ruff check .` runs linting (configured in `pyproject.toml`).

## Coding Style & Naming Conventions
- Python 3.11, 4-space indentation, max line length 100 (ruff).
- Use type hints and keep dataclasses for structured config data.
- Naming: `snake_case` for functions/variables, `CamelCase` for classes, `UPPER_SNAKE` for constants.
- Keep JSON keys consistent with RunSpec fields (e.g., `run_id`, `ack_timeout_ms`, `payload_schema_hash`).

## Testing Guidelines
- Framework: pytest. Tests live in `tests/` and are named `test_*.py`.
- Add unit tests for protocol framing, codecs, and scheduler logic.
- If tests are not run, note that explicitly in the PR.

## Commit & Pull Request Guidelines
- Git history does not show a formal convention; use concise, imperative summaries (e.g., “add mock sweep examples”).
- PRs should include: purpose, linked issue (if any), commands run (or “not run”), and doc updates when behavior changes.

## Security & Configuration Tips
- `configs/examples/` are templates; do not commit real device addresses, credentials, or private datasets.
- Generated logs land under `out/`; avoid committing large or sensitive logs unless needed for documentation.
