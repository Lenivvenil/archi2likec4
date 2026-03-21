"""Internationalization: message catalogs for ru/en."""

from __future__ import annotations

# ── QA incident messages ─────────────────────────────────────────────────
# Each entry: (title, description_template, impact, remediation)
# Templates may contain {placeholders} for .format() calls.

_MESSAGES: dict[str, dict[str, dict[str, str]]] = {
    'QA-1': {
        'ru': {
            'title': 'Системы без домена',
            'description': (
                '{count} систем не размещены ни на одной диаграмме '
                'в functional_areas/. Конвертер помещает их в домен «unassigned».'
            ),
            'impact': (
                'Системы не отображаются в доменных views, невозможно '
                'понять их бизнес-принадлежность.'
            ),
            'remediation': (
                '1. Откройте Archi → Views → functional_areas\n'
                '2. Для каждой системы определите целевой домен\n'
                '3. Перетащите элемент на соответствующую диаграмму домена'
            ),
        },
        'en': {
            'title': 'Systems without domain',
            'description': (
                '{count} systems are not placed on any functional_areas/ diagram. '
                'The converter places them in the "unassigned" domain.'
            ),
            'impact': (
                'Systems are not shown in domain views, '
                'their business ownership is unclear.'
            ),
            'remediation': (
                '1. Open Archi → Views → functional_areas\n'
                '2. Determine the target domain for each system\n'
                '3. Drag the element onto the corresponding domain diagram'
            ),
        },
    },
    'QA-2': {
        'ru': {
            'title': 'Незаполненные карточки систем',
            'description': (
                '{count} из {total} систем/подсистем не имеют '
                'ни одного заполненного свойства (CI, Criticality, LC stage и др.).'
            ),
            'impact': (
                'Метаданные в архитектурном портале отображаются как '
                '«TBD» — невозможно оценить критичность, ответственных, стадию ЖЦ.'
            ),
            'remediation': (
                '1. Откройте элемент в Archi → вкладка Properties\n'
                '2. Заполните как минимум: CI, Criticality, Dev team\n'
                '3. Приоритет — системы с наибольшим числом пустых полей'
            ),
        },
        'en': {
            'title': 'Incomplete system cards',
            'description': (
                '{count} of {total} systems/subsystems have no filled properties '
                '(CI, Criticality, LC stage, etc.).'
            ),
            'impact': (
                'Metadata in the architecture portal shows as "TBD" — '
                'criticality, ownership, and lifecycle stage are unknown.'
            ),
            'remediation': (
                '1. Open the element in Archi → Properties tab\n'
                '2. Fill in at least: CI, Criticality, Dev team\n'
                '3. Prioritize systems with the most empty fields'
            ),
        },
    },
    'QA-3': {
        'ru': {
            'title': 'Системы на разборе',
            'description': (
                'Эти системы находятся в папке !РАЗБОР — '
                'их статус в модели не определён.'
            ),
            'impact': (
                'Системы помечены тегом #to_review и требуют '
                'решения: оставить в модели или удалить.'
            ),
            'remediation': (
                '1. Для каждой системы определите, является ли она актуальной\n'
                '2. Если актуальна — переместите из !РАЗБОР в правильную папку\n'
                '3. Если не актуальна — удалите элемент из модели'
            ),
        },
        'en': {
            'title': 'Systems under review',
            'description': (
                'These systems are in the review folder — '
                'their status in the model is undefined.'
            ),
            'impact': (
                'Systems are tagged #to_review and need a decision: '
                'keep in the model or remove.'
            ),
            'remediation': (
                '1. Determine if each system is still relevant\n'
                '2. If relevant — move from the review folder to the correct one\n'
                '3. If not relevant — delete the element from the model'
            ),
        },
    },
    'QA-4': {
        'ru': {
            'title': 'Кандидаты на декомпозицию',
            'description': (
                '{count} систем имеют ≥{threshold} '
                'подсистем — вероятно, их дочерние компоненты являются '
                'самостоятельными микросервисами.'
            ),
            'impact': (
                'Интеграции всех подсистем схлопываются в одну стрелку '
                'родителя, теряется детализация.'
            ),
            'remediation': (
                '1. Добавьте систему в promote_children в .archi2likec4.yaml\n'
                '2. Укажите целевой домен: promote_children: {{ "Parent": "domain" }}\n'
                '3. Перезапустите конвертер — подсистемы станут самостоятельными системами'
            ),
        },
        'en': {
            'title': 'Decomposition candidates',
            'description': (
                '{count} systems have ≥{threshold} subsystems — '
                'their children are likely independent microservices.'
            ),
            'impact': (
                'All subsystem integrations collapse into a single parent arrow, '
                'losing detail.'
            ),
            'remediation': (
                '1. Add the system to promote_children in .archi2likec4.yaml\n'
                '2. Specify the target domain: promote_children: {{ "Parent": "domain" }}\n'
                '3. Re-run the converter — subsystems become standalone systems'
            ),
        },
    },
    'QA-5': {
        'ru': {
            'title': 'Системы без документации',
            'description': 'Эти системы не имеют описания в поле documentation.',
            'impact': (
                'В архитектурном портале отсутствует описание назначения '
                'системы — затруднено понимание её роли.'
            ),
            'remediation': (
                '1. Откройте элемент в Archi → поле Documentation\n'
                '2. Добавьте краткое описание назначения системы (1-2 предложения)'
            ),
        },
        'en': {
            'title': 'Systems without documentation',
            'description': 'These systems have no description in the documentation field.',
            'impact': (
                'The architecture portal lacks a description of the system\'s purpose — '
                'understanding its role is difficult.'
            ),
            'remediation': (
                '1. Open the element in Archi → Documentation field\n'
                '2. Add a brief description of the system\'s purpose (1-2 sentences)'
            ),
        },
    },
    'QA-6': {
        'ru': {
            'title': 'Осиротевшие функции',
            'description': (
                '{count} ApplicationFunction не имеют привязки '
                'к родительскому ApplicationComponent.'
            ),
            'impact': (
                'Функции не отображаются ни в одной системе — '
                'потеряна часть функциональной архитектуры.'
            ),
            'remediation': (
                '1. Найдите осиротевшие функции в Archi (--verbose)\n'
                '2. Добавьте CompositionRelationship к целевому ApplicationComponent\n'
                '3. Или переместите XML-файл функции в папку целевого компонента'
            ),
        },
        'en': {
            'title': 'Orphan functions',
            'description': (
                '{count} ApplicationFunction elements are not linked '
                'to a parent ApplicationComponent.'
            ),
            'impact': (
                'Functions are not shown in any system — '
                'part of the functional architecture is lost.'
            ),
            'remediation': (
                '1. Find orphan functions in Archi (--verbose)\n'
                '2. Add a CompositionRelationship to the target ApplicationComponent\n'
                '3. Or move the function XML file to the target component folder'
            ),
        },
    },
    'QA-7': {
        'ru': {
            'title': 'Потерянные интеграции',
            'description': (
                '{skipped} из {total} интеграционных связей '
                '({pct}%) не удалось разрешить — один или оба endpoint не найдены.'
            ),
            'impact': (
                'Часть интеграций между системами не отображается — '
                'неполная картина взаимодействий.'
            ),
            'remediation': (
                '1. Запустите конвертер с --verbose для детального лога\n'
                '2. Проверьте, что source и target — валидные ApplicationComponent\n'
                '3. Убедитесь, что связи не ведут на удалённые элементы'
            ),
        },
        'en': {
            'title': 'Lost integrations',
            'description': (
                '{skipped} of {total} integration relationships '
                '({pct}%) could not be resolved — one or both endpoints not found.'
            ),
            'impact': (
                'Some integrations between systems are not shown — '
                'incomplete interaction picture.'
            ),
            'remediation': (
                '1. Run the converter with --verbose for detailed logs\n'
                '2. Check that source and target are valid ApplicationComponents\n'
                '3. Make sure relationships don\'t point to deleted elements'
            ),
        },
    },
    'QA-8': {
        'ru': {
            'title': 'Покрытие solution views',
            'description': (
                '{unresolved} из {total} элементов на solution-диаграммах '
                'не удалось сопоставить с C4-моделью (разрешено {resolved}, '
                'не разрешено {unresolved}).'
            ),
            'impact': (
                'Solution views могут отображать неполную картину — '
                'часть элементов диаграмм теряется при конвертации.'
            ),
            'remediation': (
                '1. Проверьте, что все элементы — валидные ApplicationComponent\n'
                '2. Удалите элементы других типов (BusinessService и т.д.)\n'
                '3. Убедитесь, что элементы не «призраки» удалённых компонентов'
            ),
        },
        'en': {
            'title': 'Solution view coverage',
            'description': (
                '{unresolved} of {total} elements on solution diagrams '
                'could not be mapped to the C4 model (resolved {resolved}, '
                'unresolved {unresolved}).'
            ),
            'impact': (
                'Solution views may show an incomplete picture — '
                'some diagram elements are lost during conversion.'
            ),
            'remediation': (
                '1. Check that all elements are valid ApplicationComponents\n'
                '2. Remove elements of other types (BusinessService, etc.)\n'
                '3. Make sure elements are not "ghosts" of deleted components'
            ),
        },
    },
    'QA-9': {
        'ru': {
            'title': 'Системы без инфраструктурной привязки',
            'description': (
                '{count} систем не имеют связи с инфраструктурными '
                'нодами (Node, SystemSoftware).'
            ),
            'impact': 'На deployment view не видно, где развёрнуты эти системы.',
            'remediation': (
                '1. Откройте систему в Archi\n'
                '2. Создайте RealizationRelationship к целевому Node\n'
                '3. Или добавьте AssignmentRelationship'
            ),
        },
        'en': {
            'title': 'Systems without infrastructure mapping',
            'description': (
                '{count} systems have no relationship to infrastructure '
                'nodes (Node, SystemSoftware).'
            ),
            'impact': 'The deployment view does not show where these systems are deployed.',
            'remediation': (
                '1. Open the system in Archi\n'
                '2. Create a RealizationRelationship to the target Node\n'
                '3. Or add an AssignmentRelationship'
            ),
        },
    },
    'QA-10': {
        'ru': {
            'title': 'Проблемы иерархии развёртывания',
            'description': (
                '{count} проблем в deployment-топологии: '
                'плавающее ПО, пустые Location, ноды без привязки к Location.'
            ),
            'impact': (
                'Deployment view показывает неструктурированную топологию — '
                'невозможно определить физическое размещение.'
            ),
            'remediation': (
                '1. SystemSoftware должен быть вложен в Node (AggregationRelationship)\n'
                '2. Location должен содержать хотя бы один Node\n'
                '3. Root Node должен быть вложен в Location\n'
                '4. Leaf-ноды (ПО/хранилище) не должны содержать дочерних элементов\n'
                '5. Глубина вложенности не должна превышать 6 уровней\n'
                '6. Один элемент не должен появляться в нескольких ветках дерева'
            ),
        },
        'en': {
            'title': 'Deployment hierarchy issues',
            'description': (
                '{count} issues in the deployment topology: '
                'floating software, empty Locations, nodes not under a Location.'
            ),
            'impact': (
                'The deployment view shows an unstructured topology — '
                'physical placement cannot be determined.'
            ),
            'remediation': (
                '1. SystemSoftware must be nested in a Node (AggregationRelationship)\n'
                '2. Location must contain at least one Node\n'
                '3. Root Node must be nested in a Location\n'
                '4. Leaf nodes (infraSoftware) must not have children\n'
                '5. Nesting depth must not exceed 6 levels\n'
                '6. An element must not appear in multiple tree branches'
            ),
        },
    },
}

# QA-10 sub-issue labels
_QA10_ISSUES: dict[str, dict[str, str]] = {
    'floating_sw': {
        'ru': 'SystemSoftware как root-нод (плавающее ПО)',
        'en': 'SystemSoftware as root node (floating software)',
    },
    'empty_location': {
        'ru': 'Location без дочерних нод',
        'en': 'Location without child nodes',
    },
    'root_no_location': {
        'ru': 'Root Node без привязки к Location',
        'en': 'Root Node not under a Location',
    },
    'leaf_with_children': {
        'ru': 'Leaf-нод (ПО/хранилище) содержит дочерние элементы',
        'en': 'Leaf node (infraSoftware) has children',
    },
    'excessive_depth': {
        'ru': 'Чрезмерная глубина вложенности (>6 уровней)',
        'en': 'Excessive nesting depth (>6 levels)',
    },
    'duplicate_archi_id': {
        'ru': 'Дублирование archi_id в разных ветках дерева',
        'en': 'Duplicate archi_id across different tree branches',
    },
}

# ── AUDIT.md header/summary labels ──────────────────────────────────────

_AUDIT_HEADER: dict[str, dict[str, str]] = {
    'title': {
        'ru': 'Реестр инцидентов качества ArchiMate-модели',
        'en': 'ArchiMate Model Quality Incident Register',
    },
    'auto_generated': {
        'ru': 'Автоматически сгенерировано archi2likec4 v{version}, {date}.',
        'en': 'Automatically generated by archi2likec4 v{version}, {date}.',
    },
    'fix_prompt': {
        'ru': 'Исправьте находки в ArchiMate-модели и перезапустите конвертер.',
        'en': 'Fix findings in the ArchiMate model and re-run the converter.',
    },
    'summary_heading': {
        'ru': 'Сводка',
        'en': 'Summary',
    },
}

_SUMMARY_LABELS: dict[str, dict[str, str]] = {
    'systems': {'ru': 'Систем', 'en': 'Systems'},
    'subsystems': {'ru': 'Подсистем', 'en': 'Subsystems'},
    'meta_completeness': {'ru': 'Заполненность метаданных', 'en': 'Metadata completeness'},
    'domain_assigned': {'ru': 'С доменом', 'en': 'With domain'},
    'integrations': {'ru': 'Интеграций', 'en': 'Integrations'},
    'data_entities': {'ru': 'Data-сущностей', 'en': 'Data entities'},
    'deploy_mappings': {'ru': 'Deploy-маппингов', 'en': 'Deploy mappings'},
    'metric': {'ru': 'Метрика', 'en': 'Metric'},
    'value': {'ru': 'Значение', 'en': 'Value'},
    # AUDIT.md table and footer labels
    'problem': {'ru': 'Проблема', 'en': 'Problem'},
    'impact_label': {'ru': 'Влияние', 'en': 'Impact'},
    'recommendation': {'ru': 'Рекомендация', 'en': 'Recommendation'},
    'no_incidents': {'ru': 'Инцидентов качества не обнаружено.', 'en': 'No quality incidents found.'},
    'suppressed_note': {
        'ru': ' Исключено из отчёта (audit_suppress): {count} элементов.',
        'en': ' Excluded from report (audit_suppress): {count} elements.',
    },
    'suppressed_qa_note': {
        'ru': ' Подавлены по QA-ID: {ids}.',
        'en': ' Suppressed by QA-ID: {ids}.',
    },
    'footer': {
        'ru': 'Всего инцидентов: {qa_num}.{suppress_note} Сгенерировано archi2likec4 v{version}.',
        'en': 'Total incidents: {qa_num}.{suppress_note} Generated by archi2likec4 v{version}.',
    },
    'shown_first': {
        'ru': ' (показаны первые {n} из {total})',
        'en': ' (showing first {n} of {total})',
    },
    'field_completeness': {
        'ru': 'Заполненность по полям',
        'en': 'Completeness by field',
    },
    'top_systems': {
        'ru': 'Топ-{n} систем с максимальным числом пустых полей',
        'en': 'Top {n} systems with most empty fields',
    },
    # Table column headers
    'col_num': {'ru': '#', 'en': '#'},
    'col_system': {'ru': 'Система', 'en': 'System'},
    'col_tags': {'ru': 'Теги', 'en': 'Tags'},
    'col_domain': {'ru': 'Домен', 'en': 'Domain'},
    'col_subsystems': {'ru': 'Подсистем', 'en': 'Subsystems'},
    'col_field': {'ru': 'Поле', 'en': 'Field'},
    'col_filled': {'ru': 'Заполнено', 'en': 'Filled'},
    'col_empty_fields': {'ru': 'Пустых полей', 'en': 'Empty fields'},
    'col_element': {'ru': 'Элемент', 'en': 'Element'},
    'col_kind': {'ru': 'Kind', 'en': 'Kind'},
    'col_issue': {'ru': 'Проблема', 'en': 'Issue'},
    'subdomain': {'ru': 'Субдомен', 'en': 'Subdomain'},
    'subdomain_plural': {'ru': 'Субдомены', 'en': 'Subdomains'},
    'l2_subdomain_label': {'ru': 'Субдомен (L2)', 'en': 'Subdomain (L2)'},
}


# ── Web UI strings ───────────────────────────────────────────────────────

WEB_MESSAGES: dict[str, dict[str, str]] = {
    'title': {'ru': 'Аудит качества', 'en': 'Quality Audit'},
    'dashboard': {'ru': 'Панель аудита качества', 'en': 'Quality Audit Dashboard'},
    'systems': {'ru': 'Системы', 'en': 'Systems'},
    'subsystems': {'ru': 'Подсистемы', 'en': 'Subsystems'},
    'metadata': {'ru': 'Метаданные', 'en': 'Metadata'},
    'with_domain': {'ru': 'С доменом', 'en': 'With Domain'},
    'integrations': {'ru': 'Интеграции', 'en': 'Integrations'},
    'deploy_maps': {'ru': 'Deploy-маппинги', 'en': 'Deploy Maps'},
    'suppressed': {'ru': 'Скрыто', 'en': 'Suppressed'},
    'remediations': {'ru': 'Ремедиации', 'en': 'Remediations'},
    'review_all': {'ru': 'Обзор всех', 'en': 'Review all'},
    'incidents': {'ru': 'Инциденты', 'en': 'Incidents'},
    'severity': {'ru': 'Серьёзность', 'en': 'Severity'},
    'incident': {'ru': 'Инцидент', 'en': 'Incident'},
    'count': {'ru': 'Кол-во', 'en': 'Count'},
    'actions': {'ru': 'Действия', 'en': 'Actions'},
    'details': {'ru': 'Подробнее', 'en': 'Details'},
    'suppress': {'ru': 'Скрыть', 'en': 'Suppress'},
    'unsuppress': {'ru': 'Показать', 'en': 'Unsuppress'},
    'no_incidents': {'ru': 'Инцидентов качества не найдено.', 'en': 'No quality incidents found.'},
    'hierarchy': {'ru': 'Иерархия', 'en': 'Hierarchy'},
    'refresh': {'ru': 'Обновить', 'en': 'Refresh'},
    'back': {'ru': 'Назад к панели', 'en': 'Back to dashboard'},
    'problem': {'ru': 'Проблема', 'en': 'Problem'},
    'impact': {'ru': 'Влияние', 'en': 'Impact'},
    'remediation': {'ru': 'Рекомендация', 'en': 'Remediation'},
    'affected': {'ru': 'Затронутые элементы', 'en': 'Affected Elements'},
    'action': {'ru': 'Действие', 'en': 'Action'},
    'assign': {'ru': 'Назначить', 'en': 'Assign'},
    'mark_reviewed': {'ru': 'Проверено', 'en': 'Mark reviewed'},
    'promote': {'ru': 'Промоутить', 'en': 'Promote'},
    'undo': {'ru': 'Отменить', 'en': 'Undo'},
    'hidden_by_suppress': {
        'ru': 'элемент(ов) скрыто через audit_suppress.',
        'en': 'element(s) hidden by audit_suppress.',
    },
    'remed_review': {'ru': 'Обзор ремедиаций', 'en': 'Remediations Review'},
    'remed_subtitle': {
        'ru': 'Все конфиг-решения для этой конвертации',
        'en': 'All config-driven decisions for this conversion',
    },
    'domain_overrides': {'ru': 'Назначения доменов', 'en': 'Domain Overrides'},
    'reviewed_systems': {'ru': 'Проверенные системы', 'en': 'Reviewed Systems'},
    'promoted_children': {'ru': 'Промоутированные', 'en': 'Promoted Children'},
    'suppressed_systems': {'ru': 'Скрытые системы', 'en': 'Suppressed Systems'},
    'suppressed_incidents': {'ru': 'Скрытые инциденты', 'en': 'Suppressed Incidents'},
    'no_remed': {'ru': 'Ремедиации ещё не настроены.', 'en': 'No remediations configured yet.'},
    'system_hierarchy': {'ru': 'Иерархия систем', 'en': 'System Hierarchy'},
    'system': {'ru': 'Система', 'en': 'System'},
    'domain': {'ru': 'Домен', 'en': 'Domain'},
    'parent': {'ru': 'Родитель', 'en': 'Parent'},
    'dark_mode': {'ru': 'Тёмная тема', 'en': 'Dark mode'},
    'light_mode': {'ru': 'Светлая тема', 'en': 'Light mode'},
    'subdomain': {'ru': 'Субдомен', 'en': 'Subdomain'},
}


def get_web_msg(key: str, lang: str = 'ru') -> str:
    """Get a localized web UI string."""
    entry = WEB_MESSAGES.get(key, {})
    return entry.get(lang, entry.get('ru', key))


def get_msg(qa_id: str, field: str, lang: str = 'ru', **kwargs: object) -> str:
    """Get a localized message for a QA incident field.

    Args:
        qa_id: QA incident identifier (e.g. 'QA-1')
        field: Message field ('title', 'description', 'impact', 'remediation')
        lang: Language code ('ru' or 'en')
        **kwargs: Format placeholders for the message template
    """
    msgs = _MESSAGES.get(qa_id, {})
    lang_msgs = msgs.get(lang, msgs.get('ru', {}))
    template = lang_msgs.get(field, '')
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def get_qa10_issue(issue_key: str, lang: str = 'ru') -> str:
    """Get localized QA-10 sub-issue label."""
    return _QA10_ISSUES.get(issue_key, {}).get(lang, issue_key)


def get_audit_label(key: str, lang: str = 'ru', **kwargs: object) -> str:
    """Get localized audit header/summary label."""
    entry = _AUDIT_HEADER.get(key) or _SUMMARY_LABELS.get(key, {})
    template = entry.get(lang, entry.get('ru', key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template
