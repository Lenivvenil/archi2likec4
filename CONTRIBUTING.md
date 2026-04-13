# Contributing to archi2likec4

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd archi2likec4

# Create virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode (includes pytest, flask, pyyaml)
pip install -e ".[dev]"

# For federation script development:
pip install -e ".[federation]"
```

## Running Tests

```bash
# Run tests
python3 -m pytest tests/ -v

# Lint (matches CI)
ruff check archi2likec4/ tests/

# Type check (matches CI)
mypy archi2likec4/ --ignore-missing-imports
```

## Running the Converter

```bash
# With defaults (model in architectural_repository/model, output in output/)
archi2likec4

# With custom paths
archi2likec4 /path/to/model /path/to/output

# With config file
archi2likec4 --config .archi2likec4.yaml

# Dry run (validate only, no file generation)
archi2likec4 --dry-run

# Alternative: via python module
python3 -m archi2likec4
```

## Configuration

Copy `.archi2likec4.example.yaml` to `.archi2likec4.yaml` and customize.
See the example file for all available options.

## Code Structure

- `archi2likec4/models.py` — dataclasses and default constants
- `archi2likec4/config.py` — configuration loading (YAML + CLI)
- `archi2likec4/parsers.py` — coArchi XML parsing
- `archi2likec4/builders/` — system hierarchy and domain assignment (package)
- `archi2likec4/generators/` — LikeC4 .c4 file generation (package)
- `archi2likec4/templates/` — Jinja2 HTML templates for the Flask web UI
- `archi2likec4/maturity/` — GAP-based maturity auditor (detectors, scoring, reporters)
- `archi2likec4/i18n.py` — ru/en message catalog
- `archi2likec4/scripts/federate_template.py` — federation script generation
- `archi2likec4/web.py` — Flask UI (dashboard, remediations, hierarchy)
- `archi2likec4/pipeline.py` — main orchestration

## Diagnostic Tools

Diagnostic scripts live in `tools/` and are not part of the installed package:

- `tools/stats.py` — deep model statistics (systems, integrations, domains)
- `tools/diag_targets.py` — lost integration targets and self-loop analysis
- `tools/diag_dupes.py` — duplicate integration diagnostics
- `tools/diag_views.py` — solution view element resolution
- `tools/diag_orphan_subsystems.py` — orphaned subsystem detection
- `tools/analyze_views.py` — LikeC4 exported JSON view analysis

Run from the project root: `python3 tools/stats.py`

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all checks pass: `pytest tests/ -v && ruff check archi2likec4/ tests/ && mypy archi2likec4/ --ignore-missing-imports`
4. Run the converter to verify output: `archi2likec4`
5. Submit a pull request with a clear description
