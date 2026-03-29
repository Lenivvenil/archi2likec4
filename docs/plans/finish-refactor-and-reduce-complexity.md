# Plan: Finish Solution Views Refactor and Reduce Builder Complexity

## Overview
Завершаем рефакторинг `generate_solution_views()` (#2) — убираем последний `# noqa: C901` в generators,
затем снижаем цикломатическую сложность трёх C901-функций в builders/ (`assign_domains`, `assign_subdomains`,
`build_systems`). Цель — убрать все оставшиеся `# noqa: C901` в кодовой базе.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Finish generate_solution_views dispatcher refactor

Завершить план `refactor-solution-views.md` — `generate_solution_views()` (views.py:532) всё ещё имеет
`# noqa: C901`. Хелперы `_generate_functional_view`, `_generate_integration_view`, `_generate_deployment_view`
уже извлечены, но основная функция (~150 строк) содержит inline-логику, которую нужно делегировать.

- [x] В `archi2likec4/generators/views.py`: вынести precompute-блок (строки ~559-581: deploy_targets, sys_ids, rel_lookup, by_solution) в `_prepare_view_context()` → возвращает dataclass/NamedTuple с подготовленными данными
- [x] Упростить цикл `for solution_slug, views in ...` так, чтобы dispatch по `sv.view_type` был единственной веткой
- [x] Убрать `# noqa: C901` из `generate_solution_views`
- [x] Проверить: `ruff check archi2likec4/generators/views.py` — ноль C901
- [x] Исправить падающий тест `TestGenerateFunctionalView::test_empty_paths_returns_empty` в `tests/test_generators.py`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 2: Extract phases from assign_domains

`assign_domains()` в `archi2likec4/builders/domains.py:18` (~130 строк) содержит 4 последовательных прохода:
overrides, hit-based, promote_children, extra_patterns. Каждый проход — отдельная функция.

- [x] В `archi2likec4/builders/domains.py`: извлечь `_apply_domain_overrides(systems, domain_overrides, id_to_domains)` — проход 1
- [x] Извлечь `_assign_by_view_membership(systems, id_to_domains)` — проход 2 (hit counting)
- [x] Извлечь `_promote_children_domains(domain_systems, promote_children)` — проход 3
- [x] Извлечь `_apply_extra_patterns(domain_systems, unassigned, extra_domain_patterns)` — проход 4
- [x] Убрать `# noqa: C901` из `assign_domains`
- [x] Add/update tests for each extracted function in `tests/test_builders.py`
- [x] Mark completed

---

### Task 3: Extract phases from assign_subdomains

`assign_subdomains()` в `archi2likec4/builders/domains.py:113` (~180 строк) выполняет multi-phase subdomain
resolution с majority-vote fallback. Разбить на фазы.

- [ ] В `archi2likec4/builders/domains.py`: извлечь `_build_subdomain_lookup(parsed_subdomains, domain_systems)` — построение lookup-таблиц
- [ ] Извлечь `_assign_subdomain_by_folder(systems, subdomain_lookup)` — прямое назначение по принадлежности к папке
- [ ] Извлечь `_assign_subdomain_by_majority_vote(unassigned, integrations, subdomain_lookup)` — majority-vote fallback
- [ ] Убрать `# noqa: C901` из `assign_subdomains`
- [ ] Add/update tests for each extracted function in `tests/test_builders.py`
- [ ] Mark completed

---

### Task 4: Extract phases from build_systems

`build_systems()` в `archi2likec4/builders/systems.py:87` (~160 строк) выполняет 4-фазную конструкцию систем:
collect, promote, dot-names, attach. Разбить на фазы.

- [ ] В `archi2likec4/builders/systems.py`: извлечь `_collect_systems(components, filter_fn)` — фаза 1 (сбор и фильтрация)
- [ ] Извлечь `_promote_subsystems(systems, promote_children)` — фаза 2 (продвижение)
- [ ] Извлечь `_resolve_dot_names(systems)` — фаза 3 (парсинг `Parent.Child` нотации)
- [ ] Убрать `# noqa: C901` из `build_systems`
- [ ] Add/update tests for each extracted function in `tests/test_builders.py`
- [ ] Mark completed

---

### Task 5: Verify zero C901 suppressions and cleanup

Финальная проверка: ни одного `# noqa: C901` во всём проекте.

- [ ] Выполнить `grep -r 'noqa: C901' archi2likec4/` — должен вернуть 0 результатов
- [ ] `ruff check archi2likec4/` — 0 предупреждений
- [ ] Убедиться что покрытие ≥ 85%
- [ ] Обновить `docs/plans/refactor-solution-views.md` — отметить все задачи как выполненные, переместить в `docs/plans/completed/`
- [ ] Закоммитить: `refactor: eliminate all C901 suppressions in builders and generators (#2)`
- [ ] Add/update tests for the above changes
- [ ] Mark completed
