# Plan: Final Quality Audit and New Issue Discovery

## Overview
Финальный прогон всех инструментов качества после закрытия открытых issues. Цель — найти новые
проблемы, которые не попали в предыдущий аудит, и зафиксировать их как GitHub issues для
следующей итерации. Результат: актуальный backlog с приоритетами.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`
- `pip-audit`
- `bandit -r archi2likec4/ -ll`

---

### Task 1: Run static analysis and collect findings

Полный прогон всех статических анализаторов — собираем результаты.

- [x] Прогнать `mypy archi2likec4/ --ignore-missing-imports --strict` — зафиксировать все новые ошибки типов
- [x] Прогнать `ruff check archi2likec4/ tests/ --select=ALL --ignore=D,ANN,ERA,FBT,S101` — расширенный набор правил для выявления скрытых проблем
- [x] Прогнать `bandit -r archi2likec4/ -ll -f json > /tmp/bandit_report.json` — security issues
- [x] Прогнать `pip-audit` — известные CVE в зависимостях
- [x] Прогнать `vulture archi2likec4/` (если установлен) — dead code
- [x] Записать все findings в `docs/plans/quality-audit-findings.md` (временный файл для анализа)
- [x] Add/update tests for the above changes (audit-only task, no code changes)
- [x] Mark completed

---

### Task 2: Assess test quality and coverage gaps

Смотрим что не покрыто тестами и где тесты ненадёжны.

- [ ] Прогнать `pytest --cov=archi2likec4 --cov-report=html` — открыть отчёт, найти модули с coverage < 80%
- [ ] Проверить `tests/test_web.py` — покрыты ли все 10 POST routes, edge cases (missing form data, invalid redirect)
- [ ] Проверить `tests/test_config.py` — покрыты ли все новые поля добавленные в ходе рефакторинга
- [ ] Проверить `tests/test_pipeline_e2e.py` — есть ли тест с конфигом `deployment_env`
- [ ] Найти `# type: ignore` и `# noqa` в тестах — каждый такой случай потенциальная проблема
- [ ] Записать gaps в `docs/plans/quality-audit-findings.md`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

---

### Task 3: Manual code review — architecture and API surface

Ручной ревью ключевых модулей для обнаружения архитектурных проблем.

- [ ] `archi2likec4/pipeline.py`: проверить что все публичные функции имеют полные type annotations; нет глобального state; все параметры `convert()` задокументированы
- [ ] `archi2likec4/parsers.py`: проверить обработку всех edge cases XML (пустые теги, отсутствующие атрибуты, unicode в name)
- [ ] `archi2likec4/web.py`: проверить все HTTP ответы — правильные status codes; нет утечки путей файловой системы в ошибках
- [ ] `archi2likec4/builders/`: проверить что все builder функции детерминированы (один и тот же input → одинаковый output)
- [ ] `archi2likec4/models.py`: проверить что все dataclass поля имеют типы; нет мутабельных дефолтов
- [ ] Записать findings в `docs/plans/quality-audit-findings.md`
- [ ] Add/update tests for the above changes
- [ ] Mark completed

---

### Task 4: File new GitHub issues from findings

Фиксируем новые проблемы как GitHub issues с правильными метками и приоритетами.

- [ ] Прочитать `docs/plans/quality-audit-findings.md`
- [ ] Для каждого finding: определить приоритет (CRITICAL/HIGH/MEDIUM/LOW) и категорию (security, architecture, code-quality, tech-debt, test-quality)
- [ ] Создать GitHub issue через `gh issue create` для каждого finding с полями: title `[PRIORITY] краткое название`, body с разделами `## Проблема`, `## Решение`, `## Файлы`, `## Трудозатраты`, соответствующие labels
- [ ] Убедиться что нет дублей с уже открытыми issues
- [ ] Закрыть или обновить устаревшие issues если картина изменилась
- [ ] Удалить временный файл `docs/plans/quality-audit-findings.md`
- [ ] Mark completed

---

### Task 5: Update MEMORY.md and project documentation

Синхронизируем состояние проекта с документацией.

- [ ] Обновить `/Users/ivankuzmin/.claude/projects/-Users-ivankuzmin-Projects-archi2likec4/memory/MEMORY.md` — раздел "GitHub Issues — Open" актуальным списком
- [ ] Обновить раздел "Current State" в MEMORY.md — новое количество тестов и coverage
- [ ] Если `CLAUDE.md` устарел (новые файлы, изменённые сигнатуры) — обновить таблицу Key Files
- [ ] Прогнать финальный `pytest --cov-fail-under=85` — убедиться что coverage gate проходит
- [ ] Закоммитить все pending изменения документации: `docs: update project state and issue backlog`
- [ ] Add/update tests for the above changes
- [ ] Mark completed
