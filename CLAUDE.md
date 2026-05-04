# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**archi2likec4** converts coArchi XML (ArchiMate) repositories to LikeC4 `.c4` files.
Zero runtime dependencies — PyYAML and Flask are optional extras.

## Development Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Commands

```bash
# Run converter
archi2likec4                          # default: model in architectural_repository/model/, output in output/
archi2likec4 /path/to/model /path/to/output --config .archi2likec4.yaml
archi2likec4 --dry-run                # validate only, no file generation
python -m archi2likec4                # alternative entry point

# Test (1100+ tests, coverage gate 85%)
python -m pytest tests/ -v --tb=short
python -m pytest tests/test_builders_systems.py -v           # single file
python -m pytest tests/test_builders_systems.py::TestName -v # single class
python -m pytest tests/test_builders_systems.py::TestName::test_method -v  # single test

# Lint & type check
ruff check archi2likec4/ tests/
ruff check --fix archi2likec4/ tests/   # autofix
mypy archi2likec4/ --ignore-missing-imports
```

## Architecture

4-phase pipeline with NamedTuple data flow (no global state):

```
parse → build → validate → generate
```

| Phase    | Entry point       | Output         |
|----------|-------------------|----------------|
| parse    | `_parse()`        | `ParseResult`  |
| build    | `_build()`        | `BuildResult`  |
| validate | `_validate()`     | warnings/errors|
| generate | `_generate()`     | `.c4` files    |

All phases live in `pipeline.py`. `ParseResult` (pipeline.py) and `BuildResult` (builders/_result.py) are typed NamedTuples — data contracts between phases.

### Package layout

- `models.py` — dataclasses: `System`, `Integration`, `DeploymentNode`, etc.
- `config.py` — `ConvertConfig`, YAML loading
- `parsers.py` — coArchi XML → dataclasses
- `builders/` — system hierarchy, domains, integrations, deployment, data entities
- `generators/` — dataclasses → `.c4` content + `MATURITY.md`
- `maturity/` — GAP-based maturity auditor (10 detectors, penalty scoring)
- `web.py` / `web_routes.py` — optional Flask dashboard (`pip install "archi2likec4[web]"`)
- `i18n.py` — ru/en message catalog

### Element Hierarchy (5 levels)

1. **Domain** (L1) — from `functional_areas/{domain}/` folder
2. **Subdomain** (L2, optional) — from `functional_areas/{domain}/{subdomain}/`
3. **System** (L3) — ArchiMate ApplicationComponent
4. **Subsystem** (L4) — dot notation: `SystemName.SubsystemName`
5. **Function** (L5) — ArchiMate ApplicationFunction

## Coding Standards

- **Line length**: 120 characters (ruff). Max complexity: 15.
- **Logging**: always `logging.getLogger(__name__)` — never hardcode logger names.
- **Exceptions**: use domain exceptions from `archi2likec4.exceptions`:
  - Config issues → `ConfigError`
  - XML parse failures → `ParseError`
  - Validation gate failures → `ValidationError`
- **Typing**: `disallow_untyped_defs = true` for all modules except `web.py`, `web_routes.py`, `parsers.py`, `scripts/federate_template.py`.
- **IDs**: `make_id()` (utils.py) produces only `[a-z][a-z0-9_]*` — no hyphens (LikeC4 parses them as minus operator).

## Test Conventions

- Use `MockConfig` and `MockBuilt` from `tests/helpers.py` for unit tests.
- Integration tests (e2e) in `tests/test_pipeline_e2e.py` use real XML fixtures.
- Coverage gate: 85% (`pytest --cov-fail-under=85`).

## Behavioral Guidelines

### Think Before Coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.

### Simplicity First

- No features beyond what was asked. No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

### Surgical Changes

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken. Match existing style.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.
- Every changed line should trace directly to the user's request.

### Goal-Driven Execution

Transform tasks into verifiable goals:
- "Add validation" → write tests for invalid inputs, then make them pass
- "Fix the bug" → write a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

For multi-step tasks, state a brief plan with verification steps.
