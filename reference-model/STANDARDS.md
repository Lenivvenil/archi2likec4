# Принципы и стандарты архитектурной модели LikeC4

Этот документ — первоисточник для подготовки, ревью и развития архитектурной модели в формате LikeC4. Все решения в золотом стандарте (reference-model) и в выходе конвертера archi2likec4 должны соответствовать этим принципам.

---

## 1. Философия: зачем нужна модель

### Модель — это живая документация, а не картинка

Архитектурная модель в LikeC4 — это **код**, который версионируется, ревьюится и валидируется. Она не рисуется в визуальном редакторе и не экспортируется в PNG для вставки в Confluence. Модель живёт в git-репозитории рядом с кодом и CI/CD.

**Почему это важно:**
- Картинка устаревает в момент создания. Код обновляется в рамках рабочего процесса.
- Диаграмма в Visio/Draw.io не имеет семантики — это набор прямоугольников. Модель в LikeC4 знает, что `payment_hub` — это `system`, а не просто синий прямоугольник.
- Модель позволяет генерировать множество views из одного источника данных. Одна правка в модели обновляет все диаграммы.

### Один источник правды (architecture-as-code)

Каждый элемент архитектуры описывается **ровно один раз** в модели. Views — это проекции модели, не дублирование данных. Если система описана в `model/domains/payments.c4`, её свойства не повторяются в view-файлах.

### Навигация вместо полотна

Архитектурная модель — это **дерево с навигацией**, а не одна гигантская диаграмма. Пользователь начинает с ландшафта (30 000 ft) и погружается через `navigateTo` к нужному уровню детализации.

```
Landscape (L1-L3)
  └── navigateTo → Domain view (интеграции)
        └── navigateTo → System view (функциональная архитектура L3-L5)
              └── navigateTo → System deployment view (инфраструктура)
```

**Правило:** ни один view не должен содержать >25 элементов. Если больше — декомпозируйте на вложенные views.

---

## 2. Иерархия элементов

Модель использует 5-уровневую иерархию элементов, каждый уровень имеет свой `kind` в спецификации.

### Таблица уровней

| Уровень | Kind | Назначение | Пример | Источник в ArchiMate |
|---------|------|-----------|--------|---------------------|
| L1 | `domainGroup` | Группа доменов — функциональная область верхнего уровня | Business, Support, Technology | Grouping / Folder |
| L2 | `domain` | Бизнес-домен — связная область ответственности | Channels, Payments, Risk | Grouping / Folder |
| L3 | `system` | Прикладная система — развёртываемый продукт | Core Banking, Payment Hub | ApplicationComponent |
| L4 | `subsystem` | Подсистема / модуль — крупный функциональный блок внутри системы | Accounts Module, GL Module | ApplicationComponent (вложенный) |
| L5 | `appFunction` | Прикладная функция — атомарная бизнес-операция | Open Account, Calculate Balance | ApplicationFunction |

### Когда использовать каждый уровень

**L1 → L2 (domainGroup → domain):**
Всегда присутствуют. Каждая система принадлежит ровно одному домену. Домены группируются в domain groups по бизнес-логике (бизнес / поддержка / технология).

**L3 (system):**
Всегда присутствует. Система — это то, что имеет имя, команду-владельца и может быть развёрнуто независимо. Если что-то нельзя задеплоить отдельно — это subsystem, а не system.

**L4 (subsystem):**
Используется, когда система содержит >1 различимого модуля. Примеры:
- Монолит с модулями (Core Banking → Accounts, GL, Customer)
- Набор микросервисов внутри одного продукта (Payment Hub → Orchestrator, Clearing, SWIFT Adapter)

**Правило:** если в ArchiMate у системы есть вложенные ApplicationComponent — они становятся subsystem.

**L5 (appFunction):**
Используется, когда у subsystem (или system без subsystems) есть явные бизнес-функции. Примеры:
- Accounts Module → Open Account, Close Account, Freeze Account
- Clearing Engine → Calculate Net Position, Generate Settlement File

**Правило:** если в ArchiMate у компонента есть ApplicationFunction — они становятся appFunction.

### Что НЕ является уровнем иерархии

- **Базы данных, очереди, хранилища** — это не subsystem и не appFunction. Это deployment-артефакты, они описываются в deployment модели как `instanceOf` или как `dataStore` / `dataEntity` в data-слое.
- **Технические компоненты** (rate limiter, auth middleware) — это subsystem, если они имеют бизнес-смысл; иначе это деталь реализации, которая не нужна в архитектурной модели.

### Пример полной иерархии

```likec4
model {
  bank = enterprise 'Demo Bank' {
    business = domainGroup 'Business' {                      // L1
      payments = domain 'Payments' {                         // L2
        payment_hub = system 'Payment Hub' {                 // L3
          // ... subsystems и functions в extend-файле
        }
      }
    }
  }
}

// systems/payment_hub/model.c4
model {
  extend bank.business.payments.payment_hub {
    orchestrator = subsystem 'Payment Orchestrator' {        // L4
      validate_payment = appFunction 'Validate Payment' {}   // L5
      route_payment = appFunction 'Route Payment' {}         // L5
      execute_payment = appFunction 'Execute Payment' {}     // L5
    }
    clearing = subsystem 'Clearing Engine' {                 // L4
      calc_net = appFunction 'Calculate Net Position' {}     // L5
      gen_settlement = appFunction 'Generate Settlement' {}  // L5
    }
    swift_adapter = subsystem 'SWIFT Adapter' {              // L4
      format_mt103 = appFunction 'Format MT103' {}           // L5
      send_fin = appFunction 'Send FIN Message' {}           // L5
    }
  }
}
```

---

## 3. Визуальный язык

### Принцип: каждый kind визуально отличим

На любом view пользователь должен **без легенды** отличить system от subsystem, subsystem от appFunction. Это достигается комбинацией трёх параметров: **цвет**, **форма**, **размер**.

### Таблица визуальных назначений

| Kind | Color | Shape | Size | Обоснование |
|------|-------|-------|------|-------------|
| `domainGroup` | `amber` | `rectangle` | `large` | Тёплый, группирующий, крупный — сразу видно структурный контейнер |
| `domain` | `secondary` | `rectangle` | — | Нейтральный серо-голубой — структура, не акцент |
| `system` | `primary` | `rectangle` | — | Основной синий — главный объект внимания |
| `subsystem` | `indigo` | `rectangle` | — | Глубже = холоднее; отличается от primary насыщенностью |
| `appFunction` | `slate` | `rectangle` | `small` | Самый мелкий и приглушённый — лист дерева |
| `externalSystem` | `muted` | `rectangle` | — | Явно внешний — бледный, не наш |
| `dataEntity` | `data-green` | `document` | — | Данные = зелёный; форма document — не прямоугольник |
| `dataStore` | `gray` | `cylinder` | — | Хранилище = цилиндр — классическая метафора БД |
| `actor` | `green` | `person` | — | Человек — форма person |

### Правила контраста

1. **Соседние уровни иерархии не используют один цвет.** L3 (primary) ≠ L4 (indigo) ≠ L5 (slate).
2. **Форма отличает категорию.** Приложения = rectangle. Данные = document/cylinder. Люди = person.
3. **Размер отличает глубину.** domainGroup = large. appFunction = small. Остальные = default.
4. **Внешнее = muted.** Всё, что не наше (external systems, actors, CBR, Visa) — приглушённые цвета.

### Пользовательские цвета

Конвертер определяет собственную палитру для точного контроля:

```likec4
specification {
  color archi-app #7EB8DA       // Голубой — прикладные системы
  color archi-app-light #BDE0F0 // Светло-голубой — подсистемы
  color archi-data #F0D68A      // Жёлтый — данные
  color archi-store #B0B0B0     // Серый — хранилища
  color archi-tech #93D275      // Зелёный — инфраструктура
}
```

**Правило:** если встроенных цветов LikeC4 недостаточно для контраста — определяйте custom color через hex.

### Связи (relationships)

| Тип | Color | Line | Head | Когда |
|-----|-------|------|------|-------|
| `sync` | `green` | `solid` | `normal` | REST, gRPC, JDBC — запрос-ответ |
| `async` | `amber` | `dashed` | `open` | Kafka, RabbitMQ — fire-and-forget |
| `publishes` | `amber` | `dashed` | `open` | Публикация событий в брокер |
| `subscribes` | `green` | `dotted` | `diamond` | Подписка на события |
| `owns` | `primary` | `dotted` | `diamond` | Владение данными (golden source) |
| `reads` | `muted` | `dotted` | `open` | Чтение чужих данных (CDC, API) |
| `writes` | `red` | `dotted` | `normal` | Запись в чужие данные |
| `persists` | `gray` | `dashed` | `normal` | dataStore → dataEntity |

---

## 4. Типы view и их назначение

Каждый view отвечает на конкретный вопрос. Если вопрос не сформулирован — view не нужен.

### 4.1 Landscape (index)

**Вопрос:** «Из чего состоит наш IT-ландшафт?»

**Аудитория:** CTO, новый сотрудник, внешний аудитор.

**Что показывает:**
- Все domain groups, domains и systems (L1 → L2 → L3)
- Внешних акторов (customer, operator)
- Внешние системы (CBR, Visa, SWIFT)
- Ключевые межгрупповые связи

**Что НЕ показывает:** subsystems, appFunctions, data entities, deployment.

**navigateTo:** каждый domain — ссылка на domain view.

```likec4
views {
  view index {
    title 'Demo Bank — System Landscape'
    include bank
    include bank.business
    include bank.business.*          // domains
    include bank.business.*.*        // systems inside domains
    include bank.support
    include bank.support.*
    include bank.support.*.*
    include bank.tech
    include bank.tech.*
    include bank.tech.*.*
    include customer, operator, cbr, visa, swift
    include customer -> bank.business.channels.*
    include operator -> bank.business.channels.*
    // navigateTo на domain views
    include bank.business.payments with { navigateTo domain_payments }
    autoLayout TopBottom
  }
}
```

### 4.2 Domain view — интеграционная архитектура

**Вопрос:** «Как системы этого домена взаимодействуют с остальным миром?»

**Аудитория:** архитектор домена, тимлид, аналитик.

**Что показывает:**
- Все системы домена
- ВСЕ входящие связи (кто вызывает наши системы)
- ВСЕ исходящие связи (кого вызывают наши системы)
- Внешние системы-контрагенты

**Что НЕ показывает:** внутренности систем (subsystems), внутренние связи чужих доменов.

**navigateTo:** каждая система — ссылка на system view.

**Scope:** всегда привязан к конкретному домену через `view X of {path}`.

```likec4
views {
  view domain_payments of bank.business.payments {
    title 'Payments — Integration Architecture'
    include *                                    // все системы домена
    include -> bank.business.payments.* ->       // все входящие/исходящие
    // navigateTo на system views
    include bank.business.payments.payment_hub with { navigateTo system_paymenthub }
    include bank.business.payments.card_processing with { navigateTo system_cardprocessing }
    autoLayout TopBottom
  }
}
```

**Почему именно «интеграционная архитектура»:** этот view показывает контракты между доменами. Архитектор домена видит все точки зависимости — кто от него зависит и от кого зависит он.

### 4.3 System view — функциональная архитектура

**Вопрос:** «Что внутри этой системы? Из каких модулей и функций она состоит?»

**Аудитория:** тимлид, разработчик, новый инженер в команде.

**Что показывает:**
- Подсистемы (L4) внутри системы
- Прикладные функции (L5) внутри подсистем
- Внутренние связи между подсистемами
- Входящие/исходящие связи системы (но НЕ внутренности соседей)

**Что НЕ показывает:** deployment, data entities, внутренности других систем.

**Scope:** `view X of {domain}.{system}`.

```likec4
views {
  view system_paymenthub of bank.business.payments.payment_hub {
    title 'Payment Hub — Functional Architecture'
    include *                                        // subsystems + appFunctions
    include -> bank.business.payments.payment_hub -> // внешние связи
    autoLayout TopBottom
  }
}
```

**Критерий полноты:** если system view показывает только сам system без вложенных элементов — модель неполная. Каждая система должна быть декомпозирована минимум до L4.

### 4.4 System deployment view — где развёрнута система

**Вопрос:** «На какой инфраструктуре работает эта конкретная система?»

**Аудитория:** DevOps, SRE, инженер на дежурстве.

**Что показывает:**
- Только те инфра-ноды, на которых размещены компоненты этой системы
- Путь: site → segment → cluster → namespace/VM → instance

**Что НЕ показывает:** соседние системы, весь ЦОД, другие namespace.

**Scope:** per-system. Файл: `systems/{id}/deployment.c4`.

```likec4
// systems/payment_hub/deployment.c4

deployment {
  extend prod.dc1.app.k8s.ns_payments {
    instanceOf bank.business.payments.payment_hub.orchestrator
    instanceOf bank.business.payments.payment_hub.clearing
    instanceOf bank.business.payments.payment_hub.swift_adapter
  }
  extend prod.dc1.data {
    instanceOf bank.business.payments.payment_hub.payment_db
    instanceOf bank.business.payments.payment_hub.payment_queue
  }
}

views {
  deployment view paymenthub_deployment {
    title 'Payment Hub — Production Deployment'
    include prod.dc1.app.k8s.ns_payments.*
    include prod.dc1.data.pg_cluster.*
    include prod.dc1.data.kafka.*
    autoLayout TopBottom
  }
}
```

**Почему per-system, а не весь ЦОД:** дежурный инженер в 3 часа ночи должен видеть только то, что относится к его системе. Обзор всего ЦОД — это отдельный view для инфраструктурной команды.

### 4.5 Deployment overview — обзор инфраструктуры

**Вопрос:** «Как выглядит наша инфраструктура целиком?»

**Аудитория:** инфраструктурная команда, CISO, аудитор.

**Что показывает:**
- Все environments (prod, staging)
- Все sites (ЦОД)
- Все segments, clusters, серверы

**Ограничение LikeC4:** оператор `.**` не работает в deployment views. Используйте star-chain:

```likec4
views {
  deployment view deployment_overview {
    title 'Deployment Architecture'
    include prod
    include prod.*                    // sites
    include prod.dc1.*               // segments
    include prod.dc1.app.*           // clusters
    include prod.dc1.app.k8s.*       // namespaces
    include prod.dc1.data.*          // storage
    include prod.dc1.dmz.*           // DMZ nodes
    include prod.dc1.mgmt.*          // monitoring
    autoLayout TopBottom
  }
}
```

### 4.6 Custom views — произвольные срезы

**Вопрос:** любой вопрос, который не покрывается стандартными views.

**Примеры:**
- «Что входит в PCI-DSS scope?»
- «Кто владеет какими данными?»
- «Что сломается, если упадёт Payment Hub?» (blast radius)
- «Какие системы обрабатывают PII?»

**Техники построения:**

| Техника | Синтаксис | Когда |
|---------|-----------|-------|
| Явный список | `include system_a, system_b` | Точно знаете, что показать |
| Фильтр по kind | `include * where kind is system` | Все элементы одного типа |
| Фильтр по тегу | `include * where tag is #pci_dss` | Семантический срез |
| Wildcard потомки | `include bank.business.payments.**` | Всё внутри scope |
| Связи элемента | `include -> payment_hub ->` | Blast radius |
| Стиль-оверлей | `style system_x { color red }` | Визуальное выделение |

```likec4
// Пример: PCI-DSS scope
views {
  view custom_pci {
    title 'PCI-DSS Scope'
    include * where tag is #pci_dss
    include visa
    include -> visa ->
    style * where tag is #pci_dss {
      color red
      border solid
    }
    autoLayout TopBottom
  }
}
```

**Правило именования:** custom views имеют префикс `custom_`.

---

## 5. Deployment модель

### Иерархия deployment nodes

```
environment (prod, staging, dev)
└── site (= ЦОД / площадка)
    └── segment (DMZ, Application, Data, Management)
        └── cluster / server (k8s, физический сервер, hypervisor)
            └── namespace / vm (k8s namespace, виртуальная машина)
                └── instanceOf (экземпляр элемента модели)
```

**Правило:** site = ЦОД. Это один уровень, не два. Если у вас одна площадка с одним ЦОД — это один site.

### Deployment node kinds

| Kind | Notation | Стиль | Когда |
|------|----------|-------|-------|
| `environment` | Environment | primary | prod, staging, dev |
| `site` | Site / Data Center | secondary, dashed | DC-1 Moscow, DC-2 SPb |
| `segment` | Network Segment | amber, dotted | DMZ, App Zone, Data Zone |
| `cluster` | Cluster | indigo | k8s cluster, DB cluster |
| `server` | Physical Server | slate | Dell R750, bare metal |
| `vm` | Virtual Machine | indigo, multiple | vm-web-01, vm-app-02 |
| `namespace` | Namespace | sky, dashed | k8s namespace |
| `storage` | Storage | gray, storage shape | Oracle RAC, PostgreSQL |
| `infraSoftware` | Infrastructure Software | gray | Kafka, Prometheus, Vault |

### Принцип разделения: инфраструктура отдельно от приложений

**Инфраструктурные файлы** (`infrastructure/*.c4`) описывают ТОЛЬКО топологию — environments, sites, segments, clusters, серверы. Никаких `instanceOf`.

**Per-system файлы** (`systems/{id}/deployment.c4`) описывают ТОЛЬКО размещение — `extend` инфраструктурного узла + `instanceOf` элементов модели.

```
infrastructure/
├── environments.c4      # deployment { environment prod {} }
└── dc1_moscow.c4        # deployment { extend prod { dc1 = site ... } }

systems/payment_hub/
└── deployment.c4        # deployment { extend prod.dc1.app.k8s.ns_payments { instanceOf ... } }
```

**Почему:** инфраструктура меняется редко и одна на всех. Размещение систем меняется часто и принадлежит команде системы.

### System tags для deployment

Каждая система автоматически получает тег `#system_{system_c4_id}`. Все вложенные элементы (subsystems, appFunctions) наследуют этот тег. Это позволяет фильтровать deployment views по системе.

---

## 6. Связи (relationships)

### Принципы

1. **Связь описывается один раз, от источника.** `payment_hub -> core_banking`, не наоборот.
2. **Каждая связь имеет label (что делает) и technology (как).** Связь без technology — неполная.
3. **Межсистемные связи живут в `integrations.c4`.** Внутрисистемные — в `systems/{id}/model.c4`.
4. **Тип связи определяет визуальный стиль.** sync = сплошная зелёная, async = пунктирная жёлтая.

### Формат

```likec4
// Межсистемная
bank.business.payments.payment_hub -[sync]-> bank.business.products.core_banking 'Debit/credit operations' {
  technology 'gRPC, Protobuf'
}

// Асинхронная через брокер
bank.business.payments.payment_hub -[async]-> bank.support.risk.aml 'AML screening' {
  technology 'Kafka, Avro'
}

// Данные
bank.business.products.core_banking -[owns]-> bank.do_customer 'Golden Source'
bank.tech.analytics.dwh -[reads]-> bank.do_transactions 'CDC replication' {
  technology 'Debezium'
}
```

### Что НЕ является связью в модели

- Сетевые маршруты (L3/L4) — это deployment, не модель
- Внутренние вызовы внутри одного subsystem — слишком детально
- Зависимости сборки (Maven, npm) — не архитектурный уровень

---

## 7. Метаданные и теги

### Обязательные метаданные

| Поле | Где | Зачем |
|------|-----|-------|
| `metadata.archi_id` | Все элементы | Трассировка к исходному ArchiMate |
| `description` | Все элементы | Краткое описание назначения |
| `technology` | Системы, связи | Стек технологий |

### Ограничения длины

- `description` на system/subsystem: **макс 500 символов**
- `description` на appFunction: **макс 300 символов**
- Если текст длиннее — обрезается с `...`

### Стандартные теги

| Тег | Назначение |
|-----|-----------|
| `#system_{id}` | Автотег системы (для deployment фильтрации) |
| `#critical` | Tier-1, SLA 99.99% |
| `#pci_dss` | В scope PCI-DSS аудита |
| `#pii` | Обрабатывает персональные данные |
| `#golden_source` | Единственный владелец данных |
| `#deprecated` | Выводится из эксплуатации |
| `#planned` | Запланирована, ещё не в production |
| `#external` | Внешняя система |
| `#to_review` | Требует ревью архитектора |

---

## 8. Файловая структура

```
output/
├── specification.c4                         # Kinds, colors, relationships, tags
├── model/
│   └── domains/
│       └── {domain_id}.c4                   # Domain + systems (L1-L3)
├── systems/
│   └── {system_id}/
│       ├── model.c4                         # extend: subsystems + functions (L4-L5) + relationships
│       └── deployment.c4                    # extend infra: instanceOf + per-system deployment view
├── infrastructure/
│   ├── environments.c4                      # deployment { environment prod {} }
│   └── {site_id}.c4                         # Site topology (segments, clusters, servers)
├── views/
│   ├── landscape.c4                         # index view (L1-L3)
│   ├── domains/
│   │   └── {domain_id}/
│   │       ├── functional.c4                # Domain functional view
│   │       └── integration.c4               # Domain integration view
│   ├── deployment-architecture.c4           # Deployment overview (all sites)
│   └── custom/                              # Custom views (PCI-DSS, data ownership, etc.)
│       └── {name}.c4
├── MATURITY.md                              # GAP-based quality report
└── maturity.json                            # Machine-readable maturity data
```

### Правила именования файлов

- Все имена в `kebab-case`
- Домены: `model/domains/{domain_c4_id}.c4`
- Системы: `systems/{system_c4_id}/model.c4` и `deployment.c4`
- Views: `views/domains/{domain_c4_id}/functional.c4`

### Правила именования идентификаторов (c4 id)

- Только `[a-z][a-z0-9_]*` — строчные буквы, цифры, подчёркивания
- **Без дефисов** — LikeC4 парсит их как минус
- Генерируются из имён через транслитерацию и нормализацию

---

## 9. Чеклист качества модели

### Структура
- [ ] Каждый element kind визуально отличим (цвет + форма + размер)
- [ ] Нет двух kinds с одинаковым цветом, которые появляются на одном view
- [ ] Каждая система декомпозирована минимум до L4 (subsystem)
- [ ] Системы с >3 subsystems содержат appFunctions (L5)

### Views
- [ ] Landscape (index) показывает L1 → L2 → L3
- [ ] Каждый domain имеет integration view
- [ ] Каждая система имеет functional view (показывает до L5)
- [ ] Каждая система имеет per-system deployment view
- [ ] `navigateTo` связывает: landscape → domain → system
- [ ] Ни один view не содержит >25 элементов

### Связи
- [ ] Все inter-system relationships имеют `technology`
- [ ] Каждая связь имеет label (что делает)
- [ ] Нет дублирования связей (одна связь = одно направление)
- [ ] Тип связи (sync/async) соответствует реальному протоколу

### Deployment
- [ ] Infrastructure файлы не содержат `instanceOf`
- [ ] Per-system deployment файлы содержат `instanceOf` + targeted view
- [ ] Deployment overview использует star-chain includes
- [ ] Все системы размещены хотя бы в одном environment

### Метаданные
- [ ] Все элементы имеют `description`
- [ ] Все системы имеют `technology`
- [ ] Все системы имеют `#system_{id}` tag
- [ ] `likec4 build` проходит без ошибок и без unresolved references

---

## 10. Anti-patterns

### Не делайте так

| Anti-pattern | Почему плохо | Как правильно |
|-------------|-------------|---------------|
| Один гигантский view со всеми системами и связями | Нечитаемо, >50 элементов | Декомпозиция на landscape + domain + system views |
| БД как subsystem (`core_db = subsystem 'Core DB'`) | БД — это инфраструктура, не бизнес-функция | `core_db` → deployment model как storage node |
| Цвет = команда-владелец | Цвет должен показывать тип, не оргструктуру | Используйте теги и metadata для ownership |
| Dynamic views для sequence диаграмм | Слабая замена PlantUML, аналитики уже пишут их | Используйте PlantUML для sequences |
| `integration_map` — все системы со всеми связями | Паутина, ничего не видно | Domain-scoped integration views |
| Один deployment view = весь ЦОД | Бесполезно для дежурного инженера | Per-system deployment views |
| `technology` пусто на связях | Невозможно понять, как системы общаются | Всегда указывайте протокол |
| Дублирование описания в view и model | Рассинхрон неизбежен | Описание только в model, views — проекции |
