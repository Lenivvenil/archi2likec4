# Plan: Merge Review Branch and Close Remaining Issues

## Overview
Ветка `review-closed-issues` содержит исправления для 9 из 12 открытых issues (#2, #3, #4, #14, #19, #27, #28, #29, #34).
Нужно замержить ветку в main, закрыть решённые issues и устранить оставшиеся проблемы: PLR0913 (12 функций с избыточными параметрами) и stale type: ignore.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

### Task 1: Merge review-closed-issues and close resolved issues
Замержить ветку review-closed-issues в main и закрыть все issues, которые были решены в этой ветке.
- [x] Merge branch `review-closed-issues` into `main`
- [x] Close issue #2 (generate_solution_views split) with reference to commit
- [x] Close issue #3 (BuildResult diagnostics extraction) with reference to commit
- [x] Close issue #4 (BuildResult pass-through fields) with reference to commit
- [x] Close issue #14 (hardcoded 'prod') with reference to commit
- [x] Close issue #28 (mypy ignore_missing_imports scoped) with reference to commit
- [x] Close issue #29 (spec.py hardcoded colors/shapes/tags) with reference to commit
- [x] Close issue #34 (audit.py untyped-call) with reference to commit
- [x] Close issue #19 (Russian regex — partially fixed, patterns in config.py) with note explaining current state
- [x] Close issue #27 (C901 — as designed, 6 modules with documented justification) with note
- [x] Run validation commands to confirm main is green
- [x] Mark completed

### Task 2: Introduce ViewContext dataclass to reduce PLR0913 in views.py
Создать контекстный объект для передачи общих параметров в функции генерации views, сократив количество параметров с 6-13 до 2-4.
- [x] In `archi2likec4/generators/views.py`: create `ViewContext` dataclass grouping common parameters (config, systems, integrations, archi_to_c4, sys_domain, domain_systems, iface_c4_path, etc.)
- [x] Refactor `generate_solution_views()` to accept `ViewContext` instead of 10 individual params
- [x] Refactor `_dispatch_view()` to accept `ViewContext` instead of 13 params
- [x] Refactor `_generate_integration_view()` to accept `ViewContext` instead of 13 params
- [x] Refactor `_generate_system_view()` to accept `ViewContext` instead of 11 params
- [x] Refactor `_generate_domain_view()`, `_generate_functional_view()`, `_generate_deployment_view()` similarly
- [x] Update callers in `archi2likec4/pipeline.py` (`_generate()` function) to construct and pass `ViewContext`
- [x] Add/update tests for the above changes
- [x] Run validation commands — confirm zero PLR0913 violations in views.py
- [x] Mark completed

### Task 3: Introduce BuildContext to reduce PLR0913 in builders and pipeline
Создать контекстный объект для builder-функций и _generate(), чтобы устранить оставшиеся PLR0913 нарушения.
- [x] In `archi2likec4/builders/systems.py`: create `SystemBuildConfig` dataclass to reduce params in `build_systems()` and `_attach_subsystems()`
- [x] In `archi2likec4/builders/deployment.py`: create `DeploymentMappingContext` to reduce params in `build_deployment_map()` (currently 6)
- [x] In `archi2likec4/pipeline.py`: create `SolutionViewInfo` to reduce params in `_generate()`
- [x] In `archi2likec4/generators/views.py`: `_resolve_elements()` already uses ViewContext (3 params, fixed in Task 2)
- [x] Add/update tests for the above changes
- [x] Run `ruff check archi2likec4/ --select PLR0913` — confirm zero violations
- [x] Mark completed

### Task 4: Fix stale type: ignore and bare except
Устранить устаревшие type: ignore комментарии и bare except в config.py и audit_data.py (issue #33).
- [ ] In `archi2likec4/config.py`: audit all `type: ignore` comments — remove stale ones, narrow remaining to specific error codes
- [ ] In `archi2likec4/audit_data.py`: audit all `type: ignore` comments — remove stale ones
- [ ] In `archi2likec4/audit_data.py`: replace bare `except:` with specific exception types
- [ ] Run `mypy archi2likec4/ --ignore-missing-imports` — confirm no regressions
- [ ] Add/update tests if behavior changes
- [ ] Close issue #33 with reference to commit
- [ ] Mark completed

### Task 5: Update pygments and close CVE issue
Обновить pygments для устранения CVE-2026-4539 (issue #36).
- [ ] Check current pygments version in dev dependencies
- [ ] Update pygments to latest patched version in pyproject.toml or requirements
- [ ] Run validation commands to confirm no regressions
- [ ] Close issue #36 with reference to commit
- [ ] Mark completed
