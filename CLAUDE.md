# CLAUDE.md — Developer Guide for archi2likec4

## Overview

**archi2likec4** converts coArchi XML (ArchiMate) repositories to LikeC4 `.c4` files.
Zero runtime dependencies — PyYAML and Flask are optional extras.

## Architecture

4-phase pipeline with NamedTuple data flow:

```
parse  →  build  →  validate  →  generate
```

| Phase    | Entry point       | Output         |
|----------|-------------------|----------------|
| parse    | `_parse()`        | `ParseResult`  |
| build    | `_build()`        | `BuildResult`  |
| validate | `_validate()`     | warnings/errors|
| generate | `_generate()`     | `.c4` files    |

## Key Files

| Path | Purpose |
|------|---------|
| `archi2likec4/pipeline.py` | Orchestration — `convert()`, `ConvertResult`, `main()`, `ParseResult`, `SolutionViewInfo`, `_parse/build/validate/generate` |
| `archi2likec4/config.py` | YAML config loading — `ConvertConfig`, `load_config()` |
| `archi2likec4/models.py` | Dataclasses — `AppComponent`, `System`, `Integration`, etc. |
| `archi2likec4/parsers.py` | XML parsing — `parse_systems()`, `parse_subdomains()`, `parse_integrations()`, `parse_deployment()`, etc. |
| `archi2likec4/builders/systems.py` | System hierarchy, subsystem extraction, function attachment; exports `SystemBuildConfig` |
| `archi2likec4/builders/domains.py` | Domain + subdomain assignment (multi-pass) |
| `archi2likec4/builders/integrations.py` | Integration building and interface path resolution |
| `archi2likec4/builders/data.py` | Data entities and dataStore detection |
| `archi2likec4/builders/deployment.py` | Deployment topology and node mapping; exports `DeploymentMappingContext` |
| `archi2likec4/builders/_result.py` | `BuildResult` NamedTuple and `BuildDiagnostics` dataclass — data contracts between build and generate phases |
| `archi2likec4/generators/spec.py` | LikeC4 spec file (kinds, tags) |
| `archi2likec4/generators/domains.py` | Domain and subdomain `.c4` files |
| `archi2likec4/generators/systems.py` | System detail `.c4` files |
| `archi2likec4/generators/entities.py` | Data entity `.c4` files |
| `archi2likec4/generators/relationships.py` | Cross-domain relationship files |
| `archi2likec4/generators/deployment.py` | Deployment view `.c4` files |
| `archi2likec4/generators/views.py` | Solution and system views; exports `ViewContext`, `build_view_context()` |
| `archi2likec4/generators/audit.py` | `AUDIT.md` quality report |
| `archi2likec4/templates/` | Jinja2 HTML templates for Flask web UI |
| `archi2likec4/exceptions.py` | Domain exceptions — `Archi2LikeC4Error`, `ConfigError`, `ParseError`, `ValidationError` |
| `archi2likec4/audit_data.py` | QA incident computation |
| `archi2likec4/web.py` | Flask audit dashboard (optional) |
| `archi2likec4/utils.py` | Shared utilities — `make_id()`, `transliterate()`, `escape_str()` |
| `archi2likec4/i18n.py` | ru/en message catalog |
| `tests/helpers.py` | Shared test mocks — `MockConfig`, `MockBuilt` |

## Element Hierarchy

archi2likec4 builds a 5-level element hierarchy in LikeC4:

1. **Domain** (L1) — functional business area (from `functional_areas/{domain}/` folder)
2. **Subdomain** (L2, optional) — nested functional group (from `functional_areas/{domain}/{subdomain}/`)
3. **System** (L3) — application system (ArchiMate ApplicationComponent)
4. **Subsystem** (L4) — component of system (dot notation: `SystemName.SubsystemName`)
5. **Function** (L5) — application function (ArchiMate ApplicationFunction)

Systems without subdomains skip L2; their path is `domain.system`.

## Validation Commands

```bash
ruff check archi2likec4/ tests/
python -m pytest tests/ -v --tb=short
mypy archi2likec4/ --ignore-missing-imports
```

## Test Conventions

- Use `MockConfig` and `MockBuilt` from `tests/helpers.py` for unit tests.
- Integration tests (e2e) in `tests/test_pipeline_e2e.py` use real XML fixtures.
- Coverage gate: 85% (`pytest --cov-fail-under=85`).

## Coding Standards

- **Logging**: always `logging.getLogger(__name__)` — never hardcode `'archi2likec4'`.
- **Exceptions**: raise domain exceptions from `archi2likec4.exceptions`:
  - Config issues → `ConfigError`
  - XML parse failures → `ParseError`
  - Validation gate failures → `ValidationError`
- **Line length**: 120 characters (ruff).
- **Typing**: `disallow_untyped_defs = true` for all modules except `web.py`, `parsers.py`, and `scripts/federate_template.py`.
- **NamedTuples**: `ParseResult` (pipeline.py) and `BuildResult` (_result.py) are the data contracts between phases — all fields must be fully typed.
