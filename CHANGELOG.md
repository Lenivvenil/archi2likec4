# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **dataStore**: automatic detection of database SystemSoftware (PostgreSQL, Oracle, Redis, MongoDB, etc.) → `dataStore` element kind on deployment diagrams
- **dataStore↔dataEntity links**: `build_datastore_entity_links()` via AccessRelationship, generates `persists` relationships
- **i18n**: bilingual (ru/en) message catalog for all 10 QA incidents + audit report headers
- **Language config**: `language: ru|en` in `.archi2likec4.yaml`
- **Bank-specific constants decoupled**: DOMAIN_RENAMES, EXTRA_DOMAIN_PATTERNS, PROMOTE_CHILDREN moved from models.py to config.py defaults

## [1.0.0] — 2026-03-09

### Added
- **Core converter**: 4-phase pipeline (parse → build → validate → generate) for coArchi XML → LikeC4 .c4
- **Element kinds**: domain, system, subsystem, appFunction, dataEntity, infraNode, infraSoftware, infraLocation
- **Deployment topology**: 735 nodes, 383 app→infra mappings, Location elements (ЦОД)
- **Solution views**: functional, integration, and deployment diagram generation
- **Quality audit**: 10 QA incidents (QA-1..QA-10) with AUDIT.md report generation
- **Web UI**: Flask audit dashboard, incident detail, remediations review, system hierarchy pages
- **Configuration**: `.archi2likec4.yaml` — domain overrides, promote_children, audit_suppress, quality gates
- **Federation**: multi-project support via `federate_template.py`
- **CLI**: `archi2likec4` entry point with `--strict`, `--verbose`, `--dry-run` flags; `web` subcommand
- **PEP 561**: `py.typed` marker for type checker discovery

### Architecture highlights
- 289 systems, 94 subsystems, 1656 functions, 309 data entities parsed from ArchiMate model
- Cross-layer relationships via ApplicationService realization
- Domain assignment: folder-based detection + regex patterns + manual overrides
- Subsystem promotion for complex systems (EFS, EFS_PLT)

## [0.x] — Pre-release iterations

Iterations 1–17 tracked in NOTES.md. Key milestones:
- **Iter 1–9**: Core parsing, building, generation pipeline
- **Iter 10–13**: Config system, federation, solution views, deployment topology
- **Iter 14**: Code review fixes (8 findings)
- **Iter 15**: Quality incident register (AUDIT.md)
- **Iter 16–17**: Web UI audit dashboard + remediation actions
