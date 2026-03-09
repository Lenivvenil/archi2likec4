# archi2likec4

Конвертер из [coArchi](https://github.com/archimatetool/archi-modelrepository-plugin) XML (ArchiMate) в [LikeC4](https://likec4.dev/) `.c4` файлы.

## Что делает

Читает модель coArchi (Git-репозиторий ArchiMate) и генерирует полный набор `.c4` файлов для LikeC4:

- **Domains** — бизнес-домены (извлекаются из `diagrams/functional_areas/`)
- **Systems / Subsystems** — из `ApplicationComponent` (точка в имени = subsystem)
- **AppFunctions** — из `ApplicationFunction` (привязка через Composition/Assignment/Realization)
- **DataEntities** — из `DataObject` + AccessRelationship
- **Integrations** — из FlowRelationship / ServingRelationship / TriggeringRelationship
- **Deployment** — инфраструктурная топология из Technology-слоя ArchiMate
- **Views** — landscape, functional, integration, persistence-map, deployment, solution views
- **AUDIT.md** — отчёт качества конвертации (9 категорий инцидентов)

## Структура проекта

```
archi2likec4/
├── pyproject.toml          # метаданные пакета
├── archi2likec4/
│   ├── __init__.py
│   ├── __main__.py         # python -m archi2likec4
│   ├── models.py           # dataclasses + константы
│   ├── utils.py            # transliterate, make_id, escape_str
│   ├── parsers.py          # парсинг XML файлов coArchi
│   ├── builders.py         # трансформация: systems, integrations, domains
│   ├── generators.py       # генерация .c4 файлов
│   ├── config.py           # ConvertConfig + YAML-загрузка
│   ├── audit_data.py       # вычисление QA-инцидентов
│   ├── web.py              # Flask UI для аудита качества
│   ├── federation.py       # шаблоны для federate.py
│   └── pipeline.py         # main() — оркестрация
├── tests/
│   ├── test_utils.py
│   ├── test_parsers.py
│   ├── test_builders.py
│   ├── test_generators.py
│   ├── test_config.py
│   ├── test_audit_data.py
│   └── test_pipeline_e2e.py
└── architectural_repository/  # входные данные (coArchi модель)
```

## Использование

```bash
# Стандартный запуск (модель в architectural_repository/model, выход в output/)
archi2likec4

# Указать пути
archi2likec4 /path/to/model /path/to/output

# Через модуль (альтернатива)
python -m archi2likec4

# Просмотр результата
cd output && npx likec4 serve
```

### CLI-флаги

| Флаг | Описание |
|------|----------|
| `--config PATH` | YAML-файл конфигурации (по умолчанию: `.archi2likec4.yaml` если есть) |
| `--strict` | Качественные пороги (quality gates) как ошибки, а не предупреждения |
| `--verbose` | Подробный вывод (уровень DEBUG) |
| `--dry-run` | Только парсинг и валидация, без генерации файлов |

Пример:

```bash
python -m archi2likec4 --config my-config.yaml --strict --verbose
```

### Web UI для аудита качества

```bash
# Запустить дашборд (по умолчанию http://localhost:8090)
archi2likec4 web

# Указать порт и конфиг
archi2likec4 web --port 9000 --config my-config.yaml /path/to/model
```

Дашборд показывает метрики конвертации, 9 категорий QA-инцидентов и позволяет:
- Назначать домены неразмеченным системам (QA-1)
- Отмечать системы как проверенные (QA-3)
- Промоутить подсистемы (QA-4)
- Подавлять инциденты (suppress) с прозрачным отображением
- Ревизировать все принятые решения на странице `/remediations`

Требует `flask` (`pip install archi2likec4[web]`).

## Структура вывода

```
output/
├── specification.c4            # kinds, colors, tags
├── relationships.c4            # cross-domain integrations
├── entities.c4                 # dataEntity + access relationships
├── domains/
│   └── {domain}.c4             # domain + nested systems
├── systems/
│   └── {system}.c4             # extend block + detail view
├── deployment/
│   ├── topology.c4             # инфраструктурные узлы
│   └── mapping.c4              # app → infra маппинг
├── views/
│   ├── landscape.c4            # top-level view
│   ├── persistence-map.c4      # data entity map
│   ├── deployment-architecture.c4  # deployment view
│   ├── domains/{domain}/
│   │   ├── functional.c4       # systems in domain
│   │   └── integration.c4      # cross-domain links
│   └── solutions/
│       └── {solution}.c4       # solution-level views
├── AUDIT.md                    # отчёт качества конвертации
└── scripts/
    ├── federate.py             # pull system specs from repos
    └── federation-registry.yaml
```

## Тесты

```bash
python -m pytest tests/ -v
```

## Требования

- Python ≥ 3.10
- Конвертер использует только stdlib
- PyYAML (`pip install archi2likec4[federation]`) — для `--config` и `scripts/federate.py`
- Flask (`pip install archi2likec4[web]`) — для web UI аудита качества
- pytest для тестов (`pip install archi2likec4[dev]`)
