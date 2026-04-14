# Custom Views — как строить произвольные срезы архитектуры

LikeC4 позволяет создавать произвольные view, которые показывают любой срез модели — по тегам, по scope, по явному списку элементов. Это мощный инструмент для ответов на конкретные вопросы: «что в PCI-DSS scope?», «кто владеет данными?», «какие системы затронет отказ X?».

## Когда нужен custom view

- Регуляторный аудит (PCI-DSS, PII, SOX scope)
- Blast radius анализ (что сломается при отказе системы X?)
- Data ownership / data flow
- Team topology (какие системы за какой командой?)
- Migration scope (что затронет миграция?)

## Техники построения

### 1. Explicit include — явный список элементов

Самый простой и предсказуемый способ. Перечисляете нужные элементы и связи:

```
view my_custom_view {
  title 'My Custom Slice'
  include bank.business.payments.payment_hub
  include bank.business.products.core_banking
  include bank.business.payments.payment_hub -> bank.business.products.core_banking
  autoLayout TopBottom
}
```

### 2. Kind filter — фильтр по типу элемента

```
view all_databases {
  title 'All Databases'
  include * where kind is database
  autoLayout TopBottom
}
```

### 3. Tag filter — фильтр по тегу

```
view critical_systems {
  title 'Tier-1 Critical Systems'
  include * where tag is #critical
  autoLayout TopBottom
}
```

### 4. Scope + wildcard — все потомки элемента

```
view payments_deep {
  title 'Payments — Full Depth'
  include bank.business.payments.**
  autoLayout TopBottom
}
```

### 5. Relationship includes — показать связи

```
// Все входящие и исходящие связи элемента
include -> bank.business.payments.payment_hub ->

// Только исходящие
include bank.business.payments.payment_hub -> *

// Конкретная связь
include bank.business.payments.payment_hub -> bank.business.products.core_banking
```

### 6. Style overrides — визуальное выделение

```
style bank.business.payments.card_processing {
  color red
  border solid
}
```

## Примеры в модели

См. `views/compliance.c4`:
- **custom_pci** — PCI-DSS scope (cardholder data environment)
- **custom_data_ownership** — карта владения данными

## Рецепт: создание нового custom view

1. Определите вопрос, на который отвечает view
2. Составьте список элементов, которые нужно показать
3. Добавьте связи между ними (`include A -> B` или `include -> A ->`)
4. При необходимости выделите ключевые элементы через `style`
5. Выберите layout: `autoLayout TopBottom` или `autoLayout LeftRight`
6. Дайте view говорящее имя с префиксом `custom_`
