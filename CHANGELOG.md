# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.1.0] — 2026-03-16

### Added
- **Five-level application hierarchy**: L1 domain → L2 subdomain → L3 system → L4 subsystem → L5 function
- **`subdomain` LikeC4 kind**: new element kind with amber colour between domain and system
- **Auto-detection of subdomains**: from nested `functional_areas/{domain}/{subdomain}/` folder structure in coArchi XML
- **Subdomain rendering**: systems grouped inside subdomain blocks in `domains/{id}.c4`; graceful fallback (no subdomain) for flat domain folders
- **i18n keys**: `subdomain`, `subdomain_plural`, `l2_subdomain_label` in ru/en catalogs
- **Web UI hierarchy**: `/hierarchy` page shows subdomain level between domain and system
- **`tools/` directory**: diagnostic scripts (stats.py, diag_targets.py, diag_dupes.py, diag_views.py, diag_orphan_subsystems.py) moved out of root for cleaner project layout

### Changed
- **`builders/` package**: `builders.py` split into `builders/` package (`systems.py`, `domains.py`, `integrations.py`, `deployment.py`, `datastore.py`)
- **`generators/` package**: `generators.py` split into `generators/` package (`domains.py`, `systems.py`, `relationships.py`, `deployment.py`, `views.py`, `audit.py`)
- **`templates/` directory**: Jinja2 templates extracted from inline Python strings to `.j2` files
- **Coverage gate**: test coverage gated at 85%, 413+ tests across 12 files
- **Public API**: `archi2likec4/__init__.py` exports clean public surface (`ConvertConfig`, `load_config`, `run_pipeline`)

### Removed
- `convert.py` root script (duplicated `archi2likec4` console_scripts entrypoint)
- `NOTES.md` (development scratch notes; added to `.gitignore`)

## [1.0.0] — 2026-03-09

### Added
- **Core converter**: 4-phase pipeline (parse → build → validate → generate) for coArchi XML → LikeC4 .c4
- **Element kinds**: domain, system, subsystem, appFunction, dataEntity, infraNode, infraSoftware, infraLocation, dataStore
- **Deployment topology**: 735 nodes, 383 app→infra mappings, Location elements (ЦОД)
- **dataStore**: automatic detection of database SystemSoftware (PostgreSQL, Oracle, Redis, MongoDB, etc.)
- **dataStore↔dataEntity links**: `build_datastore_entity_links()` via AccessRelationship
- **Solution views**: functional, integration, and deployment diagram generation
- **Quality audit**: 10 QA incidents (QA-1..QA-10) with AUDIT.md report generation
- **Web UI**: Flask audit dashboard, incident detail, remediations review, system hierarchy pages
- **Configuration**: `.archi2likec4.yaml` — domain overrides, promote_children, audit_suppress, quality gates
- **i18n**: bilingual (ru/en) message catalog for all QA incidents + audit report
- **Federation**: multi-project support via `federate_template.py`
- **CLI**: `archi2likec4` entry point with `--strict`, `--verbose`, `--dry-run` flags; `web` subcommand
- **CI**: GitHub Actions workflow (Python 3.10–3.13, ruff, pytest, mypy)
- **PEP 561**: `py.typed` marker for type checker discovery

### Security & reliability (code review rounds 1–6)
- **Output safety**: `.archi2likec4-output` marker file prevents accidental `rmtree` of non-generated directories
- **Open redirect protection**: `_safe_redirect()` rejects protocol-relative URLs (`//`)
- **Config validation**: type checks for all mapping fields, negative threshold guards, unknown keys warning
- **Integration accuracy**: `AggregationRelationship` excluded from integration builder; `total_eligible` metric for QA-7
- **Web hardening**: `model_root.is_dir()` fail-fast, `_load_config_safe()` for all mutation routes, `RuntimeError` handler
- **PyYAML error contract**: `RuntimeError` instead of `SystemExit` for uniform CLI error handling

### Architecture highlights
- 289 systems, 94 subsystems, 1656 functions, 309 data entities parsed from ArchiMate model
- Cross-layer relationships via ApplicationService realization
- Domain assignment: folder-based detection + regex patterns + manual overrides
- Subsystem promotion for complex systems
- Bank-specific constants decoupled to config defaults
- 369 tests across 12 test files

## [0.x] — Pre-release iterations

Iterations 1–17 tracked in NOTES.md. Key milestones:
- **Iter 1–9**: Core parsing, building, generation pipeline
- **Iter 10–13**: Config system, federation, solution views, deployment topology
- **Iter 14**: Code review fixes (8 findings)
- **Iter 15**: Quality incident register (AUDIT.md)
- **Iter 16–17**: Web UI audit dashboard + remediation actions
