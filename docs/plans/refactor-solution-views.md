# Plan: Split generate_solution_views into Per-Type Functions

## Overview
Разбиваем монолитную функцию `generate_solution_views()` в `generators/views.py` (384 строки,
`# noqa: C901`) на три специализированные функции и общий resolver. Каждая функция отвечает
за один тип view: functional, integration, deployment. Снимаем `# noqa: C901`.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Extract shared element resolution logic

Дублированная логика резолвинга archi_id → c4_path используется в трёх ветках — выносим в хелпер.

- [x] В `archi2likec4/generators/views.py`: создать функцию `_resolve_elements(element_archi_ids, archi_to_c4, promoted_archi_to_c4, tech_archi_to_c4, entity_archi_ids, view_type) -> tuple[list[str], list[str]]` — первый список resolved c4_paths, второй unresolved archi_ids
- [x] Функция должна заменить дублированный resolution-блок (~lines 211-261) из трёх веток `if view_type ==`
- [x] Сигнатура должна быть полностью типизирована (`dict[str, str]`, `dict[str, list[str]] | None`, `set[str] | None`)
- [x] Add/update tests for the above changes (unit-тест `_resolve_elements` в `tests/test_generators.py`)
- [x] Mark completed

---

### Task 2: Extract _generate_deployment_view()

Выносим deployment view generation в отдельную функцию.

- [x] В `archi2likec4/generators/views.py`: создать `_generate_deployment_view(view, resolved_elements, deployment_map, tech_archi_to_c4, deployment_env) -> tuple[str, int, int]` — возвращает (file_content, unresolved_count, total_elements)
- [x] Перенести логику из `generate_solution_views` для `view_type == 'deployment'` (~lines 444-502) в эту функцию
- [x] Использовать `_resolve_elements()` из Task 1 для резолвинга
- [x] Убедиться что ancestor dedup для infra paths и `{deployment_env}.{ip}.**` логика перенесена корректно
- [x] Add/update tests for the above changes (unit-тест `_generate_deployment_view` в `tests/test_generators.py`)
- [x] Mark completed

---

### Task 3: Extract _generate_functional_view() and _generate_integration_view()

Выносим functional и integration view generation.

- [ ] В `archi2likec4/generators/views.py`: создать `_generate_functional_view(view, resolved_elements, sys_domain, sys_subdomain) -> tuple[str, int, int]`
- [ ] Перенести логику functional view (~lines 282-337) используя `_resolve_elements()` из Task 1
- [ ] В `archi2likec4/generators/views.py`: создать `_generate_integration_view(view, resolved_elements, entity_archi_ids, relationships, archi_to_c4, promoted_archi_to_c4, sys_domain, sys_subdomain) -> tuple[str, int, int]`
- [ ] Перенести логику integration view (~lines 339-442) включая orphan removal и entity cap логику
- [ ] Add/update tests for the above changes (unit-тесты обоих функций в `tests/test_generators.py`)
- [ ] Mark completed

---

### Task 4: Refactor generate_solution_views() to dispatcher and cleanup

Главная функция становится dispatcher'ом, снимаем C901.

- [ ] В `archi2likec4/generators/views.py`: переписать `generate_solution_views()` как thin dispatcher — итерация по `solution_views`, вызов нужной `_generate_*_view()` функции
- [ ] Убрать `# noqa: C901` из строки функции
- [ ] Убрать unreachable `else`-блок (если был)
- [ ] Итоговый размер `generate_solution_views()` должен быть ≤ 60 строк
- [ ] `ruff check` без C901 предупреждений
- [ ] Закоммитить: `refactor: split generate_solution_views into per-type functions, remove C901 noqa (#2)`
- [ ] Add/update tests for the above changes (интеграционный тест через `tests/test_pipeline_e2e.py`)
- [ ] Mark completed
