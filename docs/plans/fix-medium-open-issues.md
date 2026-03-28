# Plan: Fix MEDIUM Open Issues (#19, #27, #29)

## Overview
Закрываем три MEDIUM open issue: захардкоженные русские regex-паттерны (#19), 6 модулей
с отключённой C901 complexity (#27), и захардкоженные цвета/формы/теги в spec.py (#29).
Все три — tech-debt и code quality без breaking changes в API.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Move hardcoded Russian regex patterns to config (#19)

В `parsers.py` есть regex паттерны специфичные для русского языка — выносим в конфиг.

- [x] Найти все `re.compile(...)` паттерны с русскими строками в `archi2likec4/parsers.py`
- [x] В `archi2likec4/config.py`: добавить поля в `ConvertConfig` для каждого русскоязычного паттерна (например `integration_pattern: str`, `domain_pattern: str`) с дефолтными значениями равными текущим хардкодам
- [x] Добавить обработку новых полей в `load_config()` в `archi2likec4/config.py`
- [x] В `archi2likec4/parsers.py`: заменить хардкод на обращение к конфигу; если parsers не имеют доступа к config — передавать паттерны как параметры в функции `parse_*()`
- [x] Обновить сигнатуры `parse_systems()`, `parse_subdomains()` и т.д. если нужно
- [x] В `tests/helpers.py`: если `MockConfig` не имеет новых полей — добавить с теми же дефолтами
- [x] Закоммитить: `refactor: move hardcoded Russian regex patterns to config (#19)`
- [x] Add/update tests for the above changes (`tests/test_config.py`: тест загрузки паттернов из YAML; `tests/test_parsers.py`: тест с кастомным паттерном)
- [x] Mark completed

---

### Task 2: Reduce C901 noqa suppressions (#27)

6 из 12 модулей используют `# noqa: C901` — анализируем каждый и рефакторим где возможно.

- [ ] Найти все `# noqa: C901` в `archi2likec4/` через grep
- [ ] Для каждого: оценить сложность функции и решить — рефакторить (extract helper) или обосновать оставить
- [ ] В `archi2likec4/parsers.py`: если есть C901 функции с явными ветками — извлечь хелперы (target: убрать хотя бы 2 из 6 suppressions)
- [ ] В `archi2likec4/builders/`: аналогично
- [ ] Для оставшихся C901 которые нельзя убрать без breaking change — добавить комментарий объясняющий почему (TODO или justified complexity)
- [ ] Обновить `pyproject.toml` если нужно скорректировать лимиты
- [ ] Закоммитить: `refactor: reduce C901 noqa suppressions, extract helpers in parsers/builders (#27)`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

---

### Task 3: Move hardcoded spec colors/shapes/tags to config (#29)

В `spec.py` цвета, формы и теги хардкожены — делаем конфигурируемыми.

- [ ] Найти все хардкоды в `archi2likec4/generators/spec.py` — цвета `color =`, формы `shape =`, теги `#tag`
- [ ] В `archi2likec4/config.py`: добавить опциональные поля `spec_colors: dict[str, str]`, `spec_shapes: dict[str, str]`, `spec_tags: list[str]` с дефолтами из текущих хардкодов
- [ ] Добавить обработку в `load_config()` в `archi2likec4/config.py`
- [ ] В `archi2likec4/generators/spec.py`: функция `generate_spec()` принимает `config: ConvertConfig` и использует `config.spec_colors`, `config.spec_shapes`, `config.spec_tags`
- [ ] В `archi2likec4/pipeline.py`: убедиться что `config` передаётся в `generate_spec()`
- [ ] Добавить `'spec_colors', 'spec_shapes', 'spec_tags'` в `_KNOWN_KEYS` в `config.py`
- [ ] Закоммитить: `feat: make spec.py colors, shapes, tags configurable (#29)`
- [ ] Add/update tests for the above changes (`tests/test_generators.py`: тест с кастомными цветами/формами; `tests/test_config.py`: тест загрузки spec настроек)
- [ ] Mark completed
