# Plan: Review Closed Issues

## Overview
Проверяем, что все 22 закрытых issue действительно исправлены в коде, а не просто закрыты.
Для каждого issue: читаем описание, находим соответствующий код, убеждаемся что fix есть, проверяем наличие тестов.
Если fix отсутствует или неполный — создаём новый issue с меткой `regression`.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Verify CRITICAL and HIGH fixes (#1, #6, #7)

Проверяем три самых важных закрытых issue — CRITICAL и HIGH приоритет.

- [x] Issue #1 (приватные функции между builder-подмодулями): проверить `archi2likec4/builders/`, что нет прямого импорта `_` функций между подмодулями; все публичные через `__init__.py`
- [x] Issue #6 (банко-специфичные дефолты в config.py и models.py): проверить, что `_DEFAULT_DOMAIN_RENAMES`, `_DEFAULT_EXTRA_DOMAIN_PATTERNS`, `_DEFAULT_PROMOTE_CHILDREN` помечены как bank-specific или вынесены из дефолтной конфигурации
- [x] Issue #7 (XXE через xml.etree.ElementTree): проверить `archi2likec4/parsers.py` — все `ET.parse()` заменены на `defusedxml`; проверить `pyproject.toml` что `defusedxml` в зависимостях
- [x] Для каждого: найти соответствующий тест в `tests/` который это покрывает
- [x] Если fix отсутствует — создать `gh issue create` с меткой `regression`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 2: Verify MEDIUM security and validation fixes (#15, #18, #21)

Проверяем безопасность: XSS, валидация входных данных.

- [x] Issue #21 (XSS в web.py): проверить `archi2likec4/web.py` — все места где `domain` подставляется в HTML ответы используют `html.escape()`
- [x] Issue #18 (пустой archi_id): проверить `archi2likec4/parsers.py` — после `.get('id', '')` есть проверка на пустую строку с `logger.warning` и skip; добавлены проверки для `parse_technology_elements` и `parse_location_elements` (regression fix)
- [x] Issue #15 (нет валидации c4_id): проверить что c4_id проходит через валидацию перед интерполяцией в `.c4` синтаксис (недопустимые символы, пустая строка)
- [x] Найти тесты для каждого случая в `tests/test_web.py`, `tests/test_parsers.py`
- [x] Если fix отсутствует — создать `gh issue create` с меткой `regression`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 3: Verify MEDIUM parsers and error handling fixes (#16, #17, #22)

Проверяем обработку ошибок в parsers и pipeline.

- [x] Issue #16 (непоследовательная обработка XML): проверить `archi2likec4/parsers.py` — все `ET.ParseError` ловятся через `logger.warning`, не пробрасываются raw
- [x] Issue #17 (_detect_special_folder сравнение с None): проверить что используется `is None` / `is not None`, не `== None`
- [x] Issue #22 (_load_data не ловит ParseError): проверить `archi2likec4/pipeline.py` — `_load_data()` ловит `ParseError` наряду с `ConfigError`
- [x] Найти тесты в `tests/test_parsers.py`, `tests/test_pipeline_e2e.py`
- [x] Если fix отсутствует — создать `gh issue create` с меткой `regression`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 4: Verify MEDIUM refactoring fixes (#9, #10, #11, #12, #13)

Проверяем рефакторинги: side effects, дублирование кода, иерархия исключений.

- [ ] Issue #9 (validate-фаза с побочными эффектами): проверить `archi2likec4/pipeline.py` — `_validate()` не пишет файлы, не мутирует `built`
- [ ] Issue #10 (config мутируется in-place): проверить `archi2likec4/pipeline.py` — `convert()` делает копию config или config immutable
- [ ] Issue #11 (нет BuildError/GenerateError): проверить `archi2likec4/exceptions.py` — есть ли `BuildError` и `GenerateError` в иерархии
- [ ] Issue #12 (дублирование truncate): проверить `archi2likec4/generators/_common.py` — есть `truncate_desc()` хелпер, используемый всеми генераторами
- [ ] Issue #13 (дублирование metadata): проверить `archi2likec4/generators/_common.py` — есть `render_metadata()` хелпер
- [ ] Если fix отсутствует — создать `gh issue create` с меткой `regression`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

---

### Task 5: Verify MEDIUM test and models fixes (#20, #23, #24)

Проверяем тесты и i18n.

- [ ] Issue #20 (приватные константы models.py в utils.py): проверить `archi2likec4/utils.py` — нет импортов `_` констант из `models.py`; если нужны константы — они публичные
- [ ] Issue #23 (i18n fallback непоследователен): проверить `archi2likec4/i18n.py` — `get_qa10_issue()` имеет fallback на `'ru'` как и остальные функции
- [ ] Issue #24 (MockConfig неполный): проверить `tests/helpers.py` — `MockConfig` содержит все поля из `ConvertConfig` включая `audit_suppress`, `audit_suppress_incidents`, `promote_warn_threshold`, `standard_keys`, `deployment_env`, `language`, и `promote_children`
- [ ] Если fix отсутствует — создать `gh issue create` с меткой `regression`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

---

### Task 6: Verify LOW fixes (#25, #26, #30, #31, #32)

Проверяем CI, документацию и cleanup.

- [ ] Issue #25 (нет кэширования в CI): проверить `.github/workflows/` — есть `cache: pip` в `actions/setup-python`
- [ ] Issue #26 (нет security-сканирования): проверить `.github/workflows/` — есть шаг с `pip-audit` и/или `bandit`
- [ ] Issue #30 (dead code, deferred imports): проверить `archi2likec4/pipeline.py` — нет неиспользуемых imports на верхнем уровне; deferred imports (`from . import X` внутри функций) оправданы
- [ ] Issue #31 (неточности в CONTRIBUTING.md): проверить `CONTRIBUTING.md` — описание templates совпадает с реальной структурой; view titles корректны
- [ ] Issue #32 (CI мелочи): проверить `.github/workflows/` — нет redundant flags; есть explicit `permissions:` блоки
- [ ] Add/update tests for the above changes
- [ ] Mark completed
