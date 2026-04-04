# demo-bank: Эталонная референсная модель LikeC4

Синтетический архитектурный репозиторий банка. 5 систем, 2 домена, 2 ЦОДа, 8 VM.
Демонстрирует все паттерны целевой структуры для обучения агентов и архитекторов.

## Что демонстрирует эта модель

### 1. Структура «два файла на систему»
Каждая система — директория с `model.c4` (логика) и `deployment.c4` (физика).
Агент всегда знает, какой файл открыть.

### 2. Shared infrastructure через extend
VM объявлены один раз в `infrastructure/`. Системы расширяют нужные VM:
```
// infrastructure/dc_main.c4    — объявляет vm db_01
// systems/mobile_bank/deployment.c4  — extend prod.dc_main.data_zone.db_01 { instanceOf ... }
// systems/core_banking/deployment.c4 — extend prod.dc_main.data_zone.db_01 { instanceOf ... }
```
Одна VM, два файла, два extend — LikeC4 мержит автоматически.

### 3. Deployment views без exclude
Targeted includes по конкретным VM-путям. Никакой tag-фильтрации:
```likec4
deployment view mobile_bank_prod {
  include prod.dc_main.dmz.web_01.**
  include prod.dc_main.app_zone.app_01.**
  include prod.dc_main.data_zone.db_01.**
}
```

### 4. Domain → System → Subsystem через extend-цепочку
```
domains/channels.c4           — system mobile_bank 'Мобильный банк'
systems/mobile_bank/model.c4  — extend channels.mobile_bank { rest_api = service ... }
```

### 5. Связи во владении SOURCE-системы
Все исходящие интеграции — в `model.c4` системы-источника:
```
// systems/mobile_bank/model.c4
channels.mobile_bank -> products.core_banking 'проверка баланса'
channels.mobile_bank -> products.anti_fraud 'проверка транзакции'
```

### 6. Shared VM видна в нескольких deployment views
`db_01` содержит БД трёх систем (МБ, АБС, карты). Каждая система включает
`prod.dc_main.data_zone.db_01.**` в своём view — и видит ВСЕ компоненты на VM,
но view показывает контекст именно этой VM, а не всю инфраструктуру.

### 7. DR-реплики
Резервный ЦОД содержит DR-инстансы с переопределённым стилем:
```likec4
extend prod.dc_dr.app_zone.app_dr_01 {
  mb_api_dr = instanceOf channels.mobile_bank.rest_api {
    title 'МБ REST API (DR)'
    style { color amber }
  }
}
```

## Размеры файлов

| Файл | Строки | Назначение |
|------|--------|------------|
| specification.c4 | 97 | Словарь модели |
| infrastructure/dc_main.c4 | 64 | Основной ЦОД |
| infrastructure/dc_dr.c4 | 23 | Резервный ЦОД |
| domains/channels.c4 | 23 | Домен «Каналы» |
| domains/products.c4 | 40 | Домен «Продукты» + external |
| systems/*/model.c4 | 42-58 | Подсистемы + связи |
| systems/*/deployment.c4 | 32-56 | Deployment + views |
| views/landscape.c4 | 35 | Кросс-системные views |
| **Среднее** | **~40** | |
| **Максимум** | **97** | |

Все файлы < 100 строк. Агент читает один файл за один вызов.

## Карта интеграций

```
Мобильный банк ──sync──▶ АБС ──async──▶ Карточный процессинг ──sync──▶ Mastercard
       │                                          │
       │──sync──▶ Карточный процессинг             │
       │                                          │
       │──async─▶ Центр уведомлений ◀──async──────┘
       │                  │
       │──sync──▶ Антифрод │──async──▶ SMS-провайдер
                  │
                  └──async─▶ Центр уведомлений
```

## Карта deployment (shared VM)

```
dc_main/dmz/web_01:       МБ.web_app
dc_main/app_zone/app_01:  МБ.rest_api, МБ.push_service, Карты.gateway, Карты.hsm
dc_main/app_zone/app_02:  АБС.accounts, АБС.payments
dc_main/app_zone/app_03:  Уведомления.dispatcher/sms/push, Антифрод.scoring/rules
dc_main/data_zone/db_01:  МБ.db, АБС.core_db, Карты.card_db  ← shared!
dc_main/data_zone/mq_01:  АБС.core_mq, Уведомления.queue, Антифрод.fraud_db/stream
dc_dr/app_zone/app_dr_01: МБ.rest_api(DR), Карты.gateway(DR)
```

## Как использовать

### Для обучения агента
Скопировать в проект как `reference/` и указать в CLAUDE.md:
```
Используй reference/ как эталон структуры при создании новых систем.
```

### Для валидации
```bash
cd reference-model && npx likec4 build
```

### Как шаблон новой системы
```bash
cp -r systems/notification_hub systems/new_system
# Отредактировать model.c4 и deployment.c4
```
