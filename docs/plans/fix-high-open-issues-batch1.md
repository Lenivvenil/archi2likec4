# Plan: Fix HIGH Open Issues — Batch 1 (Type Safety, CSRF, Config)

## Overview
Закрываем четыре HIGH open issue: типизация audit_data.py (#5), CSRF-токены в web UI (#8),
захардкоженный 'prod' в deployment topology (#14), и сужение mypy ignore_missing_imports (#28).
В рабочей директории уже есть незакоммиченные изменения для #5, #14 и #28 — нужно завершить #8 и закоммитить всё.

## Validation Commands
- `python -m pytest tests/ -v --tb=short --cov=archi2likec4 --cov-fail-under=85`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Verify and commit type safety fixes (#5, #14, #28)

Незакоммиченные изменения для #5, #14, #28 уже готовы — верифицируем и коммитим.

- [x] Проверить `archi2likec4/audit_data.py`: нет `object` в сигнатуре `compute_audit_incidents()`, нет `getattr()` и `# type: ignore`, импорты через `TYPE_CHECKING`
- [x] Проверить `archi2likec4/config.py`: поле `deployment_env: str = 'prod'` в `ConvertConfig`, обработка в `load_config()`, добавлено в `_KNOWN_KEYS`
- [x] Проверить `archi2likec4/generators/views.py`: параметр `deployment_env: str = 'prod'` в `generate_solution_views()`, используется при генерации
- [x] Проверить `archi2likec4/pipeline.py`: `config.deployment_env` передаётся в `generate_deployment_c4()` и `generate_solution_views()`
- [x] Проверить `pyproject.toml`: `ignore_missing_imports = true` только в `[[tool.mypy.overrides]]` для `flask`, `yaml`, `defusedxml` — не глобально
- [x] Убрать мёртвый `import secrets` из `archi2likec4/web.py` (будет добавлен правильно в Task 2)
- [x] `ruff check` и `mypy` проходят без ошибок
- [x] Прогнать `pytest`; если тесты падают — исправить
- [x] Закоммитить: `fix: type safety in audit_data, configurable deployment_env, narrow mypy overrides (#5, #14, #28)`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 2: Implement CSRF token protection (#8)

Добавляем double-submit cookie CSRF защиту без внешних зависимостей.
Паттерн: при GET-запросе генерируем `csrf_token` через `secrets.token_hex(32)`, кладём в cookie
и инжектим в формы через context_processor. При POST — сверяем cookie с hidden input.

- [x] В `archi2likec4/web.py`: добавить `import secrets` (строка 1 импортов)
- [x] В `archi2likec4/web.py`: добавить `app.secret_key = secrets.token_hex(32)` сразу после создания `app`
- [x] В `archi2likec4/web.py`: добавить `@app.context_processor` — функция `inject_csrf()` которая при GET создаёт `secrets.token_hex(32)`, ставит в `session['_csrf']` и возвращает `{'csrf_token': session['_csrf']}`
- [x] В `archi2likec4/web.py`: переписать `_csrf_check()` — на POST сверять `request.form.get('_csrf_token')` с `session.get('_csrf')`; если не совпадает — `abort(403)`; оставить fallback Origin/Referer проверку как вторичный слой
- [x] В `archi2likec4/templates/base.html`: создать макрос или Jinja2 helper `{{ csrf_field() }}` как `<input type="hidden" name="_csrf_token" value="{{ csrf_token }}">`
- [x] В `archi2likec4/templates/detail.html`: добавить `{{ csrf_field() }}` во все 4 формы
- [x] В `archi2likec4/templates/dashboard.html`: добавить `{{ csrf_field() }}` во все 4 формы
- [x] В `archi2likec4/templates/remediations.html`: добавить `{{ csrf_field() }}` во все 6 форм (строки ~21, 45, 70, 94, 118 + новые)
- [x] Закоммитить: `fix: add session-based CSRF token protection to web UI (#8)`
- [x] Add/update tests for the above changes (`tests/test_web.py`: тест что POST без токена возвращает 403, с токеном — 302)
- [x] Mark completed
