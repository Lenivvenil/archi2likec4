# Plan: Five-Level Application Component Hierarchy

## Overview
Вводим пятиуровневую иерархию прикладных компонентов: L1 домен → L2 субдомен → L3 система (context) → L4 подсистема (container) → L5 прикладная функция (component). Сейчас уровень субдомена отсутствует: системы находятся непосредственно под доменами. Новый уровень вводится как LikeC4-kind `subdomain`, детектируется из вложенности папок `diagrams/functional_areas/{domain}/{subdomain}/` (или через naming-pattern в ApplicationComponent), встраивается в data-model, builder и generator.

## Validation Commands
- `python -m pytest tests/ -x -q`
- `python -m ruff check archi2likec4/ --select E,F,W`
- `python -c "from archi2likec4 import pipeline; print('import ok')" `

---

### Task 1: Define Subdomain Data Model and Detection Strategy
Добавить в `models.py` датакласс `Subdomain` и определить источник данных для субдоменов в Archi XML.
- [x] Прочитать `archi2likec4/models.py` и добавить `@dataclass class Subdomain` с полями: `c4_id: str`, `name: str`, `domain_id: str`, `system_ids: list[str]` (по аналогии с `System`)
- [x] В `archi2likec4/models.py` добавить `Subdomain` в `__all__` / экспорт рядом с `System`, `Domain`
- [x] Прочитать `archi2likec4/parsers.py` — найти, как сканируются папки `functional_areas/{domain}/`, и определить, какая структура используется для субдоменов: вложенные папки `{domain}/{subdomain}/` или naming-pattern `Parent.Child` в ApplicationComponent на уровне домена
- [x] В `archi2likec4/parsers.py` добавить извлечение субдоменов: собирать промежуточный уровень папок (`functional_areas/{domain}/{subdomain}/`) в новый `ParsedSubdomain(archi_id, name, domain_folder, component_ids)`; если вложенных папок нет — документировать fallback (субдомен = домен, уровень пропускается)
- [x] Добавить `parsed_subdomains: list[ParsedSubdomain]` в `ParseResult` NamedTuple
- [x] Add/update tests for the above changes (`tests/test_parsers.py`: тест `test_subdomain_folder_extraction` с фиктивным XML-деревом с двумя уровнями папок)
- [x] Mark completed

---

### Task 2: Update Builder — Assign Systems to Subdomains
В `archi2likec4/builders.py` после определения домена системы определять субдомен и строить путь `domain.subdomain.system`.
- [x] Прочитать `archi2likec4/builders.py`, блок domain-assignment (функции ~строки 641–733), понять текущий `c4_path = f"{domain_id}.{system_id}"`
- [x] Добавить `subdomain_systems: dict[str, list[str]]` и `subdomains: list[Subdomain]` в `BuildResult` NamedTuple
- [x] В builder: после Pass 1–3 domain-assignment добавить Pass 4 — subdomain assignment: для каждой системы найти субдомен по `parsed_subdomains` (проверка, входит ли `archi_id` системы в `component_ids` субдомена)
- [x] Пересчитать `system.c4_path` с учётом субдомена: `domain_id.subdomain_id.system_id` (если субдомен есть) или оставить `domain_id.system_id` (fallback без субдомена)
- [x] Пересчитать пути зависимых элементов (`Subsystem.c4_path`, `AppFunction.c4_path`, `Integration`, `DataAccess`) — они строятся от `system.c4_path`, поэтому должны наследовать новый путь автоматически; проверить и при необходимости явно обновить
- [x] Add/update tests (`tests/test_builders.py`): `test_system_assigned_to_subdomain`, `test_system_without_subdomain_falls_back`, `test_integration_path_includes_subdomain`)
- [x] Mark completed

---

### Task 3: Update LikeC4 Specification — Add `subdomain` Kind
Добавить `subdomain` в `specification.c4` (цвет, стиль, иконка) по аналогии с `domain` и `system`.
- [x] Прочитать `archi2likec4/generators.py`, найти блок генерации `specification.c4` (блок `specification { ... }`)
- [x] Добавить `element subdomain` с цветом (например, amber/secondary между domain и system), стилем `shape: rectangle`, иконкой по аналогии с `domain`
- [x] Прочитать шаблоны/строки для `domain` (как рендерится `domain` в `domains/{id}.c4`) и создать аналогичный шаблон для `subdomain` внутри домена
- [x] Убедиться, что `subdomain` добавлен в README/комментарии specification рядом с другими kinds
- [x] Add/update tests (`tests/test_generators.py`): `test_specification_contains_subdomain_kind`)
- [x] Mark completed

---

### Task 4: Update Generator — Render Subdomains in Domain Files
Изменить рендеринг `domains/{id}.c4`: системы оборачивать в блок субдомена, если субдомен назначен.
- [x] Прочитать `archi2likec4/generators.py`, найти функцию генерации `domains/{id}.c4` (блок где итерируются системы домена)
- [x] Добавить группировку систем по субдоменам: если у домена есть субдомены, вначале рендерить `{subdomain_id} = subdomain "{subdomain_name}" { ... }`, внутри — системы этого субдомена; системы без субдомена рендерить напрямую в домен (fallback)
- [x] Проверить, что `systems/{id}.c4` (подсистемы и функции) не требует изменений — пути уже пересчитаны в Task 2; исправлен `generate_system_detail_c4`: путь теперь `domain.subdomain.system` если субдомен назначен
- [x] Проверить `relationships.c4` — пути интеграций теперь включают субдомен, убедиться что они правильно рендерятся
- [x] Проверить `solutions/` views — пути элементов в solution views должны использовать обновлённые `c4_path`
- [x] Add/update tests (`tests/test_generators.py`): `test_domain_file_contains_subdomain_block`, `test_system_nested_in_subdomain`, `test_system_without_subdomain_at_domain_root`)
- [x] Mark completed

---

### Task 5: Update AUDIT and QA — Propagate Subdomain Awareness
Обновить диагностику (QA incidents) и Web UI для отображения нового уровня иерархии.
- [x] Прочитать `archi2likec4/audit_data.py` — найти QA-1 (unassigned systems) и QA-6 (orphan functions); проверить, что пути систем с субдоменами корректно попадают в отчёты
- [x] Обновить `archi2likec4/i18n.py` — добавить ключи `subdomain`, `subdomain_plural`, `l2_subdomain_label` в Russian и English каталоги
- [x] Прочитать `archi2likec4/web.py` — найти блоки где отображается `domain → system` иерархия в `/hierarchy` и dashboard; добавить уровень субдомена в дерево
- [x] Обновить `tests/helpers.py` (`MockBuilt`) — добавить `subdomains=[]` и `subdomain_systems={}` дефолты в `MockBuilt`
- [x] Обновить `tests/test_audit_data.py` если есть тесты, зависящие от структуры `BuildResult`
- [x] Add/update tests (`tests/test_web.py`): `test_hierarchy_page_shows_subdomain_level`)
- [x] Mark completed

---

### Task 6: Integration, Cleanup, and Documentation
Связать все компоненты, убрать TODO, обновить документацию и пример конфига.
- [x] Запустить полный набор тестов `python -m pytest tests/ -x -q`; устранить все падения
- [x] Прочитать `.archi2likec4.example.yaml` — добавить пример секции `subdomain_overrides` (по аналогии с `domain_overrides`) если нужна ручная привязка системы к субдомену
- [x] Прочитать `README.md` — обновить раздел про иерархию элементов (добавить строку L2 subdomain)
- [x] Прочитать `CHANGELOG.md` — добавить запись в `[Unreleased]` про новый уровень субдомена
- [x] Убрать все TODO/FIXME, добавленные в Tasks 1–5
- [x] Запустить `python -m ruff check archi2likec4/ --select E,F,W` — исправить предупреждения
- [x] Mark completed
