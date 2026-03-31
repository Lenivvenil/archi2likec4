# Plan: Close issue 35 and coverage uplift

## Overview
Закрыть последний открытый issue #35 (PLR0913 — фактически решён) и поднять тестовое покрытие модулей `parsers.py` (82%) и `pipeline.py` (84%) до ≥90%. Также улучшить покрытие `builders/systems.py` (87%) и `builders/data.py` (88%). Цель — довести общее покрытие до 93%+.

## Validation Commands
- `python -m pytest tests/ -v --tb=short`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`
- `python -m pytest tests/ --cov=archi2likec4 --cov-report=term --cov-fail-under=92`

### Task 1: Close issue 35 and verify PLR0913 is resolved
Закрыть issue #35 на GitHub. Проверить, что `ruff check --select PLR0913` не находит нарушений. Единственный `noqa: PLR0913` в `views.py:577` на factory-функции `build_view_context` — это осознанное решение (factory создаёт dataclass из raw-данных).
- [ ] Run `ruff check archi2likec4/ --select PLR0913` and confirm zero violations
- [ ] Close GitHub issue #35 with comment explaining resolution
- [ ] Mark completed

### Task 2: Improve parsers.py test coverage to 90%+
`parsers.py` — 82% (557 statements, 102 uncovered). Непокрытые строки включают edge cases парсинга XML: пустые/отсутствующие атрибуты, nested elements, специфические ArchiMate типы.
- [ ] Read uncovered lines in `archi2likec4/parsers.py` (lines 34-35, 92-114, 151-154, 237-291, 305-326, 366-394, 441-496, 525-555, 592-636, 659-672, 700-732, 767-808)
- [ ] Add tests in `tests/test_parsers.py` covering XML edge cases: missing attributes, empty elements, unknown element types
- [ ] Add tests for deployment parsing edge cases (lines 767-808)
- [ ] Add tests for integration parsing edge cases (lines 592-636)
- [ ] Verify `parsers.py` coverage ≥ 90% with `python -m pytest tests/test_parsers*.py --cov=archi2likec4.parsers --cov-report=term`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

### Task 3: Improve pipeline.py test coverage to 90%+
`pipeline.py` — 84% (490 statements, 78 uncovered). Непокрытые строки — CLI entry point (`main()`), error handling paths, file I/O в `_generate()`.
- [ ] Read uncovered lines in `archi2likec4/pipeline.py` (lines 137, 201, 238-281, 291-296, 325-326, 387-416, 449-490, 510-578, 624-630, 646-658, 688-749, 919-962)
- [ ] Add tests for `_generate()` error paths and edge cases in `tests/test_pipeline.py`
- [ ] Add tests for `main()` CLI entry point using mock args and monkeypatch
- [ ] Add tests for config validation and error handling paths
- [ ] Verify `pipeline.py` coverage ≥ 90% with `python -m pytest tests/test_pipeline*.py --cov=archi2likec4.pipeline --cov-report=term`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

### Task 4: Improve builders coverage to 90%+
`builders/systems.py` — 87% (32 uncovered), `builders/data.py` — 88% (10 uncovered). Непокрытые строки — edge cases в system hierarchy building и data entity detection.
- [ ] Read uncovered lines in `archi2likec4/builders/systems.py` (lines 40, 70-72, 95-96, 140-141, 317-318, 328, 377, 387-400, 441-470)
- [ ] Read uncovered lines in `archi2likec4/builders/data.py` (lines 61-69, 76, 90, 135, 140)
- [ ] Add tests for systems.py edge cases: subsystem extraction with missing parents, function attachment with unknown systems
- [ ] Add tests for data.py edge cases: dataStore detection fallbacks, missing entity links
- [ ] Verify both modules ≥ 90% coverage
- [ ] Add/update tests for the above changes
- [ ] Mark completed

### Task 5: Verify overall coverage and cleanup
Финальная проверка: общее покрытие ≥ 92%, все validation commands проходят, нет stale noqa/type:ignore.
- [ ] Run full test suite with coverage: `python -m pytest tests/ --cov=archi2likec4 --cov-report=term --cov-fail-under=92`
- [ ] Run `ruff check archi2likec4/ tests/` — confirm zero violations
- [ ] Run `mypy archi2likec4/ --ignore-missing-imports` — confirm zero errors
- [ ] Verify no stale `noqa` comments (each should still suppress a real violation)
- [ ] Add/update tests for the above changes
- [ ] Mark completed
