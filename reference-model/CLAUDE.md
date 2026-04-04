# demo-bank — Эталонная архитектурная модель LikeC4

Синтетический пример идеального архитектурного репозитория.
5 систем, 2 домена, 2 ЦОДа, 8 VM. Используй как образец при работе с asaka-architecture.

## Структура
- `specification.c4` — Kind'ы элементов, deployment-нод, тегов. Меняется редко.
- `infrastructure/` — Топология ЦОДов (зоны, кластеры, VM). Shared для всех систем.
- `domains/` — По одному файлу на бизнес-домен. Объявляет системы (имя + описание).
- `systems/{name}/model.c4` — Подсистемы через `extend` + исходящие интеграции.
- `systems/{name}/deployment.c4` — `extend` VM с instanceOf + deployment views.
- `views/` — Кросс-системные views (ландшафт, доменные контексты).

## Конвенции
- Идентификаторы: snake_case, без дефисов (LikeC4 парсит `-` как минус).
- Каждая система — ровно `model.c4` + `deployment.c4` в своей директории.
- Система объявляется в `domains/{domain}.c4`, детализируется через `extend` в `model.c4`.
- Исходящие связи — в `model.c4` SOURCE-системы.
- Deployment: `extend prod.{dc}.{zone}.{vm} { instanceOf {domain}.{system}.{component} }`.
- Deployment views: targeted includes по конкретным VM-путям, без exclude.

## Типовые операции

### Добавить систему
1. `domains/{domain}.c4` → добавить `system {id} '{Name}' { ... }`
2. Создать `systems/{id}/model.c4` → `extend {domain}.{id} { компоненты... }`
3. Создать `systems/{id}/deployment.c4` → `extend prod.{dc}.{zone}.{vm} { instanceOf ... }`

### Задеплоить компонент на VM
1. `systems/{name}/deployment.c4` → добавить `extend prod.{dc}.{zone}.{vm} { instanceOf ... }`
2. Добавить путь VM в deployment view

### Добавить интеграцию
1. `systems/{source}/model.c4` → `{source_fqn} -> {target_fqn} '{описание}'`

## Команды
```
npx likec4 serve          # Live preview
npx likec4 build          # Валидация
npx likec4 codegen json   # Экспорт модели
```
