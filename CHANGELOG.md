# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **PyPI publish workflow**: `.github/workflows/publish.yml` — trusted OIDC publishing on GitHub Release (TestPyPI → PyPI)
- **ApplicationService resolution**: parse, resolve ownership, integrate into views and integrations
- **View hierarchy navigation**: folder-based `/` titles for LikeC4 sidebar tree
- **Deployment diagram fixes**: infraSoftware shape (rectangle), appFunction exclusion

### Fixed
- **[P1] Deployment view unresolved ratio**: appFunction elements no longer inflate `total_elements` denominator, giving accurate unresolved metrics
- **[P1] Trash filter state leak**: `DEFAULT_TRASH_NAMES` mutation now wrapped in try/finally to restore default between runs (critical for web process)
- **[P2] CSRF hardening**: POST without Origin or Referer header now rejected (403), closing blind CSRF vector
- **[P2] Domain sanitization in /promote-system**: `sanitize_path_segment()` now applied consistently (was missing vs /assign-domain)
- **[P2] C4 identifier validation in domain_renames**: new_id must match `^[a-z_][a-z0-9_-]*$` to prevent syntactically invalid .c4 output

### Changed
- Test count: 369 → 413

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
