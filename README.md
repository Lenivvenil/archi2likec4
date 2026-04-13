# archi2likec4

[![PyPI version](https://img.shields.io/pypi/v/archi2likec4)](https://pypi.org/project/archi2likec4/)
[![Python versions](https://img.shields.io/pypi/pyversions/archi2likec4)](https://pypi.org/project/archi2likec4/)
[![Homebrew tap](https://img.shields.io/badge/homebrew-tap-orange)](https://github.com/Lenivvenil/homebrew-archi2likec4)
[![License: MIT](https://img.shields.io/github/license/Lenivvenil/archi2likec4)](LICENSE)

Конвертер из [coArchi](https://github.com/archimatetool/archi-modelrepository-plugin) XML в [LikeC4](https://likec4.dev/) architecture-as-code.

## Installation

```bash
# PyPI (базовая установка — zero runtime dependencies)
pip install archi2likec4

# Homebrew (macOS/Linux)
brew tap Lenivvenil/archi2likec4
brew install archi2likec4

# PyPI с Web UI (Flask dashboard)
pip install "archi2likec4[web]"
```

## Зачем

Архитектурная модель в Archi — это полноценная база знаний: системы, интеграции, deployment, метаданные. Но доступ к ней — только через десктопное приложение. Нельзя дать ссылку коллеге, нельзя встроить в CI, нельзя навигировать в браузере.

**archi2likec4** выгружает эту модель в [LikeC4](https://likec4.dev/) — code-first инструмент, где архитектура описывается текстовыми `.c4` файлами, версионируется в Git и рендерится как интерактивный портал прямо в браузере.

Результат: вся архитектурная информация из Archi становится доступна любому через `npx likec4 serve`, без установки Archi.

```bash
pip install archi2likec4
archi2likec4
cd output && npx likec4 serve
```

---

## Что конвертируется

```mermaid
graph LR
  subgraph "coArchi XML"
    AC[ApplicationComponent]
    AF[ApplicationFunction]
    DO[DataObject]
    REL[Relationships]
    TECH[Technology layer]
    DIAG[Diagrams]
  end

  subgraph "LikeC4 .c4"
    DOM[Domains]
    SYS[Systems / Subsystems]
    FN[Functions]
    INT[Integrations]
    DATA[Data entities]
    DEPL[Deployment topology]
    VIEWS[Views]
  end

  DIAG --> DOM
  AC --> SYS
  AF --> FN
  DO --> DATA
  REL --> INT
  TECH --> DEPL
  DIAG --> VIEWS
```

- **Домены** — из иерархии диаграмм `functional_areas/`
- **Субдомены** — из вложенных папок `functional_areas/{domain}/{subdomain}/` (L2, опционально)
- **Системы и подсистемы** — из `ApplicationComponent` (точка в имени = подсистема: `EFS.Core`)
- **Функции** — из `ApplicationFunction`, привязанные к родительской системе
- **Интеграции** — из Flow / Serving / Triggering relationships
- **Data-сущности** — из `DataObject` + `AccessRelationship`
- **Deployment** — полное дерево инфраструктуры из Technology-слоя
- **Solution views** — functional, integration, deployment из диаграмм Archi
- **AUDIT.md** — 10 категорий quality-инцидентов с рекомендациями по исправлению

На выходе ~200 `.c4` файлов, готовых к `likec4 serve`.

---

## CLI

```bash
archi2likec4 [MODEL_ROOT] [OUTPUT_DIR] [--config PATH] [--strict] [--verbose] [--dry-run] [--sync-target DIR]
```

По умолчанию: модель в `architectural_repository/model/`, выход в `output/`.
С `--strict` предупреждения quality gates становятся ошибками.
С `--dry-run` — только валидация, файлы не пишутся.
С `--sync-target DIR` — после генерации скопировать файлы в указанную директорию (переопределяет YAML-настройку `sync_target`).

---

## Конфигурация

Всё опционально. Скопируйте `.archi2likec4.example.yaml` → `.archi2likec4.yaml`:

```yaml
promote_children:           # подсистемы → самостоятельные системы
  EFS: channels

domain_renames:             # переименование доменов из Archi
  banking_operations: [products, "Products"]

extra_domain_patterns:      # назначение домена по паттерну имени
  - c4_id: platform
    name: Platform
    patterns: [ELK, Grafana, Kubernetes]

quality_gates:
  max_unresolved_ratio: 0.5

audit_suppress: [LegacySystem]          # исключить из AUDIT.md
audit_suppress_incidents: [QA-6]        # подавить категорию целиком
domain_overrides: { AD: platform }      # ручное назначение домена
subdomain_overrides:                    # ручное назначение субдомена
  SystemName: subdomain_c4_id
sync_target: /path/to/companion-repo   # авто-копирование output после генерации
```

---

## Web UI

```bash
pip install "archi2likec4[web]"
archi2likec4 web
```

Дашборд на `localhost:8090`: метрики модели, 10 QA-инцидентов, one-click ремедиации (назначить домен, промоутить подсистему, подавить инцидент). Все решения — на странице `/remediations`. Тёмная тема, русский и английский язык.

---

## Quality Audit

Каждый запуск генерирует `AUDIT.md` — реестр инцидентов для владельцев ArchiMate-модели.

| | Что проверяется |
|---|---|
| **QA-1** Critical | Системы без домена |
| **QA-2** High | Пустые карточки (нет ни одного заполненного свойства) |
| **QA-3** High | Системы в папке `!РАЗБОР` |
| **QA-4** Medium | Кандидаты на декомпозицию (10+ подсистем) |
| **QA-5** Medium | Системы без documentation |
| **QA-6** Low | Осиротевшие функции |
| **QA-7** Critical | Нерезолвленные интеграции |
| **QA-8** High | Элементы solution views, не найденные в модели |
| **QA-9** Medium | Системы без deployment-маппинга |
| **QA-10** Medium | Проблемы иерархии развёртывания |

Пустые категории не отображаются. Подавленные — учитываются прозрачно.

---

## Как устроен конвертер

```mermaid
graph LR
  XML["coArchi XML"] --> P["Parse"]
  P --> B["Build"]
  B --> V["Validate"]
  V --> G["Generate"]
  G --> C4[".c4 files"]
  G --> AUDIT["AUDIT.md"]

  P -. "ParseResult" .-> B
  B -. "BuildResult" .-> V
```

Четыре фазы, данные передаются через типизированные `NamedTuple`. Нет глобального состояния.

Иерархия элементов: **L1 домен → L2 субдомен → L3 система → L4 подсистема → L5 функция**.

```
archi2likec4/
  models.py         dataclasses: System, Integration, DeploymentNode…
  config.py         ConvertConfig, YAML-загрузка, валидация
  parsers.py        coArchi XML → dataclasses
  builders/         сборка систем, доменов, интеграций, deployment (пакет)
  generators/       dataclasses → .c4 контент + AUDIT.md (пакет)
  templates/        Jinja2-шаблоны .c4 и AUDIT.md
  audit_data.py     compute_audit_incidents() — структурированные QA-данные
  i18n.py           каталог сообщений ru/en
  web.py            Flask UI (dashboard, ремедиации, иерархия)
  pipeline.py       convert() API, main() CLI, оркестрация
```

---

## Library Usage

```python
from archi2likec4 import convert, ConvertConfig

# Простейший вызов — использует .archi2likec4.yaml из текущей директории
result = convert('architectural_repository/model', 'output')
print(f'Сконвертировано {result.systems_count} систем, записано {result.files_written} файлов')

# Передача конфига явно
cfg = ConvertConfig(strict=True, language='en')
result = convert('model', 'out', config=cfg)

# Dry-run — валидация без записи файлов
result = convert('model', 'out', dry_run=True)
assert result.files_written == 0
```

Исключения при ошибках:
- `FileNotFoundError` — директория модели не найдена
- `ConfigError` — ошибка в `.archi2likec4.yaml`
- `ParseError` — все XML-файлы в директории не распарсились
- `ValidationError` — нарушены quality gates

---

## Разработка

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v   # 586+ тестов
```

Python >= 3.10. Базовая конвертация — zero dependencies (stdlib only).
Опционально: `[web]` — Flask + PyYAML (аудит-дашборд), `[federation]` — PyYAML (федерация).
YAML-конфиг (`.archi2likec4.yaml`) также требует PyYAML: `pip install pyyaml`.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and PR guidelines.

For security issues, see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
