# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.3.0] — 2026-03-20

### Added
- **Public `convert()` API** (`pipeline.py`): library-safe function returning `ConvertResult` dataclass — never calls `sys.exit()`. Raises `ConfigError`, `ParseError`, `ValidationError`, `FileNotFoundError` on failure
- **`ConvertResult`** dataclass: `systems_count`, `integrations_count`, `files_written`, `warnings`, `output_dir` fields; exported from `archi2likec4`
- **`--version` CLI flag**: `archi2likec4 --version` prints the installed package version
- **`web` subcommand visible in `--help`**: shown via argparse epilog with `RawDescriptionHelpFormatter`
- **`ParseError` activation** (`parsers.py`): all `parse_*` functions raise `ParseError` when all XML files in a directory fail to parse
- **`ValidationError` activation** (`pipeline.py`): `convert()` raises `ValidationError` when quality gates fail (`gate_errors > 0`) or in strict mode with warnings
- **Configurable `property_map` and `standard_keys`** (`ConvertConfig`): defaults from `DEFAULT_PROP_MAP` / `DEFAULT_STANDARD_KEYS` (renamed from private `_PROP_MAP` / `_STANDARD_KEYS`)
- **Configurable `sync_protected_top` and `sync_protected_paths`** (`ConvertConfig`): move sync protection out of hardcoded module constants into config fields (default: empty)
- **Dynamic version** (`__init__.py`): reads from `importlib.metadata` with fallback `'1.3.0'`
- **`tests/test_api.py`**: tests for public `convert()` API — success, dry-run, missing root, validation errors, config/parse errors
- **`TestParserErrorPaths`** (`tests/test_parsers.py`): malformed XML and `ParseError` tests for all `parse_*` functions, `_is_in_trash`, and `_detect_special_folder`

### Changed
- **`main()` refactored** as thin wrapper around `convert()`, handling exceptions → `sys.exit()` codes
- **`DEFAULT_PROP_MAP` / `DEFAULT_STANDARD_KEYS`** made public (previously `_PROP_MAP` / `_STANDARD_KEYS`) for reuse and config defaults
- **`build_metadata()`** (`utils.py`): accepts optional `prop_map` and `standard_keys` parameters
- **Version bump**: `1.2.0` → `1.3.0`

### Removed
- `DOMAIN_RENAMES`, `EXTRA_DOMAIN_PATTERNS`, `PROMOTE_CHILDREN` dead constants from `models.py` (superseded by `config.py` defaults)
- `_SYNC_PROTECTED_TOP` / `_SYNC_PROTECTED_PATHS` hardcoded module constants in `pipeline.py`

## [1.2.0] — 2026-03-20

### Added
- **Custom exception hierarchy** (`exceptions.py`): `Archi2LikeC4Error`, `ConfigError`, `ParseError`, `ValidationError` — replaces bare `ValueError`/`RuntimeError` raises across config and web
- **CLAUDE.md**: developer guide covering architecture, key files, coding standards, and validation commands
- **PyPI publish workflow** (`.github/workflows/publish.yml`): OIDC trusted publishing on GitHub release

### Changed
- **Standardized logging**: all modules now use `logging.getLogger(__name__)` instead of hardcoded `'archi2likec4'`
- **Typed `BuildResult`** (`builders/_result.py`): all 22 fields fully typed
- **Typed `ParseResult`** (`pipeline.py`): all 9 fields fully typed
- **Stricter mypy**: removed `disallow_untyped_defs = false` overrides for `archi2likec4.config` and `archi2likec4.builders`; fixed `list[dict]` → `list[dict[str, Any]]`
- **Version bump**: `1.1.0` → `1.2.0`

### Fixed
- `config.py`: all validation errors now raise `ConfigError` (subclass of `Archi2LikeC4Error`) instead of `ValueError`
- `web.py`: error handler now catches `ConfigError` instead of `RuntimeError`

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
- **`builders/` package**: `builders.py` split into `builders/` package (`systems.py`, `domains.py`, `integrations.py`, `deployment.py`, `data.py`)
- **`generators/` package**: `generators.py` split into `generators/` package (`domains.py`, `systems.py`, `relationships.py`, `deployment.py`, `views.py`, `audit.py`)
- **`templates/` directory**: Jinja2 templates extracted from inline Python strings to `.html` files
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
