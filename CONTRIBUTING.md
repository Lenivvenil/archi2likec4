# Contributing to archi2likec4

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd archi2likec4

# Create virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# For federation script development:
pip install -e ".[federation]"
```

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Running the Converter

```bash
# With defaults (model in architectural_repository/model, output in output/)
python3 convert.py

# With custom paths
python3 convert.py /path/to/model /path/to/output

# With config file
python3 convert.py --config .archi2likec4.yaml

# Dry run (validate only, no file generation)
python3 convert.py --dry-run
```

## Configuration

Copy `.archi2likec4.example.yaml` to `.archi2likec4.yaml` and customize.
See the example file for all available options.

## Code Structure

- `archi2likec4/models.py` — dataclasses and default constants
- `archi2likec4/config.py` — configuration loading (YAML + CLI)
- `archi2likec4/parsers.py` — coArchi XML parsing
- `archi2likec4/builders.py` — system hierarchy and domain assignment
- `archi2likec4/generators.py` — LikeC4 .c4 file generation
- `archi2likec4/federation.py` — federation script generation
- `archi2likec4/pipeline.py` — main orchestration

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass: `python3 -m pytest tests/ -v`
4. Run the converter to verify output: `python3 convert.py`
5. Submit a merge request with a clear description
