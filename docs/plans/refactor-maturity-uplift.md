# Plan: Full Project Refactoring and Maturity Uplift

## Overview
Проект накопил технический долг: раздутые модули (builders 1258, generators 1208, web 1081 строк), дублированная i18n-система в web.py, устаревшая документация и минимальный ruleset линтера. Цель — разбить жирные модули на пакеты, унифицировать i18n, ужесточить линтинг/типизацию, закрыть пробелы в тестах, актуализировать документацию и убрать мусорные файлы.

## Validation Commands
- `python -m pytest tests/ -x -q`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Foundation — Public API Extract, Linting Uplift, Coverage Gate
Подготовить фундамент: вынести `_flatten_deployment_nodes` в публичный API, расширить ruff ruleset, ужесточить mypy, добавить coverage gate.
- [x] Прочитать `archi2likec4/utils.py` и добавить публичную функцию `flatten_deployment_nodes(nodes: list[DeploymentNode]) -> list[DeploymentNode]` — скопировать реализацию из `archi2likec4/builders.py` (строки ~1108–1114), добавить импорт `DeploymentNode` из `.models`
- [x] В `archi2likec4/builders.py`: добавить `flatten_deployment_nodes` в `from .utils import ...`; заменить тело `_flatten_deployment_nodes` на `_flatten_deployment_nodes = flatten_deployment_nodes` (backward compat alias); обновить прямые call sites внутри builders.py на `flatten_deployment_nodes`
- [x] В `archi2likec4/pipeline.py` (~строка 287): заменить `from .builders import _flatten_deployment_nodes` на `from .utils import flatten_deployment_nodes`; обновить `_flatten_deployment_nodes(...)` → `flatten_deployment_nodes(...)`
- [x] В `archi2likec4/audit_data.py` (~строка 320): заменить `from .builders import _flatten_deployment_nodes` на `from .utils import flatten_deployment_nodes`; обновить call site
- [x] В `stats.py` (~строка 22): обновить `from archi2likec4.builders import _flatten_deployment_nodes` → `from archi2likec4.utils import flatten_deployment_nodes`; обновить call site (~строка 428)
- [x] В `pyproject.toml` секция `[tool.ruff.lint]`: изменить `select = ["E", "F", "W", "I"]` на `select = ["E", "F", "W", "I", "B", "UP", "SIM", "C90", "PT"]`
- [x] В `pyproject.toml`: добавить секцию `[tool.ruff.lint.mccabe]` с `max-complexity = 15`
- [x] В `pyproject.toml` секция `[tool.mypy]`: установить `disallow_untyped_defs = true`; добавить `[[tool.mypy.overrides]]` для `module = "archi2likec4.web"` с `disallow_untyped_defs = false` (web.py рефакторится в Task 4)
- [x] В `pyproject.toml` секция `[tool.pytest.ini_options]`: добавить `addopts = "--cov=archi2likec4 --cov-fail-under=80"`; добавить секции `[tool.coverage.run]` (`source = ["archi2likec4"]`) и `[tool.coverage.report]` (`show_missing = true`)
- [x] Запустить `ruff check archi2likec4/ tests/ --fix` для автоматических исправлений; исправить оставшиеся violations вручную (приоритет: UP pyupgrade, SIM simplify, PT pytest conventions)
- [x] Добавить отсутствующие type annotations во все функции `archi2likec4/pipeline.py` и `archi2likec4/audit_data.py` до прохождения mypy
- [x] Add/update tests: в `tests/test_utils.py` добавить тесты для `flatten_deployment_nodes` — пустой список, плоский список, вложенное дерево (использовать `archi2likec4.models.DeploymentNode`)
- [x] Mark completed

---

### Task 2: Split builders.py into Package
Разбить `archi2likec4/builders.py` (1258 строк, 23 функции) на логические подмодули. Внешний API не меняется — всё реэкспортируется через `__init__.py`.
- [x] Прочитать `archi2likec4/builders.py` полностью; определить группы функций: systems, domains, integrations, deployment, data
- [x] Создать директорию `archi2likec4/builders/` и файл `archi2likec4/builders/__init__.py` — реэкспорт всего публичного API: `BuildResult`, `build_systems`, `assign_domains`, `build_integrations`, `build_deployment`, `build_data_entities`, `build_data_access`, `datastore_entity_links`, `assign_subdomains`, `apply_domain_prefix`; также реэкспортировать `_flatten_deployment_nodes` (backward compat alias → `flatten_deployment_nodes` из utils)
- [x] Создать `archi2likec4/builders/systems.py` — перенести: `build_systems`, `_resolve_app_services`, `attach_functions`, `attach_interfaces`, `_classify_interface`, `_attach_subsystems`, `_assign_tags`, `_make_unique_id`, `_extract_url`; прописать все необходимые imports из models, utils
- [x] Создать `archi2likec4/builders/domains.py` — перенести: `assign_domains`, `assign_subdomains`, `apply_domain_prefix`, `_match_extra_domain`; прописать imports
- [x] Создать `archi2likec4/builders/integrations.py` — перенести: `build_integrations`, `_dedup_integrations`; прописать imports
- [x] Создать `archi2likec4/builders/deployment.py` — перенести: `build_deployment`, `_build_deployment_path_index`, `_build_comp_c4_path`, `_build_comp_index`, `enrich_deployment_from_visual_nesting`, `build_tech_archi_to_c4_map`; прописать imports
- [x] Создать `archi2likec4/builders/data.py` — перенести: `build_data_entities`, `build_data_access`, `datastore_entity_links`, `_is_db_software`; прописать imports
- [x] Перенести `BuildResult` NamedTuple в `archi2likec4/builders/__init__.py` или в отдельный `archi2likec4/builders/_result.py` (импортировать в __init__)
- [x] Удалить оригинальный `archi2likec4/builders.py`
- [x] Add/update tests: запустить `tests/test_builders.py` — убедиться что все тесты проходят без изменений (реэкспорт должен обеспечить полную совместимость); исправить если что-то сломалось
- [x] Mark completed

---

### Task 3: Split generators.py into Package
Разбить `archi2likec4/generators.py` (1208 строк, 21 функция) на логические подмодули по аналогии с Task 2.
- [x] Прочитать `archi2likec4/generators.py` полностью; определить группы функций
- [x] Создать `archi2likec4/generators/` пакет с `__init__.py` — реэкспорт всего публичного API: `generate_specification`, `generate_domain_files`, `generate_subdomain_content`, `generate_system_detail`, `generate_relationships`, `generate_landscape_view`, `generate_functional_views`, `generate_integration_views`, `generate_solution_views`, `generate_deployment_views`, `generate_audit_markdown`, `generate_data_entities`
- [x] Создать `archi2likec4/generators/spec.py` — перенести: `generate_specification`, `_kind_block`, `_rel_block`
- [x] Создать `archi2likec4/generators/domains.py` — перенести: `generate_domain_files`, `generate_subdomain_content`, `_domain_header`, `_system_element`
- [x] Создать `archi2likec4/generators/systems.py` — перенести: `generate_system_detail`, `_interface_section`, `_function_section`, `_render_system`
- [x] Создать `archi2likec4/generators/relationships.py` — перенести: `generate_relationships`
- [x] Создать `archi2likec4/generators/views.py` — перенести: `generate_landscape_view`, `generate_functional_views`, `generate_integration_views`, `generate_solution_views`, `generate_deployment_views`
- [x] Создать `archi2likec4/generators/audit.py` — перенести: `generate_audit_markdown`, `_incident_block`, `_build_persistence_map`
- [x] Создать `archi2likec4/generators/entities.py` — перенести: `generate_data_entities`, `_entity_block`
- [x] Удалить оригинальный `archi2likec4/generators.py`
- [x] Add/update tests: запустить `tests/test_generators.py` — убедиться что все тесты проходят без изменений; исправить если что-то сломалось
- [x] Mark completed

---

### Task 4: Web UI Detangle — Extract Templates, Unify i18n
Разгрузить `archi2likec4/web.py` (1081 строк): вынести inline HTML-шаблоны в файлы, объединить `_UI_STRINGS` в web.py с `i18n.py`.
- [x] Прочитать `archi2likec4/web.py` полностью; найти все строковые константы-шаблоны (`_DASHBOARD_TEMPLATE`, `_DETAIL_TEMPLATE`, `_REMEDIATIONS_TEMPLATE`, `_HIERARCHY_TEMPLATE`, `_BASE_CSS`, `_THEME_JS`) и dict `_UI_STRINGS`
- [x] Создать директорию `archi2likec4/templates/`
- [x] Создать `archi2likec4/templates/base.html` с общим layout: перенести CSS из `_BASE_CSS` и JS из `_THEME_JS`; использовать Jinja2 блоки (`{% block title %}`, `{% block content %}`)
- [x] Создать `archi2likec4/templates/dashboard.html` из `_DASHBOARD_TEMPLATE` — наследовать base.html через `{% extends "base.html" %}`
- [x] Создать `archi2likec4/templates/detail.html` из `_DETAIL_TEMPLATE`
- [x] Создать `archi2likec4/templates/remediations.html` из `_REMEDIATIONS_TEMPLATE`
- [x] Создать `archi2likec4/templates/hierarchy.html` из `_HIERARCHY_TEMPLATE`
- [x] Прочитать `archi2likec4/i18n.py`; добавить в него `WEB_MESSAGES: dict[str, dict[str, str]]` — перенести содержимое `_UI_STRINGS` из web.py; добавить публичную функцию `get_web_msg(key: str, lang: str) -> str`
- [x] Обновить `archi2likec4/web.py`: удалить `_UI_STRINGS` и все строковые шаблоны; загружать шаблоны через Flask `render_template()`; i18n через `from .i18n import get_web_msg`; Flask app создавать с `template_folder=Path(__file__).parent / "templates"`; целевой размер ≤ 400 строк
- [x] Обновить `pyproject.toml`: в `[tool.setuptools.packages.find]` добавить `package_data = {"archi2likec4" = ["templates/*.html"]}` (или секцию `[tool.setuptools.package-data]`)
- [x] Add/update tests: запустить `tests/test_web.py` — адаптировать если изменился способ создания Flask app; убедиться что все тесты зелёные
- [x] Mark completed

---

### Task 5: Test Completeness — Gap Fill and Mock Cleanup
Закрыть пробелы в тестовом покрытии: `models.py` (0 прямых тестов), `federation.py` (0 тестов), `pipeline._validate` (не тестирован). Привести `MockConfig`/`MockBuilt` в порядок.
- [x] Прочитать `archi2likec4/models.py` полностью; создать `tests/test_models.py` с тестами: конструкция всех dataclass, defaults, edge cases для NS constants, `TRANSLIT_MAP`, `RESERVED_WORDS`, `METADATA_MAPPING`
- [x] Прочитать `archi2likec4/federation.py` (39 строк); если `tests/test_federate.py` уже существует — расширить, иначе создать; добавить тесты для `generate_federate_script()` и `generate_registry()`
- [x] Прочитать `archi2likec4/pipeline.py`, найти функцию `_validate()`; расширить `tests/test_pipeline_e2e.py` тестами для `_validate()` — проверка QA gate violations, strict mode abort, verbose logging paths
- [x] Прочитать `tests/helpers.py`; обновить `MockConfig` — добавить все поля `ConvertConfig` с дефолтами: `language="ru"`, `subdomain_overrides={}`, `strict=False`, `verbose=False`, `dry_run=False`, все quality gate поля (читать `archi2likec4/config.py` для полного списка полей)
- [x] Обновить `MockBuilt` в `tests/helpers.py` — убедиться что все поля `BuildResult` покрыты дефолтами (читать `archi2likec4/builders/__init__.py` после Task 2)
- [x] Найти ad-hoc патчинг в тестах (например `config.language = 'en'` в `test_i18n.py`) — заменить на `MockConfig(language='en')`
- [x] В `pyproject.toml` поднять coverage gate: изменить `--cov-fail-under=80` → `--cov-fail-under=85`
- [x] Add/update tests: прогнать весь suite и убедиться что coverage ≥ 85%; если нет — добавить тесты для непокрытых путей
- [x] Mark completed

---

### Task 6: Cleanup, Documentation, Git Hygiene, and Roadmap
Финальная зачистка: удалить мусор, переместить diagnostic скрипты, актуализировать документацию, создать roadmap, выпустить версию 1.1.0.
- [ ] Удалить `convert.py` (6 строк — дублирует console_scripts entrypoint `archi2likec4 = "archi2likec4.pipeline:main"`)
- [ ] Создать директорию `tools/`; переместить туда `diag_dupes.py`, `diag_orphan_subsystems.py`, `diag_targets.py`, `diag_views.py`, `stats.py`; исправить в каждом `sys.path.insert(...)` на корректный import пакета
- [ ] Удалить `NOTES.md` из git tracking: `git rm NOTES.md`; добавить `NOTES.md` в `.gitignore`
- [ ] Git cleanup: удалить локальную ветку `fix/p1-release-blockers` (уже влита в main): `git branch -d fix/p1-release-blockers`; проверить ветку `v2-backlog` на наличие полезных изменений, затем удалить: `git branch -d v2-backlog`
- [ ] Удалить устаревшие артефакты сборки: `rm -rf build/ output_backup/ output_before_promote/` (если существуют)
- [ ] Обновить `README.md`: актуализировать счётчик тестов, добавить описание новой структуры пакетов `builders/` и `generators/` в секцию architecture
- [ ] Обновить `CONTRIBUTING.md`: добавить в code structure описание `builders/`, `generators/`, `templates/`, `audit_data.py`, `i18n.py`
- [ ] Обновить `CHANGELOG.md`: добавить секцию `## [Unreleased]` с описанием рефакторинга (module split, lint uplift, template extraction, test gap fill)
- [ ] Обновить `.archi2likec4.example.yaml`: заменить bank-specific имена (EFS, EFS_PLT, ASBT, Korona, SAP_HCM) на generic (crm, erp, payment_gateway, core_banking)
- [ ] В `pyproject.toml` и `archi2likec4/__init__.py`: bump version `1.0.0` → `1.1.0`
- [ ] Создать `docs/ROADMAP.md` с секциями: PyPI publish workflow, Pydantic config validation, plugin architecture, JSON/YAML output, CI auto-generation, Web UI SSE/diff/dark-theme
- [ ] Add/update tests: убедиться что перемещение diag-скриптов не сломало imports; прогнать `tests/test_cli.py` — должен быть зелёным
- [ ] Mark completed
