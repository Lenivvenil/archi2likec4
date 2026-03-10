# archi2likec4 - Рабочие заметки

## Итерация 1: ApplicationComponent -> LikeC4

### Принцип работы с входными данными

**ВАЖНО: Папки coArchi — шум. Истина — в типе объекта и его имени.**

- Тип: `ApplicationComponent` (XML тег `archimate:ApplicationComponent`)
- Иерархия определяется ТОЧЕЧНОЙ НОТАЦИЕЙ в name:
  - `EFS` — система
  - `EFS.Client_Service` — подсистема EFS
  - Два уровня: Система и Система.Подсистема
- Папки в coArchi-репозитории — служебная структура, НЕ бизнес-иерархия

### Входные данные

**Источник:** все файлы `ApplicationComponent_*.xml` рекурсивно из
`architectural_repository/model/application/`

**XML-формат:**
```xml
<archimate:ApplicationComponent name="AD" id="id-xxx" documentation="описание">
  <properties key="CI" value="TBD"/>
  <properties key="Full name" value="Active directory"/>
  ...
  <profiles href="folder.xml#id-xxx"/>     <!-- ИГНОРИРУЕМ -->
</archimate:ApplicationComponent>
```

**Что берём:**
- `name` — имя (определяет иерархию через точку)
- `id` — идентификатор ArchiMate (сохраняем в metadata как archi_id)
- `documentation` — описание (опционально)
- `properties` — key/value пары → metadata блок (УНИФИЦИРОВАННЫЙ)

**Что НЕ берём:**
- `profiles` — специализации ArchiMate ("дурная иерархия, не тащи")
- Структуру папок coArchi
- Ключ `external` (мусор, 1 файл)
- Ключ `Client` (мусор, 1 файл)

**Статистика:** 397 файлов ApplicationComponent.
92.7% (368) не имеют properties вообще — заполняем TBD.

### Маппинг properties → metadata (УТВЕРЖДЁН)

| # | ArchiMate key | LikeC4 metadata key | Если пусто |
|---|---|---|---|
| 1 | `CI` | `ci` | `'TBD'` |
| 2 | `Full name` | `full_name` | = `name` элемента |
| 3 | `LC stage` | `lc_stage` | `'TBD'` |
| 4 | `Criticality` | `criticality` | `'TBD'` |
| 5 | `Target` | `target_state` | `'TBD'` |
| 6 | `Business owner dep` | `business_owner_dep` | `'TBD'` |
| 7 | `Dev team` | `dev_team` | `'TBD'` |
| 8 | `Architect full name` | `architect` | `'TBD'` |
| 9 | `IS-officer full name` | `is_officer` | `'TBD'` |
| 10 | `External/Internal` ИЛИ `placement` | `placement` | `'TBD'` |

- `target` — зарезервированное слово LikeC4 → переименовали в `target_state`
- `External/Internal` и `placement` — одно и то же, мержим в `placement`
- ВСЕ 10 ключей ОБЯЗАТЕЛЬНЫ в каждом элементе

### Особые папки внутри application_components

- `!РАЗБОР` — обрабатываем как обычные системы + тег `#to_review`
- `!External_services` — обрабатываем как обычные системы + тег `#external`
- `trash` — пропускаем (единственное исключение)

### LikeC4 DSL — синтаксис

**Цвета:** кастомные через `color name #hex`
- `archi-app #7EB8DA` — система (мягкий голубой ArchiMate)
- `archi-app-light #BDE0F0` — подсистема (ещё светлее)

**Element kinds:**
- `system` — информационная система
- `subsystem` — подсистема (вложена в system)

**Metadata:** блок `metadata { key 'value' }` внутри элемента

**Tags:** объявляются `tag name` в specification, используются как `#name`

**Views:** `view name { include * }`, `view name of element { include * }`

**Зарезервированные слова LikeC4 (нельзя в metadata/id):**
`target`, `component`, `specification`, `model`, `views`, `deployment`,
`extend`, `element`, `tag`, `include`, `exclude`, `style`, `color`,
`shape`, `technology`, `description`, `title`, `it`, `this` и др.

**Идентификаторы:** буквы, цифры, дефис, подчёркивание. БЕЗ точек.
Не может начинаться с цифры.

### Генерация идентификаторов (name → LikeC4 id)

- Транслитерация кириллицы
- Пробелы и спецсимволы → `_`
- Lowercase
- Точка разделяет систему и подсистему (не часть id)
- Если начинается с цифры → префикс `n`
- Коллизии → суффикс `_2`, `_3`

### Прототип

Рабочий прототип в `prototype/model.c4` — проверен через `likec4 serve`.

---

## Итерация 2: ApplicationInterface (API) → LikeC4

### Анализ исходных данных

**Источник:** 216 файлов `ApplicationInterface_*.xml` рекурсивно из
`architectural_repository/model/application/`

**Статистика:**
- 216 файлов
- 0% имеют properties (все пустые)
- ~38% имеют `documentation` (82 из 216) — обычно URL на API-документацию
- Именование через точку: `MLS.Backend.api`, `Confluence.API`, `AsiaExpress.soap_api`
- Протокол часто в имени: `.api`, `.rest`, `.rest_api`, `.soap_api`
- Есть русскоязычные имена-методы: «Загрузить файл», «Получить файл»

### Решение: НЕ создаём элементы, а обогащаем системы

**Обоснование (из AaC Book v3.0 и MVP Plan v3.0):**
В проекте AaC (Architecture as Code) на GitLab банка принято:
- API-контракты живут в YAML-спеках системы (`systems/{system}.yaml`, секция `api_contracts:`)
- LikeC4-модель содержит системы/контейнеры/связи, но НЕ детали API
- Дублирование API в C4-модели и YAML — антипаттерн

**Что делаем:**
1. Парсим ApplicationInterface → извлекаем name, documentation (URL), привязку к системе
2. На системе/подсистеме добавляем `link` с URL из documentation (если есть)
3. В metadata системы добавляем `api_interfaces` — перечень имён интерфейсов
4. Генерируем скелетон YAML спеки `systems/{system-id}.yaml` с `api_contracts:`
5. Переносим связи AppComponent↔AppInterface как интеграции C4-модели

**Что НЕ делаем:**
- Не создаём element kind `interface` в LikeC4
- Не загромождаем модель сотнями API-элементов
- Не дублируем данные между LikeC4 и YAML

### Структура выходных файлов (по AaC)

```
output/
  specification.c4      (element kinds, colors, tags)
  views.c4              (landscape + per-system views)
  relationships.c4      (интеграции между системами)
  systems/
    {system-id}.c4      (определение системы с подсистемами, links, metadata)
    {system-id}.yaml    (скелетон спеки с api_contracts)
```

LikeC4 читает все .c4 рекурсивно и мержит в единую модель.

### Формат link в LikeC4

```
system_name = system 'System Name' {
  link https://swagger.bank.uz/efs 'EFS API Documentation'
  link https://wsdl.bank.uz/efs/soap 'EFS SOAP WSDL'
  ...
}
```

### Привязка интерфейса к системе

1. Через CompositionRelationship (107): AppComponent владеет AppInterface — НАДЁЖНО
2. Через точечную нотацию в имени (fallback):
   - `MLS.Backend.api` → система `MLS` (или подсистема `MLS.Backend` если есть)
   - `Confluence.API` → система `Confluence`
   - `WAF` — без точки = неизвестно → лог + пропуск

### Интеграции (relationships → C4)

**Источники:**
- FlowRelationship: AppComponent → AppInterface (891) — потребитель → API провайдера
- FlowRelationship: AppComponent → AppComponent (2,076) — прямые интеграции
- ServingRelationship: AppComponent → AppInterface (52) — провайдер обслуживает через API

**Логика:**
- Source AppComponent → резолвим в систему/подсистему
- Target AppInterface → резолвим в систему-владельца интерфейса
- Если source_system ≠ target_system → интеграция: `source -> target 'name'`
- Одинаковые пары группируем в один relationship с кол-вом потоков

### Скелетон YAML системной спеки

```yaml
system:
  name: EFS
  id: efs
  domain: TBD
  team: TBD
  status: active

api_contracts:
  - name: 'EFS.Backend.api'
    type: rest
    documentation: 'https://swagger...'
    # TODO: fill method, path, auth, etc.
```

---

## Итерация 3: DataObject → dataEntity + реструктуризация

### Входные данные

- **DataObject:** 309 файлов в `application/` — Kafka-топики, структуры данных
- **AccessRelationship:** 316 — связи AppComponent → DataObject (кто обращается к данным)
- Качество данных низкое, но при миграции коней не меняем

### Решение

- `DataObject` → `dataEntity` (shape: storage/Document, цвет мягкий зелёный)
- `AccessRelationship` → `system -> dataEntity` (прямые стрелки, без именованного kind)
- `dataStore` (shape: cylinder) — определён в spec, но пустой (контейнерный уровень не велся)
- `persists` relationship kind — определён в spec для будущего использования

### Задел под канонику

Канонические сущности (Клиент, Счёт, Кредит...) не существуют в ArchiMate-модели.
Комментарий в `entities.c4` — TODO для будущей работы.
Паттерн: `dataStore -[persists]-> dataEntity` (когда появятся контейнеры).

### Реструктуризация output

```
output/
  spec.c4                 ← specification (корень)
  landscape.c4            ← интеграции + landscape view (корень)
  entities.c4             ← dataEntity + access relationships (корень)
  systems/
    {id}.c4 + {id}.yaml
  views/
    {id}_detail.c4        ← per-system detail views
    persistence-map.c4    ← Persistence Map view
```

Принцип: spec и ландшафт в корне, остальное в дочерних каталогах.
`domain/` не используется (занят под BIAN-нарезку сервисных доменов).

### Теги

- `#entity` — все dataEntity
- `#store` — все dataStore (будущее)

### Статистика

- 309 data entities, 241 уникальных access-связей system→entity
- Landscape view исключает dataEntity (`exclude element.kind = dataEntity`)
- Persistence Map показывает системы + сущности + стрелки доступа

---

## Итерация 4: Домены + domain-grouped views

### Домены из Archi view hierarchy

**Источник:** `diagrams/functional_areas/{domain}/` — папки содержат
ArchimateDiagramModel_*.xml, из которых извлекаем ссылки на ApplicationComponent.

**Алгоритм присвоения:**
1. Для каждого домена собираем все archi_id компонентов, упомянутых на его диаграммах
2. Система получает домен, у которого максимум «попаданий» (system + subsystems + extra_archi_ids)
3. Системы без попаданий идут в `unassigned`
4. Второй проход: pattern-matching по имени → EXTRA_DOMAIN_PATTERNS (platform, external_exchange)

**DOMAIN_RENAMES:** Переименование обнаруженных доменов:
- `banking_operations` → `products` / "Products"
- `customer_service_management` → `customer_service` / "Customer Service"

### Реструктуризация output (финальная)

```
output/
  specification.c4           — element kinds, colors, tags, relationship kinds
  relationships.c4           — cross-domain integrations (model block)
  entities.c4                — dataEntity + access relationships (model block)
  domains/
    {domain}.c4              — domain element with nested systems (model block)
  systems/
    {system}.c4              — extend block + detail view
  views/
    landscape.c4             — top-level landscape view
    persistence-map.c4       — data entity persistence map view
    domains/
      {domain}/
        functional.c4        — domain functional architecture view
        integration.c4       — domain integration architecture view
    solutions/
      {solution}.c4          — solution-level views
  scripts/
    federate.py              — federation script
    federation-registry.yaml — federation registry template
```

### Навигация (drill-down)

- `view index` → клик по домену → `view {domain}_functional of {domain}`
- Клик по системе → `view {sys}_detail of {domain}.{sys}`
- Detail view показывает subsystems и appFunctions

### LikeC4 predicate semantics (ВАЖНО)

**`include * where kind is system` в scoped view — ГЛОБАЛЬНЫЙ фильтр!**

В scoped view (`view X of element`) предикат `include * where kind is system`
выбирает ВСЕ системы из ВСЕЙ модели, а не только внутри scope. Это приводит
к отображению сотен элементов вместо ожидаемых десятков.

**Правильный подход:** `include *` + exclude-предикаты:
```
view channels_functional of channels {
  include *
  exclude * where kind is subsystem
  exclude * where kind is appFunction
  exclude * where kind is dataEntity
}
```

### Статистика

- 7 доменов (channels, products, customer_service, enterprise_governance, external_exchange, platform, unassigned)
- 243 системы, 142 подсистемы
- 272 уникальных system-to-system интеграций

---

## Итерация 5: ApplicationFunction + Solution Views

### ApplicationFunction → appFunction

**Источник:** 1658 файлов `ApplicationFunction_*.xml` рекурсивно из `application/`

**Привязка к родителю (P1 — relationship-first):**
1. Ищем Composition/Assignment/Realization relationship → ApplicationComponent (ПРИОРИТЕТ)
2. Fallback: filesystem hierarchy (ApplicationComponent_*.xml в том же каталоге)
3. Если ничего не нашли → orphan (не отображается)

**Почему relationship-first:**
В файловой системе coArchi ApplicationFunction может лежать в неправильной папке,
а ArchiMate-связи явно задают принадлежность. Relationship — source of truth.

### Solution Views

**Источник:** ArchimateDiagramModel_*.xml с именами:
- `functional_architecture.{solution}` / `fucntional_architecture.{solution}` (typo в модели)
- `integration_architecture.{solution}`
- Русские варианты: `Функциональная архитектура.{solution}` и т.д.

**Functional view:** показывает системы из диаграммы + children
- Для одной системы: scoped view (`of domain.system`)
- Для нескольких: explicit includes с `{path}.*`

**Integration view:** показывает системы + связи между ними
- Используются ФАКТИЧЕСКИЕ relationship из диаграммы (relationship_archi_ids)
- Structural relationships (Composition, Realization, Assignment) и AccessRelationship фильтруются
- Fallback: `-> * / * ->` если связи не резолвятся

### P2 fixes

**P2a: extra_archi_ids индексация**
В `attach_interfaces` и `build_data_access` дубликаты archi_id (extra_archi_ids)
не индексировались → интерфейсы и data access не резолвились для дублированных систем.
Добавлена индексация `comp_index[eid] = (sys, None)` в оба метода.

**P2b: TriggeringRelationship**
Тип TriggeringRelationship не был в `relevant_types` → пропускался при парсинге.
Добавлен в множество.

### P3: Structural relationships в solution views

`rel_lookup` хранил только `(source_id, target_id)` — тип терялся.
Изменён на 3-tuple `(source_id, target_id, rel_type)`.
В цикле integration view добавлен фильтр: `_structural_types` и `AccessRelationship`
пропускаются (как в `build_integrations`).

### Статистика

- 1658 appFunctions, 0 orphans (после P1 fix)
- 52 solution views (26 functional + 26 integration) → 36 файлов
- 2262 элемента в archi→c4 map

---

## Рефакторинг: модуляризация проекта

### Проблема

Монолитный `convert.py` (2 204 строки) — трудно читать, невозможно тестировать
отдельные части, нет инфраструктуры проекта.

### Решение

Разбит на 7 модулей в пакете `archi2likec4/`:

| Модуль | Строк | Содержимое |
|--------|-------|------------|
| `models.py` | ~170 | 12 dataclasses + 7 групп констант |
| `utils.py` | ~60 | transliterate, make_id, escape_str, build_metadata |
| `parsers.py` | ~330 | 7 parse_* + 6 _helpers |
| `builders.py` | ~440 | 9 build/attach/assign_* + _build_comp_index |
| `generators.py` | ~380 | 10 generate_* + 3 _render_* |
| `federation.py` | ~160 | 2 template-генератора |
| `pipeline.py` | ~220 | main() оркестрация |

**Граф зависимостей (без циклов):**
```
models.py  ← utils.py  ← parsers.py
                         ← builders.py    ← pipeline.py ← convert.py
                         ← generators.py
federation.py (standalone) ←──────────┘
```

**Дедупликация:** Извлечён общий `_build_comp_index(systems)` —
был дублирован в attach_interfaces, build_integrations, build_data_access.

**Entry points:**
- `python convert.py` — обёртка (4 строки)
- `python -m archi2likec4` — через __main__.py
- `archi2likec4` CLI — через pyproject.toml `[project.scripts]`

### Тесты

102 теста (pytest, stdlib-only, ~0.06s):
- `test_utils.py` — transliterate, make_id, escape_str, build_metadata
- `test_parsers.py` — XML parsing с tmp_path, trash filtering, parent resolution
- `test_builders.py` — system hierarchy, attach_functions, domains, integrations
- `test_generators.py` — spec, domain, detail, relationships, entities, views

### Верификация

- `diff -rq output/ output_backup/` → IDENTICAL (вывод побайтово совпал)
- Все 3 entry points работают

---

## Итерация 6: Промоция подсистем (PROMOTE_CHILDREN)

### Проблема

Некорректное ведение ArchiMate-репозитория: компоненты, фактически являющиеся
самостоятельными микросервисами, оформлены как подсистемы через dot-naming
(`EFS.Card_Service`). Конвертер схлопывал все интеграции в один «комок» родителя:

- `build_systems()`: `EFS.Card_Service` → Subsystem под EFS
- `build_integrations()`: дедупликация `src.split('.')[0]` → все 33 подсистемы EFS
  превращались в одну стрелку «EFS ↔ X»

Пример: EFS (33 подсистемы) — фронтальная платформа, чьи дочерние компоненты
давно стали самостоятельными микросервисами с собственными интеграциями.

### Решение: гибрид (конфиг + автопредупреждения)

**1. Конфиг `PROMOTE_CHILDREN`** (`models.py`):
```python
PROMOTE_CHILDREN: dict[str, str] = {'EFS': 'channels'}
```
Словарь `{parent_name: fallback_domain}`. Все `AppComponent` с именем
`{parent}.X` перестают быть подсистемами и становятся самостоятельными системами.
Компонент-родитель исчезает из результата.

3-segment имена (`EFS.Collection_Service.ODS`) → subsystem под промоутированной
системой (`EFS.Collection_Service`).

**2. Автоматические предупреждения** (`PROMOTE_WARN_THRESHOLD = 10`):
```
WARN: System "AIM" has 48 subsystems — consider adding to PROMOTE_CHILDREN
WARN: System "EFS_PLT" has 16 subsystems — consider adding to PROMOTE_CHILDREN
WARN: System "IABS" has 15 subsystems — consider adding to PROMOTE_CHILDREN
WARN: System "RAS" has 16 subsystems — consider adding to PROMOTE_CHILDREN
```

### Изменения

| Файл | Что изменилось |
|------|---------------|
| `models.py` | +`PROMOTE_CHILDREN`, +`PROMOTE_WARN_THRESHOLD` |
| `builders.py` | `build_systems()` → 4 фазы (promote + warn), `attach_interfaces()` → fallback для dot-имён |
| `test_builders.py` | +10 тестов `TestPromoteChildren` (промоция, наследование archi_id, 3-segment, warn) |

### Результат

- EFS (1 система с 33 подсистемами) → 24 самостоятельные системы + 9 подсистем под ними
- EFS_PLT (16 подсистем) → промоутирован аналогично
- `efs.c4` → 24 файла `efs_*.c4`; `efs_plt.c4` → 16 файлов `efs_plt_*.c4`
- Интеграции: вместо одной стрелки «EFS ↔ X» — детальные связи каждого микросервиса

---

## Итерация 7: Ревью и исправление 13 findings

### P1 (критичный): parent archi_id misroutes to arbitrary child

При промоции все дети наследовали `archi_id` родителя в `extra_archi_ids`.
Downstream dict-индексы (`_build_comp_index`, `_build_comp_c4_path`) перезаписывались
последним ребёнком → все связи/функции родителя EFS уходили в `efs_web_push_adapter`.

**Фикс**: убрано наследование `parent_archi_id` → `extra_archi_ids`. Связи,
ссылающиеся на удалённого родителя, становятся unresolved (честное поведение).

### P2 (средние): 8 исправлений

| # | Баг | Фикс |
|---|-----|------|
| 1 | Parent удалялся без детей | Удаление только при наличии promoted children |
| 2 | `_find_parent_component` не доходил до `application/` | `while current != app_dir.parent` |
| 3 | Коллизия view_id при одинаковых solution slug | Суффикс `_2`, `_3`... для дубликатов |
| 4 | `parse_solution_views` молча дропал дубликаты | Добавлен `WARN` при пропуске |
| 5 | `--help` падал как путь | `argparse` в `pipeline.main()` |
| 6 | Federation: `KeyError` на malformed registry | `.get()` + валидация перед доступом |
| 7 | Federation: `fetch`/`checkout` без `check=True` | Добавлен `check=True` |
| 8 | Federation: stale файлы не удалялись | Cleanup после sync (если не `--repo`) |

### P3 (низкие): 4 исправления

| # | Баг | Фикс |
|---|-----|------|
| 1 | Data access dedup по `(sys, entity)` терял семантику | Dedup по `(sys, entity, name)` |
| 2 | `pyproject.toml` «stdlib-only» vs PyYAML в federation | Комментарий о optional dep |
| 3 | Парсеры молча проглатывали XML ошибки | Счётчик + `WARN` в 5 parse_* функциях |
| 4 | Path traversal на Windows (`os.sep` split) | Split по обоим разделителям |

### Статистика

- 113 тестов, 0 failures, 0.07s
- 289 систем, 94 подсистемы, 333 интеграции, 245 data access links

---

## Итерация 8: Ревью — 7 findings (1 P1, 4 P2, 2 P3)

### P1 (критичный): parent archi_id не ремапился на promoted children

Итерация 7 убрала наследование `parent_archi_id` → `extra_archi_ids` (чтобы избежать
dict-overwrite). Но это привело к полной потере parent-level ссылок: функции и
интеграции, привязанные к archi_id родителя, стали unresolved (2 orphan-функции,
+11 skipped интеграций).

**Фикс**: parent archi_id теперь ремапится на **первого promoted ребёнка
алфавитно** (детерминированно, одна запись в `extra_archi_ids`). Это устраняет
dict-overwrite (один ребёнок — одна запись) и сохраняет parent-level связи.

Результат: 0 orphan-функций (было 2), 6 skipped интеграций (было 17), 337 интеграций (было 333).

### P2: 4 исправления

| # | Баг | Фикс |
|---|-----|------|
| 1 | Federation cleanup удаляет не-федерированные файлы | Marker-based: удаляются только файлы с `// Federated from:` |
| 2 | `attach_interfaces` игнорирует reverse structural direction | Добавлена обработка `Interface → Component` через `setdefault` |
| 3 | Дубликаты solution diagrams дропались | Merge: элементы и связи второго дубликата добавляются в первый |
| 4 | Высокий unresolved в solution views не останавливает pipeline | `generate_solution_views` возвращает `(files, unresolved, total)`, pipeline `sys.exit(1)` при >50% |

### P3: 2 исправления

| # | Баг | Фикс |
|---|-----|------|
| 1 | `PROMOTE_CHILDREN` value (fallback_domain) не использовался | `assign_domains()` применяет fallback для promoted children без domain-membership |
| 2 | `parse_solution_views` молча глотал XML parse errors | Счётчик `parse_errors` + `WARN` вывод |

### Статистика

- 119 тестов (+6 новых), 0 failures, 0.07s
- 289 систем, 94 подсистемы, 337 интеграций, 245 data access links
- 0 orphan-функций, 6 skipped интеграций, 3 unresolved интерфейса
- 21% unresolved в solution views (753/3557) — ниже порога 50%

---

## Итерация 9: Ревью — 4 findings (1 P1, 2 P2, 1 P3)

### P1 (критичный): remap parent→first child искажает семантику

Итерация 8 ремапила parent archi_id на **первого ребёнка алфавитно**. Это
избегало orphan-функций, но **все** parent-level связи (интеграции, data access,
functions) маршрутизировались на одного произвольного ребёнка — искажение модели.

**Фикс: fan-out**:
- `build_systems()` возвращает `(systems, promoted_parents)` где
  `promoted_parents: dict[str, list[str]]` — parent_archi_id → все c4_ids детей.
- Parent archi_id **НЕ** попадает в `extra_archi_ids` ни одного ребёнка.
- `build_integrations()`: связь с promoted parent → cross-product со ВСЕМИ детьми.
- `build_data_access()`: access от promoted parent → каждый ребёнок получает свой link.
- `attach_functions()`: функция, привязанная к promoted parent → honest orphan
  (parent больше не существует как single system).
- `generate_solution_views()`: promoted parent на диаграмме → все дети включаются.

Результат: 456 интеграций (было 337), 2 orphan-функции (honest orphans).

### P2: 2 исправления

| # | Баг | Фикс |
|---|-----|------|
| 1 | `.yaml` файлы в federation пишутся без marker → stale не удаляются | Добавлен `# Federated from:` marker в .yaml; cleanup проверяет оба маркера (`//` и `#`) |
| 2 | >50% unresolved в solution views → CI exit 0 | Pipeline проверяет ratio и вызывает `sys.exit(1)` (уже было, проверено) |

### P3: 1 исправление

| # | Баг | Фикс |
|---|-----|------|
| 1 | README «Только stdlib» — но federation нужен PyYAML | Уточнено: «Только stdlib (конвертер); scripts/federate.py требует PyYAML» |

### Статистика

- 125 тестов (+6 новых: TestIntegrationFanOut ×4, TestDataAccessFanOut ×2), 0 failures
- 289 систем, 94 подсистемы, 456 интеграций, 245 data access links
- 2 orphan-функции (honest: promoted parent), 6 skipped интеграций
- 21% unresolved в solution views (753/3557) — ниже порога 50%

---

## Итерация 10: Продуктовая готовность (12 из 15 findings)

Ревью выявило 15 findings (5 P1, 7 P2, 3 P3) с вердиктом «NO-GO for broad industrial use».
Адресовано 12 findings, отложено 3 (P1-2 honest orphans — spike, P2-3/P2-4 тесты — инкрементально).

### P1-1: Внешняя конфигурация

Создан модуль `archi2likec4/config.py` с `ConvertConfig` dataclass. Все захардкоженные
значения (PROMOTE_CHILDREN, DOMAIN_RENAMES, EXTRA_DOMAIN_PATTERNS, quality gate thresholds)
теперь конфигурируемы через `.archi2likec4.yaml`. При отсутствии конфига используются
дефолты из `models.py`.

Пример: `.archi2likec4.example.yaml` — документированный шаблон конфигурации.

### P1-3: Quality gates

Добавлены 3 quality gate в фазу `_validate()`:
1. Unresolved solution views (configurable `max_unresolved_ratio`, default 0.5)
2. Orphan functions (warning at `max_orphan_functions_warn`, default 5)
3. Unassigned systems (warning at `max_unassigned_systems_warn`, default 20)

`--strict` превращает warnings в errors. `--dry-run` валидирует без генерации файлов.

### P1-4: Federation reproducibility

Добавлено поле `sha` в registry template и `federate_template.py`. Если `sha` указан,
скрипт checkout-ит конкретный коммит вместо HEAD ветки.

### P1-5: Packaging

`pyproject.toml` дополнен: license (MIT), authors, keywords, classifiers,
`[project.optional-dependencies]` (federation, dev), `[build-system]`,
`[tool.pytest.ini_options]`, `[tool.setuptools.packages.find]`.

### P2-1: Рефакторинг pipeline

`main()` разбит на 4 фазы:
- `_parse()` → ParseResult (NamedTuple)
- `_build()` → BuildResult (NamedTuple)
- `_validate()` → (warnings, errors, sv_files, ...)
- `_generate()` → файлы на диск

### P2-2: Federation standalone

`federate.py` вынесен из строкового шаблона в реальный файл
`archi2likec4/scripts/federate_template.py`. `federation.py` читает его через
`importlib.resources`. Скрипт тестируем, линтуем, виден IDE.

### P2-5, P2-6: CLI

Добавлены флаги: `--config`, `--strict`, `--verbose`, `--dry-run`.
`main()` обёрнут в try/except с graceful error messages.

### P2-7: Governance

Добавлены `LICENSE` (MIT) и `CONTRIBUTING.md`.

### P3-2: Logging

Все `print()` заменены на `logging.getLogger('archi2likec4')`.
Уровни: DEBUG (verbose), INFO (progress), WARNING (проблемы), ERROR (failures).
`--verbose` переключает на DEBUG.

### P3-3: .gitignore

Удалён дубликат `dist/`, добавлены `htmlcov/`, `.coverage`, `.pytest_cache/`.

### Изменения

| Файл | Действие |
|------|----------|
| `archi2likec4/config.py` | Создан |
| `archi2likec4/scripts/federate_template.py` | Создан |
| `archi2likec4/scripts/__init__.py` | Создан |
| `.archi2likec4.example.yaml` | Создан |
| `LICENSE` | Создан |
| `CONTRIBUTING.md` | Создан |
| `tests/test_config.py` | Создан |
| `archi2likec4/pipeline.py` | Рефакторинг (4 фазы + CLI + logging) |
| `archi2likec4/builders.py` | Logging + promote_warn_threshold параметр |
| `archi2likec4/parsers.py` | Logging + domain_renames параметр |
| `archi2likec4/generators.py` | Logging |
| `archi2likec4/federation.py` | Standalone script + SHA field |
| `pyproject.toml` | Metadata + deps + build-system |
| `.gitignore` | Fix duplicates |
| `tests/test_builders.py` | capsys → caplog |

### Статистика

- 142 теста (+17 новых: test_config ×16, caplog fix ×1), 0 failures
- 289 систем, 94 подсистемы, 456 интеграций, 245 data access links
- Конвертер: идентичный output при дефолтах
- CLI: --help, --dry-run, --strict, --verbose, --config работают

---

## Итерация 11: Bug fixes & wiring (6 findings)

Ревьюер проверил итерацию 10. 142 теста зелёные, но 6 новых findings: 2 P1, 3 P2, 1 P3.

### P1: extra_domain_patterns не передавался в assign_domains()

`assign_domains()` вызывался без `config.extra_domain_patterns` — третий проход
всегда использовал захардкоженный `EXTRA_DOMAIN_PATTERNS` из `models.py`.

**Фикс**: добавлен параметр `extra_domain_patterns` в `assign_domains()` (builders.py),
передача из `_build()` в pipeline.py. Если параметр None — fallback на EXTRA_DOMAIN_PATTERNS.

### P1: load_config() вне try/except

`load_config()` вызывался ДО try/except блока в `main()`. Malformed YAML давал
raw traceback вместо graceful error.

**Фикс**: перемещён внутрь try/except. Добавлен fallback `logging.basicConfig()` до
try-блока. Verbose пере-конфигурируется после load.

### P2: Явный --config с несуществующим путём молча игнорировался

`load_config()` проверял `config_path.exists()`, но не различал явно указанный путь
и auto-detect. Несуществующий `--config /no/such/file` тихо возвращал дефолты.

**Фикс**: добавлен `explicit = config_path is not None`. Для explicit пути — `FileNotFoundError`.
Для auto-detect — тихий fallback на дефолты (как раньше).

### P2: domain_renames не валидировался

`tuple(v)` на строке молча создавал кортеж из символов: `tuple("abc") → ('a','b','c')`.

**Фикс**: проверка `isinstance(v, (list, tuple)) and len(v) == 2`, иначе `ValueError`.

### P2: __version__ = 0.5.0, pyproject.toml = 0.6.0

**Фикс**: `__init__.__version__` обновлён до `'0.6.0'`.

### P3: README не упоминал --config и PyYAML

**Фикс**: обновлена секция «Требования» — PyYAML для `--config` и `scripts/federate.py`.

### Изменения

| Файл | Действие |
|------|----------|
| `builders.py` | +`extra_domain_patterns` параметр в `assign_domains()` |
| `pipeline.py` | Передача параметра + restructure try/except |
| `config.py` | Explicit path error + domain_renames validation |
| `__init__.py` | Version sync 0.6.0 |
| `README.md` | Обновлены требования |
| `tests/test_config.py` | +3 теста (explicit path, invalid renames ×2) |
| `tests/test_builders.py` | +2 теста (custom/empty extra_domain_patterns) |

### Статистика

- 147 тестов (+5), 0 failures
- Конвертер: идентичный output

---

## Итерация 12: Packaging, config validation, UX (4 findings)

### P1: build-backend ломал сборку wheel

`build-backend = "setuptools.backends._legacy:_Backend"` — несуществующий модуль.
`pip wheel .` падал.

**Фикс**: заменён на стандартный `"setuptools.build_meta"`. Wheel собирается: `archi2likec4-0.6.0-py3-none-any.whl`.

### P2: YAML корень-список давал непонятную ошибку

Если `.archi2likec4.yaml` содержит список на корневом уровне, `_apply_yaml()` падал
с `'list' object has no attribute 'get'`.

**Фикс**: type guard в `load_config()`: `if not isinstance(data, dict): raise ValueError(...)`.

### P3: Config not found и model not found — одинаковое сообщение

Обе ошибки ловились одним `except FileNotFoundError` с текстом `"Input not found"`.

**Фикс**: `load_config()` вынесен в отдельный try/except:
- Config error → `"Configuration error: Config file not found: ..."`
- Model error → `"Input not found: ..."`

### P3: README не документировал CLI-флаги

**Фикс**: добавлена таблица CLI-флагов (`--config`, `--strict`, `--verbose`, `--dry-run`)
с примером использования.

### Изменения

| Файл | Действие |
|------|----------|
| `pyproject.toml` | build-backend → `setuptools.build_meta` |
| `config.py` | YAML root type guard |
| `pipeline.py` | Раздельная обработка config vs input errors |
| `README.md` | Документация CLI-флагов |
| `tests/test_config.py` | +1 тест (YAML root list) |

### Статистика

- 148 тестов (+1), 0 failures
- `pip wheel .` → OK
- Конвертер: идентичный output

---

## Инвентаризация coArchi-модели

### Масштаб входного репозитория

**Всего:** 11,315 XML-файлов в `architectural_repository/model/`

| Директория | Файлов | % | Описание |
|------------|--------|---|----------|
| `relations/` | 7,282 | 64.4% | Все типы relationships |
| `application/` | 3,043 | 26.9% | Application layer elements |
| `technology/` | 435 | 3.8% | Technology/infrastructure |
| `diagrams/` | 253 | 2.2% | 125 ArchimateDiagramModel + folders |
| `business/` | 162 | 1.4% | Business layer |
| `strategy/` | 113 | 1.0% | Capabilities + ValueStreams |
| `other/` | 24 | 0.2% | Grouping, Junction, Location |
| `motivation/` | 1 | 0% | Пустой (только folder.xml) |
| `implementation_migration/` | 1 | 0% | Пустой (только folder.xml) |

### Полная таблица элементов по типам

#### Application Layer (3,043 файлов) — ПАРСИМ

| ArchiMate тип | Кол-во | Парсим? | Выход |
|---------------|--------|---------|-------|
| ApplicationFunction | 1,708 | ✅ | → `appFunction` |
| ApplicationComponent | 397 | ✅ | → `system` / `subsystem` |
| DataObject | 309 | ✅ | → `dataEntity` |
| ApplicationInterface | 216 | ✅ | → links + api_interfaces metadata |
| ApplicationService | 19 | ❌ | Не парсим |
| ApplicationInteraction | 5 | ❌ | Не парсим |
| ApplicationEvent | 3 | ❌ | Не парсим |

ApplicationService (19 шт) — потенциально полезны для связи с business layer.
ApplicationInteraction и ApplicationEvent — микроскопические, можно игнорировать.

#### Technology Layer (423 файла) — ПАРСИМ (с итерации 13)

| ArchiMate тип | Кол-во | Парсим? | Выход |
|---------------|--------|---------|-------|
| **Node** | **205** | ✅ | → `infraNode` |
| **SystemSoftware** | **83** | ✅ | → `infraSoftware` |
| **TechnologyService** | 40 | ✅ | → `infraSoftware` |
| **Device** | 31 | ✅ | → `infraNode` |
| **TechnologyCollaboration** | 30 | ✅ | → `infraNode` (clusters) |
| **Artifact** | 24 | ✅ | → `infraSoftware` |
| **CommunicationNetwork** | 7 | ✅ | → `infraNode` |
| **Path** | 3 | ✅ | → `infraNode` |

Deployment-топология: AggregationRelationship → вложенность (до 3 уровней).
Cross-layer RealizationRelationship → `system -[deployedOn]-> infraNode`.

#### Business Layer (121 файл) — НЕ ПАРСИМ

| ArchiMate тип | Кол-во | Потенциал LikeC4 |
|---------------|--------|------------------|
| BusinessService | 109 | Бизнес-сервис → связь «app реализует business service» |
| BusinessActor | 7 | → `person` в LikeC4 |
| BusinessInterface | 3 | Каналы обслуживания |
| BusinessRole | 2 | Ролевая модель |

Тонкий слой. 109 BusinessService могут дать трассировку «бизнес → приложение».
7 BusinessActor → `person` элементы (пользователи, внешние системы-акторы).

#### Strategy Layer (96 файлов) — НЕ ПАРСИМ

| ArchiMate тип | Кол-во | Потенциал |
|---------------|--------|-----------|
| Capability | 57 | Бизнес-способности (имеют property `Domain`!) |
| ValueStream | 39 | Value streams (5 готовых диаграмм в model) |

Capability с property `Domain` — прямая связь с нашими доменами. Потенциально
capability map → отдельный view type.

#### Other (22 файла) — НЕ ПАРСИМ

| ArchiMate тип | Кол-во | Потенциал |
|---------------|--------|-----------|
| Grouping | 18 | Логическая группировка в диаграммах |
| Junction | 2 | OR/AND-соединители в flows |
| Location | 2 | Физические локации (ЦОД) |

Grouping может быть полезен для deployment views (зона DMZ, внутренний контур).
Location — для geo-distributed deployment.

#### Motivation (0 элементов) и Implementation/Migration (0 элементов)

Слои пусты в модели. Нечего парсить.

### Полная таблица relationships

| Тип | Кол-во | Парсим? | Используем для |
|-----|--------|---------|----------------|
| FlowRelationship | 2,346 | ✅ | → integrations (system↔system) |
| RealizationRelationship | 1,299 | ✅ | Structural parent + cross-layer App→Tech (deployment mapping) |
| AssignmentRelationship | 1,083 | ⚠️ частично | Structural parent only. Cross-layer App→Business теряем |
| CompositionRelationship | 1,023 | ✅ | → parent resolution (function→component) |
| ServingRelationship | 491 | ✅ | → integrations |
| AggregationRelationship | 462 | ✅ | Node↔SystemSoftware topology → вложенность infraNode/infraSoftware |
| AccessRelationship | 316 | ✅ | → data access (но accessType не извлекаем) |
| **AssociationRelationship** | **161** | **❌** | **Потеряны (generic cross-layer links)** |
| **SpecializationRelationship** | **72** | **❌** | **Потеряны (наследование DataObject)** |
| TriggeringRelationship | 27 | ✅ | → integrations |

**Главная потеря**: фильтр в `parsers.py` (`relevant_element_types`) требует оба конца
relationship быть application-элементами. Все cross-layer связи отбрасываются:
- App→Node (deployment) — ~200+ relationships
- App→BusinessService (realization) — ~100+ relationships
- Node→SystemSoftware (aggregation) — 462 relationships

### Диаграммы: 125 штук, используем 54

| Категория | Кол-во | Статус |
|-----------|--------|--------|
| functional_areas/ (domain views) | ~15 | ✅ → domain assignment |
| functional_architecture.* | 21 | ✅ → solution views |
| integration_architecture.* | 31 | ✅ → solution views |
| **technology / deployment views** | **~30** | **❌ Игнорируем** |
| **conceptual_architecture.*** | **12** | **❌ Игнорируем** |
| **value_stream.*** | **5** | **❌ Игнорируем** |
| **Прочие (проектные)** | **~11** | **❌ Игнорируем** |

### Properties в модели

16 уникальных ключей найдено по всему репозиторию:

| Key | Кол-во | Парсим? | Элементы |
|-----|--------|---------|----------|
| Domain | 50 | ❌ | Capability, ApplicationComponent |
| Target | 15 | ✅ | ApplicationComponent → `target_state` |
| LC stage | 15 | ✅ | ApplicationComponent |
| Full name | 15 | ✅ | ApplicationComponent |
| Criticality | 15 | ✅ | ApplicationComponent |
| placement | 14 | ✅ | ApplicationComponent |
| IS-officer full name | 12 | ✅ | ApplicationComponent |
| Dev team | 12 | ✅ | ApplicationComponent |
| Business owner dep | 12 | ✅ | ApplicationComponent |
| Architect full name | 12 | ✅ | ApplicationComponent |
| External/Internal | 11 | ✅ | ApplicationComponent → `placement` |
| CI | 4 | ✅ | ApplicationComponent |
| Client | 1 | ❌ | Мусор |
| method | 1 | ❌ | Не используем |
| url | 1 | ❌ | Не используем |
| external | 1 | ❌ | Мусор |

**Ключевое**: `Domain` property есть на 50 Capability-элементах — прямой маппинг
на наши домены, если когда-нибудь парсим Strategy layer.

### Итог: что берём vs что теряем

```
Берём:        2,348 application-элементов (100% application layer)
                423 technology-элементов (100% technology layer)
              5,748 relationships (~79% от всех)
                 54 диаграммы (43.2% от всех)

Теряем:         239 элементов (Business 121, Strategy 96, Other 22)
              1,534 relationships (cross-layer App→Business ~840,
                                   AssociationRel 161, SpecializationRel 72,
                                   прочие ~461)
                 71 диаграмму (technology/deployment ~30, conceptual 12,
                               value_stream 5, прочие 24)
```

**Capture rate:**
- Элементы: 2,771 / 3,010 = **92%** (было 78% до итерации 13)
- Relationships: 5,748 / 7,282 = **79%** (было 72.6%)
- Диаграммы: 54 / 125 = **43.2%**

---

## Итерация 13: Technology Layer + Deployment Topology

### Реализовано

Парсинг всего Technology layer (423 элемента) + deployment topology через
AggregationRelationship + cross-layer App→Tech mapping через RealizationRelationship.

### Новые модули/функции

| Компонент | Что добавлено |
|-----------|--------------|
| `models.py` | `TechElement`, `DeploymentNode` dataclasses |
| `parsers.py` | `parse_technology_elements()`, расширены `relevant_element_types` |
| `builders.py` | `build_deployment_topology()`, `build_deployment_map()`, `_build_deployment_path_index()` |
| `generators.py` | `generate_deployment_c4()`, `generate_deployment_mapping_c4()`, `generate_deployment_view()`, обновлён `generate_spec()` |
| `pipeline.py` | Расширены ParseResult/BuildResult, вызовы новых функций |

### Kind mapping

| ArchiMate тип | LikeC4 kind |
|---------------|-------------|
| Node, Device, TechnologyCollaboration, CommunicationNetwork, Path | `infraNode` |
| SystemSoftware, TechnologyService, Artifact | `infraSoftware` |

### Deployment topology

AggregationRelationship определяет вложенность (до 3 уровней):
- TechnologyCollaboration → Node (cluster → server)
- Node → SystemSoftware (server → software)

Cross-layer RealizationRelationship: `system -[deployedOn]-> infraNode`.
Вложенные ноды используют qualified paths (`parent.child`).

### Output

```
output/
  specification.c4           ← +infraNode, +infraSoftware, +deployedOn
  deployment/                ← NEW
    topology.c4              ← infraNode tree with nested infraSoftware
    mapping.c4               ← app -[deployedOn]-> infraNode
  views/
    deployment-architecture.c4  ← NEW
```

### Статистика

- 172 теста, 0 failures
- 423 technology элементов, 735 deployment nodes, 383 deployment mappings
- Capture rate: элементы 78% → 92%, relationships 72.6% → 79%

---

## Итерация 14: Code review fixes (8 findings)

### Findings addressed

| # | Severity | Описание | Фикс |
|---|----------|----------|------|
| P1-1 | Critical | NOTES.md inventory outdated | Обновлена инвентаризация: Technology → ПАРСИМ, capture rate 92% |
| P1-2 | Critical | No e2e tests for pipeline | `tests/test_pipeline_e2e.py`: synthetic model, full pipeline, dry_run |
| P1-3 | Critical | `bool('false')` → True в config | Explicit type checking: `isinstance(val, bool)` / `str.lower() in (...)` |
| P1-4 | Critical | `extra_domain_patterns` not validated | Schema validation in `_apply_yaml()`: required keys, type checks |
| P1-5 | Critical | Promoted-parent fanout missing in solution views | `promoted_archi_to_c4` fallback + cross-product expansion |
| P2-8 | Medium | Mutable defaults in ConvertConfig | Deep copy via `default_factory=lambda` |
| P2-9 | Medium | XML parse errors swallowed silently | `logger.debug()` in folder.xml handlers |
| P3-10 | Low | Dead code block in generators.py | Removed `if sub.functions: pass` |

### Not addressed (known/deferred)

| # | Severity | Описание | Reason |
|---|----------|----------|--------|
| P2-6 | Medium | Architecture coverage limited to application layer | Known — Technology layer added in iter 13; Business/Strategy deferred |
| P2-7 | Medium | 3 deferred findings without closure criteria | Tracked in NOTES.md |

### Статистика

- 183 теста (+11), 0 failures
- Конвертер: идентичный output

## Итерация 15: Structured Audit Data + AUDIT.md

### Что сделано

Перевод качественного аудита из текстового лога в структурированные данные.

- **`archi2likec4/audit_data.py`** — новый модуль:
  - `AuditSummary` dataclass: метрики конвертации (systems, subsystems, integrations, metadata %, domain coverage)
  - `AuditIncident` dataclass: QA-инцидент с severity, affected items, remediation hints
  - `compute_audit_incidents()`: вычисляет 9 категорий инцидентов (QA-1..QA-9)
  - Suppress-механика: `audit_suppress` (по системам), `audit_suppress_incidents` (по QA-ID)

- **9 QA-инцидентов**:
  - QA-1 Critical: Системы без домена (unassigned)
  - QA-2 High: Пробелы в метаданных (CI, Full name, LC stage, etc.)
  - QA-3 High: Системы с тегом `to_review`
  - QA-4 Medium: Кандидаты на промоцию (>= threshold подсистем)
  - QA-5 Medium: Системы без документации
  - QA-6 Low: Осиротевшие функции
  - QA-7 Critical: Потерянные интеграции (relationships → 0 integrations)
  - QA-8 High: Покрытие solution views (% разрешённых элементов)
  - QA-9 Medium: Системы без инфраструктурного маппинга

- **`generators.py`** — `generate_audit_md()`: генерация AUDIT.md с таблицами, severity, remediation
- **`config.py`** — поля `audit_suppress`, `audit_suppress_incidents`, `save_suppress()`
- **Pipeline** — интеграция: compute → generate AUDIT.md, suppress-флаги из конфига

### Статистика

- 208 тестов (+25), 0 failures
- AUDIT.md генерируется как часть вывода

## Итерация 16: Flask Web UI для аудита качества

### Что сделано

- **`archi2likec4/web.py`** — Flask-приложение (710 строк):
  - Субкоманда `archi2likec4 web [--port PORT]`
  - Дашборд: 6 метрик-карточек + таблица инцидентов с severity-бейджами
  - Detail-страницы: таблица affected элементов для каждого QA-инцидента
  - Suppress/Unsuppress: POST-маршруты → обновление `.archi2likec4.yaml`
  - Inline Jinja2-шаблоны (self-contained HTML без внешних зависимостей)

- **Pipeline** — `_web_command()`: парсинг аргументов, запуск Flask-сервера
- **pyproject.toml** — optional dependency `web` = ["flask>=2.3", "pyyaml>=6.0"]

### Статистика

- 208 тестов, 0 failures
- Web UI: http://localhost:8090

## Итерация 17: Remediation-действия + UX-улучшения дашборда

### Что сделано

**A. Remediation-действия (3 QA-инцидента)**

| QA | Действие в UI | Конфиг-поле |
|----|---------------|-------------|
| QA-1 | Assign domain (dropdown) | `domain_overrides: {name: domain}` |
| QA-3 | Mark reviewed (кнопка) | `reviewed_systems: [name, ...]` |
| QA-4 | Promote (dropdown + кнопка) | `promote_children: {name: domain}` |

- `config.py`: поля `domain_overrides`, `reviewed_systems` + `update_config_field()`
- `builders.py`: Pass 0 в `assign_domains()` (overrides — высший приоритет); `reviewed_systems` в `build_systems()` убирает тег `to_review`
- `pipeline.py`: прокинуты новые параметры

**B. Видимость подавленных инцидентов**

- `audit_data.py`: поле `suppressed: bool` — инциденты всегда создаются, подавленные помечаются
- Дашборд: серые зачёркнутые строки с "(suppressed)" и кнопкой Unsuppress
- Detail: подавленные элементы серым в конце таблицы

**C. Страница ревизии `/remediations`**

- Обзор всех конфиг-решений: domain overrides, reviewed, promoted, suppressed
- Кнопки Undo для каждого решения
- Ссылка с дашборда "Review all"

**D. Цветные метрики**

- `metric-ok` (зелёный), `metric-warn` (жёлтый), `metric-crit` (красный), `metric-info` (серый)
- With Domain: ≥80% ok, 50-80% warn, <50% crit
- Metadata: ≥50% ok, 20-50% warn, <20% crit
- Integrations/Deploy: >0 ok, 0 crit

### Статистика

- 223 теста (+15), 0 failures
- 7 новых POST-маршрутов, страница /remediations

## Бэклог релиза 1.0

### Блокеры (MUST) — ✅ DONE

**B1. ✅ Документация — убрать legacy-шум**
- README.md: `convert.py` → `archi2likec4` / `python -m archi2likec4`
- CONTRIBUTING.md: аналогично
- `convert.py` оставлен как legacy wrapper (не документирован)

**B2. ✅ pyproject.toml — готовность к публикации**
- Classifier: `Development Status :: 5 - Production/Stable`
- Добавлен `readme = "README.md"`
- Добавлен `[project.urls]` (Homepage, Repository)
- Версия `1.0.0` в `__init__.py` и `pyproject.toml`

**B3. ✅ Тесты — покрытие audit_data.py**
- Добавлены тесты: QA-2 (4 теста), QA-3 (3), QA-4 (3), QA-5 (3), QA-6 (2), QA-8 (3), QA-9 (4)
- Итого 22 новых теста (было 7, стало 29)

**B4. ✅ Тесты — conftest.py**
- `MockConfig` и `MockBuilt` вынесены в `tests/helpers.py`
- `tests/conftest.py` импортирует и предоставляет как fixtures

**B5. ✅ Тесты — web.py**
- 18 тестов: dashboard (5), incident detail (5), remediations (3), helpers (5)
- Flask test client с мокированным pipeline

### Рекомендуемые (SHOULD) — ✅ DONE

**S1. ✅ Валидация иерархии систем/подсистем в Web UI**
- Страница `/hierarchy` — системы/подсистемы сгруппированы по доменам
- 5 тестов в test_web.py

**S2. ✅ print() → logger в web.py**
- `print()` заменён на `logger.info()` в startup message

**S3. ✅ py.typed маркер**
- PEP 561: пустой файл `archi2likec4/py.typed`

### Можно отложить (COULD) — ✅ DONE

**C1. ✅ CHANGELOG.md**
- История релизов в CHANGELOG.md

**C2. ✅ Расширение тестов парсера**
- 16 новых тестов: `_detect_special_folder` (3), `_find_parent_component` (3), `parse_domain_mapping` (3), `parse_solution_views` (5+2 deployment)

**C3. ✅ CLI-тесты**
- 11 тестов: args (5), error handling (5), web subcommand (1)

### Пост-1.0 бэклог — ✅ DONE

**P1. ✅ dataStore на deployment-диаграмме**
- SystemSoftware с именем БД (PostgreSQL, Oracle, Redis, MongoDB и т.д.) → `kind='dataStore'`
- Regex-паттерн `_DATASTORE_PATTERNS` в builders.py для автоматического распознавания
- `build_datastore_entity_links()` — связка dataStore ↔ dataEntity через AccessRelationship
- deployment/datastore-mapping.c4 с `persists` relationships
- deployment view включает `element.kind = dataStore`
- 12 новых тестов

**P2. ✅ i18n (ru/en) + отвязка от банка**
- `archi2likec4/i18n.py` — каталог сообщений ru/en для 10 QA-инцидентов + audit заголовки
- `config.language: str = 'ru'` — выбор языка через YAML или по умолчанию
- Банко-специфичные константы перенесены из models.py → config.py:
  - `_DEFAULT_DOMAIN_RENAMES`, `_DEFAULT_EXTRA_DOMAIN_PATTERNS`, `_DEFAULT_PROMOTE_CHILDREN`
  - models.py теперь содержит пустые дефолты (универсальный конвертер)
- audit_data.py полностью на i18n (get_msg, get_qa10_issue)
- generators.py — header + summary AUDIT.md на i18n (get_audit_label)
- 19 новых тестов (i18n, language config, dataStore)

### Не делаем (WON'T для 1.0)

- Async/threading — модели до 10K систем, sequential достаточно
- Business/Strategy layer ArchiMate — только Application + Technology

---

## Бэклог релиза 2.0

**Видение:** Из внутреннего банковского инструмента — в **стандартный мост
между ArchiMate и LikeC4** для международного сообщества архитекторов.

**Тема релиза:** Open-source продукт для практикующих архитекторов.

v1.0 умеет конвертировать одну модель для одной команды.
v2.0 должен стать инструментом, который архитектор из Берлина, Токио или
Сан-Паулу установит за 30 секунд, подключит к своей модели и получит
работающий LikeC4-workspace с интерактивной диагностикой качества.

### Эпик A: Дистрибуция — «brew install за 30 секунд»

**A1. PyPI + pipx — основной канал**
- Публикация на PyPI: `pipx install archi2likec4`
- Проверить: все зависимости опциональны, чистый `pip install` без flask/pyyaml
- README: installation one-liner для Linux/macOS/Windows

**A2. Homebrew tap**
- Создать `github.com/Lenivvenil/homebrew-archi2likec4`
- Ruby formula с virtualenv isolation (по образцу httpie/pgcli)
- `brew tap Lenivvenil/archi2likec4 && brew install archi2likec4`
- Автоматизация: GitHub Action для обновления формулы при новом релизе

**A3. Docker-образ**
- `ghcr.io/lenivvenil/archi2likec4:latest`
- Для CI/CD пайплайнов и тех, кто не хочет ставить Python
- Маленький alpine-based образ, entrypoint = CLI

**A4. GitHub Releases + автоматизация**
- GitHub Action: при push тега `v*` → PyPI publish + brew formula update + Docker push
- Генерация release notes из CHANGELOG.md
- Checksums и подписи для security-conscious пользователей

### Эпик B: Интернационализация — 7 языков

Текущее: ru/en. Целевое: **en, ru, de, fr, pt-BR, nl, ja** — покрытие
основных рынков EA-практики (DACH, Франция, Бразилия, Нидерланды — родина
ArchiMate, Япония).

**B1. Расширение i18n-каталога**
- 10 QA-инцидентов × 7 языков (title, description, remediation)
- AUDIT.md headers + summary на всех языках
- Web UI: все строки через i18n (сейчас часть захардкожена)

**B2. Locale-aware CLI**
- Автоопределение языка из `LANG`/`LC_ALL` env
- Fallback: `config.language` → env → en
- `--language de` override

**B3. Вынос строк в gettext-совместимый формат**
- Переход с dict-каталога (i18n.py) на `.po/.mo` файлы
- Возможность контрибьюторам присылать переводы через стандартный workflow
- Интеграция с Weblate / Crowdin для community-переводов

### Эпик C: Web UI — от dashboard к рабочему инструменту

**C1. Интерактивный domain assignment**
- Drag-and-drop систем между доменами
- Сохранение в `domain_overrides` конфига
- Цель: снизить unassigned без редактирования YAML вручную

**C2. Metadata bulk-edit**
- Импорт метаданных из CSV/Excel (CI, владелец, criticality)
- Inline-редактирование metadata прямо в таблице
- Маппинг по имени системы или archi_id

**C3. Review workflow для #to_review систем**
- Список систем из !РАЗБОР с действиями: keep / archive / merge
- Результат → обновление `reviewed_systems` в конфиге

**C4. Model explorer**
- Навигация по полной модели: домены → системы → подсистемы → функции
- Граф интеграций (интерактивная визуализация связей между системами)
- Поиск, фильтрация по домену/тегу/статусу
- Переход от «аудит-дашборда» к «архитектурному порталу»

**C5. Auto-fix wizard**
- QA-10 (floating SystemSoftware): предложить parent Node
- QA-9 (no infra binding): матчинг system↔node по имени
- QA-4 (promotion candidates): автопредложение promote_children
- Wizard-интерфейс: проблема → предложение → accept/reject → apply to config

**C6. Современный frontend**
- Переход с inline Jinja2 на отдельный SPA (React/Svelte/Vue)
- REST API backend (Flask → FastAPI опционально)
- Responsive design, полноценная тёмная тема
- Возможность встраивания LikeC4 diagram-компонентов (`@likec4/diagram`)

### Эпик D: Экосистемная интеграция

**D1. Поддержка ArchiMate Model Exchange Format**
- Парсер для Open Group Exchange XML (archimate3_Model.xsd + View.xsd)
- Любой ArchiMate-сертифицированный инструмент → LikeC4
- Не только Archi: BiZZdesign, Sparx EA, MEGA HOPEX, Modelio
- Это **ключ к широкой аудитории** — не привязываемся к coArchi

**D2. Поддержка .archimate формата (standalone Archi)**
- Одиночный файл .archimate (не coArchi/Grafico)
- Многие архитекторы не используют coArchi, работают с файлом напрямую
- Автодетект формата: coArchi dir / .archimate file / Exchange XML

**D3. jArchi-скрипт для экспорта в LikeC4**
- JavaScript-скрипт для Archi: «Export to LikeC4» одной кнопкой
- Вызывает archi2likec4 CLI или генерирует промежуточный Exchange XML
- Публикация в jArchi community scripts wiki

**D4. LikeC4 Model API интеграция**
- Использование `LikeC4.fromWorkspace()` для валидации сгенерированных .c4
- Post-generate проверка: парсится ли выход LikeC4 без ошибок?
- Опционально: запуск `likec4 build` как quality gate

**D5. CI/CD шаблоны**
- GitHub Action: `uses: Lenivvenil/archi2likec4-action@v2`
- GitLab CI include-шаблон
- Автоматический MR/PR с change report при изменении модели
- Quality gate: блокировка при деградации метрик

### Эпик E: Диагностика и объяснимость

**E1. Verbose tracing — «почему потерялась интеграция»**
- `--trace` флаг: для каждого skipped relationship — причина
- Structured log (JSON) + human-readable summary
- Web UI: страница трассировки потерь

**E2. Lineage — «откуда взялся элемент»**
- `archi2likec4 explain <c4-id>` → цепочка: XML → parse → build → generate
- Обратная ссылка на исходный XML файл + строку
- Web UI: click на элемент → lineage panel

**E3. Coverage map**
- Какие ArchiMate-объекты конвертированы, какие нет
- Группировка по типам и слоям ArchiMate
- HTML-отчёт в Web UI + standalone export

**E4. Change report**
- При каждом запуске — diff: что добавлено, удалено, изменено
- Markdown, пригодный для MR description
- `archi2likec4 diff --since <commit>` для targeted-отчёта

### Эпик F: Расширение модели

**F1. Business Layer**
- Парсинг: BusinessProcess, BusinessFunction, BusinessRole, BusinessActor
- LikeC4 kinds: actor, process, capability
- Связи serves/uses между business и application слоями
- Новый view: business capability map

**F2. Группировки и теги**
- ArchiMate Grouping → LikeC4 tags
- Фильтрация views по тегам
- Пользовательские группировки в конфиге

**F3. Расширенные view-типы**
- Dynamic views (sequence-style)
- Deployment views per environment (dev/test/prod split)
- Cross-domain integration matrix

### Приоритизация v2.0

| Приоритет | ID | Название | Почему | Сложность |
|-----------|-----|----------|--------|-----------|
| MUST | A1 | PyPI + pipx | Базовая дистрибуция, без этого нет продукта | Низкая |
| MUST | A2 | Homebrew tap | «brew install» — порог входа для macOS-архитекторов | Низкая |
| MUST | A4 | GitHub Releases CI | Автоматизация релизов, без ручной работы | Низкая |
| MUST | D1 | Exchange Format | Ключ к широкой аудитории — любой ArchiMate-инструмент | Высокая |
| MUST | D2 | .archimate формат | Покрытие standalone-пользователей Archi | Средняя |
| MUST | B1 | i18n 7 языков | en/de/fr/pt-BR/nl/ja — покрытие мирового рынка EA | Средняя |
| MUST | E1 | Verbose tracing | Объяснимость — доверие к инструменту | Низкая |
| SHOULD | C1 | Domain assignment UI | Интерактивное решение #1 QA-проблемы | Средняя |
| SHOULD | C4 | Model explorer | Из dashboard в архитектурный портал | Высокая |
| SHOULD | D5 | CI/CD шаблоны | Автоматизация для команд | Средняя |
| SHOULD | E2 | Lineage/explain | Отладка и доверие | Средняя |
| SHOULD | E4 | Change report | Прозрачность для MR review | Средняя |
| SHOULD | C2 | Metadata bulk-edit | Решение QA-2 (1% metadata) | Низкая |
| SHOULD | D3 | jArchi-скрипт | Интеграция в Archi напрямую | Низкая |
| SHOULD | F1 | Business Layer | Полнота модели, новая аудитория | Высокая |
| COULD | A3 | Docker-образ | CI convenience | Низкая |
| COULD | B2 | Locale-aware CLI | DX polish | Низкая |
| COULD | B3 | gettext/.po файлы | Community-переводы | Средняя |
| COULD | C3 | Review workflow | QA-3 (176 #to_review) | Средняя |
| COULD | C5 | Auto-fix wizard | QA-9, QA-10 | Средняя |
| COULD | C6 | SPA frontend | Современный UX | Высокая |
| COULD | D4 | LikeC4 Model API | Post-generate валидация | Низкая |
| COULD | E3 | Coverage map | Визуализация покрытия | Средняя |
| COULD | F2 | Теги и группировки | Nice-to-have | Низкая |
| COULD | F3 | Расширенные views | LikeC4 ещё не всё поддерживает | Высокая |

### Волны реализации v2.0

**Волна 1 — «Open source launch» (MVP для сообщества)**
- A1 (PyPI), A2 (brew), A4 (CI releases)
- D1 (Exchange Format), D2 (.archimate)
- B1 (i18n 7 языков), E1 (tracing)
- Результат: любой архитектор в мире может установить и попробовать

**Волна 2 — «Power tools»**
- C1 (domain assignment), C4 (model explorer), C2 (metadata edit)
- D5 (CI/CD), D3 (jArchi), E2 (lineage), E4 (change report)
- Результат: инструмент для ежедневной работы, а не разовой конвертации

**Волна 3 — «Full platform»**
- C6 (SPA frontend), F1 (Business Layer), B3 (gettext)
- C5 (auto-fix), F2 (теги), F3 (views)
- Результат: полноценная платформа architecture-as-code bridge

### Критерии готовности v2.0

- [ ] `brew install archi2likec4` работает из tap
- [ ] `pipx install archi2likec4` работает из PyPI
- [ ] Поддержка 3 входных форматов: coArchi, .archimate, Exchange XML
- [ ] 7 языков UI/отчётов: en, ru, de, fr, pt-BR, nl, ja
- [ ] Web UI: model explorer + interactive domain assignment
- [ ] `--trace` для диагностики потерянных элементов
- [ ] GitHub Action для автоматизации в CI
- [ ] 500+ тестов, покрытие > 80%
- [ ] README на английском, Getting Started guide
- [ ] CHANGELOG.md, версия 2.0.0

---

## Итерация post-1.0: Диагностика и устранение потерь (2026-03-10)

### Контекст

После прогона конвертера на живом coArchi-репозитории банка выявлены
системные причины неполной конвертации. Ниже — согласованный с архитектором
анализ и план исправлений.

### Статистика прогона (после Phase 1 fixes)

| Метрика | Значение |
|---------|----------|
| Элементов ArchiMate | 2 998 |
| Связей | 6 381 |
| Систем | 289, подсистем 94 |
| Интеграций (resolved) | 456 из 2 762 eligible |
| Потерянных интеграций | 298 (10.8%) |
| Data entities | 309, orphan 70 (22.7%) |
| Solution views | 87, resolution 92.2% |
| Unassigned systems | 108 (37.4%) |
| Deployment nodes | 425, mappings 383 |

### Корневые причины потерь — решения архитектора

#### 1. ApplicationService (276 потерянных интеграций, 343 unresolved view refs)

**Факт**: 93% потерянных интеграций — FlowRelationship с ApplicationService
как endpoint. ApplicationService не парсится и не индексируется.

**Решение архитектора**: ApplicationService НЕ ложится в иерархию L1–L5
(domain → system → subsystem → function → entity). Обрабатывать аналогично
ApplicationInterface:
- Парсить XML-файлы `ApplicationService_*.xml`
- Резолвить ownership через RealizationRelationship → parent ApplicationComponent
- Строить `service_c4_path: dict[str, str]` (как `iface_c4_path`)
- Использовать в `build_integrations()`, `build_data_access()`, `build_archi_to_c4_map()`

**Ожидаемый эффект**: ~276 восстановленных интеграций, 3 orphan entities
(HUMO/UzCard/MasterCard Cards), ~343 resolved view refs.

#### 2. Unassigned systems (108 штук)

**Факт**: 37.4% систем не на domain views.

**Решение архитектора**: это «псевдосистемы» — подсистемы решений, нарисованные
подрядчиками до утверждения нотации моделирования. Не баг конвертера, а проблема
исходных данных. Частично решается через:
- `domain_overrides` в .archi2likec4.yaml (19 систем через CompositionRelationship)
- Auto-inherit domain от parent через Composition (future)
- Ручная расстановка архитектором

#### 3. Orphan data entities (70 штук)

67 из 70 — просто нет AccessRelationship в исходной модели. Проблема полноты
модели, не конвертера. 3 (HUMO/UzCard/MasterCard Cards) решатся через #1
(ApplicationService → DataObject access).

#### 4. View hierarchy — плоский список в портале LikeC4

**Факт**: все views отображаются как плоский нечитаемый мегасписок.

**Решение**: LikeC4 строит навигационное дерево через **`/` в title**:
```
title 'Функциональные области / Каналы / AIM / Функциональная архитектура'
```
Создаёт папки в sidebar. У нас уже есть `folder_path` в SolutionView —
нужно конвертировать его в читаемые заголовки с `/`.

#### 5. Deployment — отсутствие вложенности в UI

**Факт**: наш код генерирует вложенный deployment (Location → Cluster → Node →
Software), но в UI может не отображаться корректно.

**Текущее состояние**: формат `model {}` с вложенными infraNode корректен.
Deployment view включает все элементы по kind. Нужно проверить:
- Корректность relationship `deployedOn` в LikeC4
- Достаточность view predicate для отображения вложенности

#### 6. Trash views в output (6 штук)

`_is_in_trash()` проверяет только model tree, а не view/diagrams tree.
Нужно проверять trash в обоих деревьях.

### План реализации Phase 2

**V2-S1: ApplicationService resolution** (P1)
- parsers.py: добавить `parse_application_services()` (как parse_application_interfaces)
- models.py: добавить `AppService` dataclass (как AppInterface)
- builders.py: добавить `resolve_services()` → `service_c4_path`
- builders.py: использовать service_c4_path в build_integrations, build_data_access
- builders.py: добавить services в build_archi_to_c4_map
- pipeline.py: интегрировать
- Тесты

**V2-S2: View hierarchy через title** (P1)
- parsers.py: сохранять human-readable folder names (не slugs)
- generators.py: генерировать title с `/` разделителями из folder_path
- Тесты

**V2-S3: Trash filter для diagrams tree** (P2)
- parsers.py: `_is_in_trash()` для view XML paths тоже
- Тесты

---

## Горизонт v3.0 — «Двусторонний мост»

**Видение:** Не только ArchiMate → LikeC4, но и **LikeC4 → ArchiMate**.
Архитекторы правят модель в Archi, разработчики — в LikeC4, изменения
синхронизируются в обе стороны.

**Ключевые идеи:**
- Обратная синхронизация: изменения в .c4 → патчи coArchi XML / Exchange XML
- Минимальный scope: domain_overrides, metadata, documentation, новые связи
- Conflict resolution при одновременном редактировании
- Watch-режим с двусторонним sync
- Plugin-архитектура для кастомных трансформаций (хуки post-parse/pre-generate)
- Multi-model merge: несколько coArchi-репо → один LikeC4 workspace
- Strategy/Motivation Layer (Goal, Principle, Requirement → traceability)
- Потенциально: VS Code extension для .c4 ↔ ArchiMate навигации
