# Plan: Refactor BuildResult — Extract Diagnostics and Remove Pass-Through Fields

## Overview
Исправляем два архитектурных HIGH issue: #3 (22-field NamedTuple со смешанными типами данных)
и #4 (pass-through поля из ParseResult в BuildResult). После рефакторинга BuildResult содержит
только то, что build-фаза произвела, диагностика вынесена в `BuildDiagnostics` dataclass.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Add BuildDiagnostics dataclass (#3)

Выделяем диагностические счётчики в отдельный dataclass, добавляем его как одно поле BuildResult.
BuildResult сжимается с 22 до 20 полей.

- [x] В `archi2likec4/builders/_result.py`: добавить `@dataclass(frozen=True) class BuildDiagnostics` с полями `orphan_fns: int`, `intg_skipped: int`, `intg_total_eligible: int`
- [x] В `archi2likec4/builders/_result.py`: заменить три поля `orphan_fns`, `intg_skipped`, `intg_total_eligible` в `BuildResult` на одно поле `diagnostics: BuildDiagnostics`
- [x] В `archi2likec4/pipeline.py`: в конструкторе BuildResult (~L325-348) заменить три отдельных значения на `BuildDiagnostics(orphan_fns=..., intg_skipped=..., intg_total_eligible=...)`
- [x] В `archi2likec4/audit_data.py`: заменить `built.orphan_fns` → `built.diagnostics.orphan_fns`, `built.intg_skipped` → `built.diagnostics.intg_skipped`, `built.intg_total_eligible` → `built.diagnostics.intg_total_eligible`
- [x] В `tests/helpers.py`: обновить `MockBuilt` — убрать три поля, добавить `diagnostics=BuildDiagnostics(orphan_fns=0, intg_skipped=0, intg_total_eligible=0)`
- [x] Закоммитить: `refactor: extract BuildDiagnostics from BuildResult (#3)`
- [x] Add/update tests for the above changes (`tests/test_audit_data.py`: убедиться что тесты используют `built.diagnostics.*`)
- [x] Mark completed

---

### Task 2: Remove pass-through fields from BuildResult (#4)

Убираем `solution_views`, `relationships`, `domains_info` из BuildResult — они принадлежат ParseResult.
ParseResult передаётся напрямую в функции generate-фазы.

- [ ] В `archi2likec4/builders/_result.py`: удалить поля `solution_views`, `relationships`, `domains_info` из `BuildResult` NamedTuple (с 20 до 17 полей)
- [ ] В `archi2likec4/pipeline.py` функция `_build()`: удалить строки `parsed.solution_views -> BuildResult.solution_views` и аналогичные для `relationships`, `domains_info` из конструктора BuildResult
- [ ] В `archi2likec4/pipeline.py` функция `_generate()`: добавить три параметра `solution_views: list[SolutionView]`, `relationships: list[RawRelationship]`, `domains_info: list[DomainInfo]`; заменить обращения `built.solution_views` → `solution_views` и т.д.
- [ ] В `archi2likec4/pipeline.py` функция `convert()`: при вызове `_generate(...)` передавать `solution_views=parsed.solution_views, relationships=parsed.relationships, domains_info=parsed.domains_info`
- [ ] В `tests/helpers.py`: удалить `solution_views`, `relationships`, `domains_info` из `MockBuilt`
- [ ] Закоммитить: `refactor: remove pass-through fields from BuildResult (#4)`
- [ ] Add/update tests for the above changes (e2e тест в `tests/test_pipeline_e2e.py` должен пройти)
- [ ] Mark completed
