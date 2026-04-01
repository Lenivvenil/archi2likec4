# Plan: April 2026 Codebase Audit

## Overview
Свежий аудит зрелой кодовой базы (1027 тестов, 96.79% coverage, 0 ruff/mypy errors) выявил новые зоны роста: CI/CD не блокирует security findings, тестовые файлы перегружены (до 3237 строк), web.py содержит 377-строчную функцию с 15 routes inline, и отсутствует часть OSS-документации.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: CI/CD Hardening

Усилить CI pipeline: сделать security scans blocking, добавить Dependabot, настроить upload coverage.

- [x] В `.github/workflows/ci.yml`: убрать `continue-on-error: true` у шагов bandit и pip-audit — security findings должны блокировать pipeline
- [x] Создать `.github/dependabot.yml` с конфигурацией для pip (weekly schedule, auto-merge patch updates)
- [x] В `.github/workflows/ci.yml`: после шага pytest добавить шаг upload coverage (codecov/codecov-action или артефакт `--cov-report=xml`)
- [x] В `pyproject.toml`: добавить `--cov-report=xml:coverage.xml` в pytest addopts для генерации XML-отчёта
- [x] Add/update tests for the above changes (N/A — CI/CD YAML configs, no unit tests applicable)
- [x] Mark completed

---

### Task 2: Fill Test Coverage Gaps

Добавить тесты для непокрытых утилит и edge cases, чтобы закрыть пробелы до 98%+.

- [x] В `tests/test_generators.py`: добавить тесты для `truncate_desc()` из `generators/_common.py` — пустая строка, строка длиннее _MAX_DESC_LEN, строка с newlines, строка ровно на границе
- [x] В `tests/test_generators.py`: добавить тесты для `render_metadata()` из `generators/_common.py` — пустой metadata dict, metadata с несколькими полями, metadata с None значениями
- [x] В `tests/test_builders.py`: добавить тесты для `build_comp_c4_path()` из `builders/_paths.py` — простой путь, вложенный путь, путь с promoted parent
- [x] В `tests/test_builders.py`: добавить тесты для `build_deployment_path_index()` из `builders/_paths.py` — пустой список nodes, nodes с вложенной иерархией
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 3: Split Large Test Files

Разбить 3 крупнейших тестовых файла на логические модули для улучшения навигации и параллельного запуска.

- [x] Разбить `tests/test_builders.py` (3237 строк) на: `test_builders_systems.py`, `test_builders_domains.py`, `test_builders_deployment.py`, `test_builders_data.py`, `test_builders_integrations.py`, `test_builders_paths.py` — по одному на builder-модуль
- [x] Разбить `tests/test_parsers.py` (1967 строк) на: `test_parsers_components.py`, `test_parsers_relationships.py`, `test_parsers_views.py`, `test_parsers_deployment.py` — по логическим блокам parse-функций
- [x] Разбить `tests/test_generators.py` (1725 строк) на: `test_generators_spec.py`, `test_generators_views.py`, `test_generators_domains.py`, `test_generators_deployment.py`, `test_generators_entities.py` — по generator-модулям
- [x] Убедиться что общие fixtures/helpers вынесены в `tests/conftest.py` или остались в `tests/helpers.py`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 4: Extract Web Routes from create_app()

Разбить монолитную `create_app()` (377 строк, 15 route handlers) в `web.py` на логические модули.

- [x] Создать `archi2likec4/web_routes.py` (или Flask Blueprint): перенести route handlers из `create_app()` — dashboard, incident detail, remediations, hierarchy, assign-domain, promote-system, health
- [x] В `archi2likec4/web.py`: оставить `create_app()` как тонкий orchestrator — создание app, регистрация blueprint, CSRF middleware, error handlers
- [x] Перенести CSRF-логику (`_check_csrf`, `_safe_redirect`) в отдельный модуль или оставить в web.py как middleware
- [x] Обновить `tests/test_web.py` — импорты и fixtures должны работать с новой структурой
- [x] В `pyproject.toml`: добавить mypy override для `archi2likec4.web_routes` с `disallow_untyped_defs = false` (Flask routes)
- [x] Add/update tests for the above changes (existing tests pass without modification — 56/56)
- [x] Mark completed

---

### Task 5: Hardcoded Values and OSS Documentation

Параметризовать оставшиеся hardcoded значения и добавить OSS-документацию.

- [x] В `archi2likec4/builders/systems.py`: заменить hardcoded `'!РАЗБОР'` на `config.trash_folder` с дефолтом `'!РАЗБОР'`; добавить поле `trash_folder: str = '!РАЗБОР'` в `ConvertConfig` (`config.py`)
- [x] В `pyproject.toml`: добавить upper bounds для зависимостей: `defusedxml>=0.7,<1.0`, `flask>=2.3,<4.0`, `pyyaml>=6.0,<7.0`
- [x] Создать `SECURITY.md` с политикой responsible disclosure (GitHub Security Advisories)
- [x] В `pyproject.toml`: добавить classifiers `Environment :: Console` и `Topic :: Software Development :: Code Generators`
- [x] Add/update tests for the above changes (тест для trash_folder config field + builder behaviour)
- [x] Mark completed
