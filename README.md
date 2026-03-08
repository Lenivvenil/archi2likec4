# archi2likec4

Конвертер из [coArchi](https://github.com/archimatetool/archi-modelrepository-plugin) XML (ArchiMate) в [LikeC4](https://likec4.dev/) `.c4` файлы.

## Что делает

Читает модель coArchi (Git-репозиторий ArchiMate) и генерирует полный набор `.c4` файлов для LikeC4:

- **Domains** — бизнес-домены (извлекаются из `diagrams/functional_areas/`)
- **Systems / Subsystems** — из `ApplicationComponent` (точка в имени = subsystem)
- **AppFunctions** — из `ApplicationFunction` (привязка через Composition/Assignment/Realization)
- **DataEntities** — из `DataObject` + AccessRelationship
- **Integrations** — из FlowRelationship / ServingRelationship / TriggeringRelationship
- **Views** — landscape, functional, integration, persistence-map, solution views

## Структура проекта

```
archi2likec4/
├── pyproject.toml          # метаданные пакета
├── convert.py              # entry point (обёртка)
├── archi2likec4/
│   ├── __init__.py
│   ├── __main__.py         # python -m archi2likec4
│   ├── models.py           # dataclasses + константы
│   ├── utils.py            # transliterate, make_id, escape_str
│   ├── parsers.py          # парсинг XML файлов coArchi
│   ├── builders.py         # трансформация: systems, integrations, domains
│   ├── generators.py       # генерация .c4 файлов
│   ├── federation.py       # шаблоны для federate.py
│   └── pipeline.py         # main() — оркестрация
├── tests/
│   ├── test_utils.py
│   ├── test_builders.py
│   ├── test_generators.py
│   └── test_parsers.py
└── architectural_repository/  # входные данные (coArchi модель)
```

## Использование

```bash
# Стандартный запуск (модель в architectural_repository/model, выход в output/)
python convert.py

# Указать пути
python convert.py /path/to/model /path/to/output

# Через модуль
python -m archi2likec4

# Просмотр результата
cd output && npx likec4 serve
```

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
├── views/
│   ├── landscape.c4            # top-level view
│   ├── persistence-map.c4      # data entity map
│   ├── domains/{domain}/
│   │   ├── functional.c4       # systems in domain
│   │   └── integration.c4      # cross-domain links
│   └── solutions/
│       └── {solution}.c4       # solution-level views
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
- Только stdlib (конвертер); сгенерированный `scripts/federate.py` требует PyYAML
- pytest для тестов (`pip install pytest`)
