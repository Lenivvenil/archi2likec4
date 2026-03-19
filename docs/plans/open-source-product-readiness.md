# Plan: Open-Source Product Readiness

## Overview

Цикл улучшений для превращения archi2likec4 в полноценную open-source библиотеку: единая версия через `importlib.metadata`, публичный `convert()` API без `sys.exit()`, активация `ParseError`/`ValidationError` (определены но не поднимаются), вынесение захардкоженных данных в `ConvertConfig`, удаление мёртвого кода и поднятие test coverage выше 85%.

## Validation Commands
- `ruff check archi2likec4/ tests/`
- `uv run pytest tests/ -v --tb=short`
- `uv run mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Version Single Source of Truth + CLI --version

Проблема: `pyproject.toml` и `archi2likec4/__init__.py` содержат разные версии (`version = "..."` и `__version__ = '...'`). CLI не имеет флага `--version`. Субкоманда `web` не видна в `--help`.

- [x] `pyproject.toml`: обновить `version` до целевой (следующий semver относительно текущего `__version__`)
- [x] `archi2likec4/__init__.py`: заменить хардкоженный `__version__ = '...'` на динамическое чтение через `importlib.metadata.version('archi2likec4')` с fallback на целевую версию
- [x] `archi2likec4/pipeline.py`: добавить `from . import __version__` в начало `main()`, добавить `parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')`, добавить `epilog` с описанием `web` субкоманды и использовать `formatter_class=argparse.RawDescriptionHelpFormatter`
- [x] `archi2likec4/__init__.py`: добавить все публичные имена (включая `convert`, `ConvertResult` если ещё нет) в `__all__`
- [x] Add/update tests: `tests/test_cli.py` — `test_version_flag` (SystemExit code 0), `test_help_shows_web` (проверить 'web' в stdout)
- [x] Mark completed

---

### Task 2: Public Library API — convert() + ConvertResult

Проблема: `main()` / `run_pipeline()` вызывает `sys.exit()` при ошибках — нельзя использовать как библиотеку. Нет типизированного возвращаемого значения.

- [x] `archi2likec4/pipeline.py`: добавить `@dataclass ConvertResult` с полями `systems_count: int`, `integrations_count: int`, `files_written: int`, `warnings: int`, `output_dir: Path`
- [x] `archi2likec4/pipeline.py`: добавить публичную функцию `convert(model_root, output_dir='output', *, config=None, config_path=None, dry_run=False) -> ConvertResult`. Функция НЕ вызывает `sys.exit()`. При ошибках бросает `FileNotFoundError`, `ConfigError`, `ParseError`, `ValidationError`. Вызывает `_parse`, `_build`, `_validate`, при `dry_run=False` — `_generate` и `_sync_output`
- [x] `archi2likec4/pipeline.py`: убедиться, что `_generate()` возвращает `int` (количество записанных файлов), а не `None`
- [x] `archi2likec4/pipeline.py`: рефакторировать `main()` в тонкую обёртку вокруг `convert()`: `main()` только парсит аргументы, вызывает `convert()`, перехватывает исключения и вызывает `sys.exit()` с нужным кодом (ValidationError/unexpected → 1, FileNotFoundError/ParseError/ConfigError → 2)
- [x] `archi2likec4/__init__.py`: экспортировать `convert` и `ConvertResult`; оставить `run_pipeline` как backward-compat alias для `main`
- [x] Add/update tests: `tests/test_api.py` — новый файл: `TestConvertReturnsResult` (success, dry-run, без config), `TestConvertRaisesOnBadInput` (missing root, ValidationError, strict warnings, ConfigError, ParseError)
- [x] Mark completed

---

### Task 3: Activate ParseError and ValidationError

Проблема: `ParseError` и `ValidationError` определены в `archi2likec4/exceptions.py` но нигде не поднимаются. В `parsers.py` 10+ мест с `except ET.ParseError: parse_errors += 1` молча накапливают ошибки без эффекта.

- [ ] `archi2likec4/parsers.py`: добавить `from .exceptions import ParseError`. В каждой `parse_*` функции после основного цикла добавить: `if not results and parse_errors > 0: raise ParseError(f'All {parse_errors} <тип> XML file(s) in {dir} failed to parse')`. Функции: `parse_application_components`, `parse_application_interfaces`, `parse_data_objects`, `parse_application_functions`, `parse_technology_elements`, `parse_relationships`
- [ ] `archi2likec4/pipeline.py`: в `convert()` после `_validate()` добавить проверки: если `gate_errors > 0` — `raise ValidationError('Quality gates failed: ...')`. Если `config.strict and gate_warnings > 0` — `raise ValidationError('strict mode: ...')`
- [ ] Add/update tests: `tests/test_parsers.py` — класс `TestParserErrorPaths`: по одному тесту `*_malformed_raises` (все файлы невалидны → `ParseError`) и `*_partial_malformed_ok` (часть невалидна → возвращает валидные) для каждого `parse_*`. Также `test_is_in_trash_malformed_folder_xml` и `test_detect_special_folder_malformed_folder_xml`
- [ ] Mark completed

---

### Task 4: Externalize Hardcoded Bank-Specific Data

Проблема: Захардкоженные данные (`_PROP_MAP`, `_STANDARD_KEYS`, `_SYNC_PROTECTED_TOP`, `_SYNC_PROTECTED_PATHS`, `DOMAIN_RENAMES`, `EXTRA_DOMAIN_PATTERNS`, `PROMOTE_CHILDREN`) мешают использовать конвертер в других организациях.

**4a. Удалить мёртвый код:**
- [ ] `archi2likec4/models.py`: удалить константы `DOMAIN_RENAMES`, `EXTRA_DOMAIN_PATTERNS`, `PROMOTE_CHILDREN` — они не используются (config.py имеет свои `_DEFAULT_*`)
- [ ] `archi2likec4/parsers.py`: убрать `DOMAIN_RENAMES` из импорта; заменить `domain_renames if domain_renames is not None else DOMAIN_RENAMES` → `domain_renames or {}`

**4b. Сделать metadata mapping конфигурируемым:**
- [ ] `archi2likec4/models.py`: переименовать `_PROP_MAP` → `DEFAULT_PROP_MAP`, `_STANDARD_KEYS` → `DEFAULT_STANDARD_KEYS` (публичные константы)
- [ ] `archi2likec4/config.py`: импортировать `DEFAULT_PROP_MAP`, `DEFAULT_STANDARD_KEYS` из `models`; добавить в `ConvertConfig` поля `property_map: dict[str, str]` и `standard_keys: list[str]` с дефолтами через `field(default_factory=lambda: dict(DEFAULT_PROP_MAP))` / `field(default_factory=lambda: list(DEFAULT_STANDARD_KEYS))`; добавить парсинг из YAML
- [ ] `archi2likec4/utils.py`: обновить импорты на `DEFAULT_PROP_MAP`/`DEFAULT_STANDARD_KEYS`; добавить опциональные параметры `prop_map=None, standard_keys=None` в `build_metadata()`, использовать их вместо глобальных констант
- [ ] `archi2likec4/builders/systems.py` и другие вызывающие `build_metadata()`: передавать `config.property_map` и `config.standard_keys`

**4c. Вынести sync protected paths:**
- [ ] `archi2likec4/config.py`: добавить в `ConvertConfig` поля `sync_protected_top: frozenset[str]` и `sync_protected_paths: frozenset[str]` с `field(default_factory=frozenset)`; добавить парсинг из YAML
- [ ] `archi2likec4/pipeline.py`: удалить константы `_SYNC_PROTECTED_TOP` и `_SYNC_PROTECTED_PATHS`; в `_sync_output()` заменить обращения к этим константам на `config.sync_protected_top` и `config.sync_protected_paths`

- [ ] Add/update tests: `tests/test_config.py` — парсинг `property_map`, `standard_keys`, `sync_protected_top`, `sync_protected_paths` из YAML. `tests/test_utils.py` — тест `build_metadata` с кастомными `prop_map`/`standard_keys`
- [ ] Mark completed

---

### Task 5: Test Coverage Boost ≥ 85%

Проблема: `parsers.py` имеет низкое покрытие (75-80%) из-за непокрытых `except ET.ParseError` обработчиков. После Tasks 1-4 могли появиться непокрытые ветки.

- [ ] Запустить `uv run pytest tests/ --cov=archi2likec4 --cov-report=term-missing` и найти непокрытые строки в `parsers.py` и `pipeline.py`
- [ ] `tests/test_parsers.py`: если `TestParserErrorPaths` не был добавлен в Task 3, добавить его здесь. Приоритет: `_find_parent_component` с malformed XML, `_find_functional_areas_dir` с malformed folder.xml, `parse_domain_mapping` когда `functional_areas` не найдена
- [ ] `tests/test_cli.py`: покрыть оставшиеся ветки `main()`: `test_config_error_exit_2` (load_config raises FileNotFoundError → exit 2), `test_model_root_not_found_exit_2`, `test_parse_error_exit_2`, `test_unexpected_error_exit_1`
- [ ] `tests/test_api.py`: убедиться что все ветки `convert()` покрыты — sync_target путь, dry_run путь
- [ ] Проверить финальный coverage: `uv run pytest tests/ -q --tb=short` — последняя строка должна содержать `Total coverage: ≥85%`
- [ ] Mark completed

---

### Task 6: Cleanup + CHANGELOG + Documentation

Финальная сборка: документация, changelog, README.

- [ ] `CHANGELOG.md`: добавить секцию `[X.Y.Z] — <дата>` с подсекциями Added / Changed / Removed, отражающими Tasks 1-5
- [ ] `README.md`: добавить или обновить секцию "Library Usage" с примером `from archi2likec4 import convert, ConvertConfig, ConvertResult` и кодом вызова; перечислить бросаемые исключения
- [ ] `CLAUDE.md`: обновить строку `pipeline.py` в таблице Key Files — добавить `convert()`, `ConvertResult` в описание
- [ ] Финальный прогон всех validation commands: `ruff check archi2likec4/ tests/`, `uv run pytest tests/ -v --tb=short`, `uv run mypy archi2likec4/ --ignore-missing-imports`
- [ ] Финальная smoke-проверка: `uv run python -c "from archi2likec4 import convert, ConvertResult, __version__; print(__version__)"` — печатает целевую версию
- [ ] Mark completed
