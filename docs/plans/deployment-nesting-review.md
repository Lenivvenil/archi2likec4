# Plan: Deployment Nesting Correctness Review

## Overview
Глубокое ревью корректности формирования вложенности объектов на deployment-диаграммах. Проект прошёл через 11 инцидентов качества: от 219 orphan-нод (visual nesting enrichment), ложной классификации infraSoftware vs dataStore, wildcard expansion в deployment views, до QA-9/QA-10 валидации. Задача — системно проверить, что все эти договорённости выполняются корректно: парсинг visual nesting из canvas XML, обогащение топологии, kind-assignment, формирование qualified c4-путей в mapping, генерация topology.c4 и deployment solution views. Исправить найденные дефекты и усилить покрытие тестами.

## Validation Commands
- `python -m pytest tests/ -x -q`
- `python -m ruff check archi2likec4/ --select E,F,W`
- `python -c "from archi2likec4 import pipeline; print('import ok')"`

---

### Task 1: Audit Visual Nesting Extraction and Enrichment
Проверить корректность двух ключевых механизмов: (1) извлечения parent→child пар из `<children>` элементов canvas XML в `_extract_visual_nesting()` и (2) обогащения топологии в `enrich_deployment_from_visual_nesting()`. Именно здесь была главная проблема проекта — 219 из 424 элементов были orphan до обогащения, после — 14. Нужно убедиться, что оставшиеся orphan действительно не имеют родителя, а не пропущены парсером.

- [x] Прочитать `archi2likec4/parsers.py`, функцию `_extract_visual_nesting()` (строки 166–186) — проверить: (a) обрабатываются ли вложенные `<children>` с пропущенным `archimateElement` href (т.е. group/note элементы на canvas); (b) если `child_id is None`, текущий `parent_id` прокидывается вглубь — убедиться, что промежуточные group-контейнеры не теряют вложенные tech-элементы; (c) написать тест `test_visual_nesting_through_group_container` — group без archi_id оборачивает два Node, оба должны получить parent_id от grandparent
- [x] Прочитать `archi2likec4/builders/deployment.py`, функцию `enrich_deployment_from_visual_nesting()` (строки 102–159) — проверить: (a) фильтр `child_aid not in root_ids` отсекает уже вложенные через AggregationRelationship ноды — а что если AggregationRelationship вложил ноду НЕПРАВИЛЬНО, а visual nesting показывает правильного родителя? Сейчас visual nesting не может исправить ошибку AggregationRelationship; (b) при конфликте нескольких диаграмм (`first wins`) — корректен ли порядок `parsed.solution_views`? Он зависит от `sorted(diagrams_dir.rglob(...))`, т.е. от имени файла. Написать тест `test_first_diagram_wins_on_conflict` с двумя диаграммами, предлагающими разных родителей для одного элемента
- [x] Добавить диагностический лог в pipeline: после enrichment вывести список оставшихся root-нод с `kind != infraLocation` (т.е. orphan `infraNode`/`infraSoftware` без Location-родителя) — это кандидаты на пропущенное visual nesting. В `archi2likec4/pipeline.py` после строки 262 добавить `logger.info` с именами orphan-нод
- [x] Add/update tests (`tests/test_builders.py`):
  - `test_visual_nesting_through_group_container` (парсер: group без archi_id не теряет вложенные элементы)
  - `test_first_diagram_wins_on_conflict` (enrichment: два conflicting visual nesting, первый побеждает)
  - `test_already_nested_by_aggregation_skipped` (enrichment: уже вложенный через AggregationRelationship не перевешивается)
  - `test_enrichment_counts_match` (enrichment: возвращаемый count = фактическое количество перемещённых нод)
- [x] Mark completed

---

### Task 2: Audit Kind Assignment and DataStore Detection
Проверить корректность присвоения kind (`infraLocation`, `infraZone`, `infraNode`, `infraSoftware`, `dataStore`) в `build_deployment_topology()`. Исторически dataStore детекция была добавлена как fix — проверить, что паттерн `_DATASTORE_PATTERNS` покрывает реальные БД в модели и не даёт false positives. Проверить, что TechElement с неизвестным `tech_type` (не из `_INFRA_NODE_TYPES`, `_INFRA_ZONE_TYPES`, `_INFRA_SW_TYPES`, не `Location`) не падает, а получает fallback kind.

- [x] Прочитать `archi2likec4/builders/deployment.py` строки 56–69 (kind assignment) — проверить: (a) что происходит, если `tech_type` не `Location` и не входит ни в один frozenset? Сейчас fallback — `infraSoftware`. Это корректно? Или лучше `infraNode`? Зафиксировать решение в комментарии; (b) что если `tech_type in _INFRA_NODE_TYPES` И имя содержит DB-паттерн (например, Node с именем "PostgreSQL cluster")? Сейчас Node ВСЕГДА → `infraNode`. Это правильно по договорённости: Node/Device — всегда контейнер, не хранилище
- [x] Прочитать `archi2likec4/parsers.py`, функцию `parse_technology_elements()` — убедиться, что все реально встречающиеся `xsi:type` значения покрыты. Проверить, что элементы с типом `TechnologyFunction`, `TechnologyProcess`, `TechnologyInteraction` (если есть в реальной модели) не теряются молча — сейчас они создают TechElement, попадают в builder и получают fallback `infraSoftware`. Добавить `logger.debug` для неизвестных типов
- [x] Расширить `_DATASTORE_PATTERNS` при необходимости: запустить конвертер с `--verbose`, проверить реальные имена всех `infraSoftware` в output — если среди них есть БД, пропущенные паттерном (например, `RabbitMQ`, `Kafka`, `MinIO`, `S3`), добавить. Если нет — зафиксировать, что паттерн полон
- [x] Add/update tests (`tests/test_builders.py`):
  - `test_unknown_tech_type_fallback_kind` — элемент с `tech_type='TechnologyFunction'` получает `infraSoftware` (или что решим)
  - `test_node_named_like_db_stays_infranode` — Node с именем "PostgreSQL Cluster" → `infraNode`, не `dataStore`
  - `test_datastore_detection_case_variations` — "POSTGRESQL", "postgreSQL", "PostgreSQL" — все → `dataStore`
  - `test_datastore_false_negative_check` — список реальных имён из модели, которые ДОЛЖНЫ быть `infraSoftware` (Nginx, Eureka, Consul и т.д.)
- [x] Mark completed

---

### Task 3: Audit Deployment Mapping Paths and Cross-References
Проверить корректность qualified c4-путей в `deployment/mapping.c4`. Mapping связывает app-сторону (`domain.subdomain.system.subsystem`) с infra-стороной (`location.cluster.node`). После введения 5-уровневой иерархии (subdomain) пути изменились — убедиться, что subdomain корректно учитывается в обеих сторонах mapping. Также проверить, что все пути в mapping действительно разрешаются в элементы из `topology.c4` и `domains/*.c4`.

- [ ] Прочитать `archi2likec4/builders/deployment.py`, функцию `build_deployment_map()` (строки 195–260) — проверить: (a) app-сторона: `f'{domain}.{subdomain}.{sys.c4_id}'` — а если subdomain пустая строка `''`? Сейчас `if subdomain` предотвращает `domain..system`, проверить тестом; (b) subsystem path строится как `f'{full}.{sub.c4_id}'` — а если subsystem также имеет subdomain? Убедиться что subdomain применяется только на уровне system; (c) infra-сторона: `_build_deployment_path_index()` строит qualified paths через рекурсию с prefix — проверить, что prefix для root нод не содержит лишней точки
- [ ] Прочитать `_build_deployment_path_index()` (строки 172–185) — проверить условие `f'{prefix}{node.c4_id}' if not prefix else f'{prefix}.{node.c4_id}'` — тут ошибка: когда prefix пустой, используется `f'{prefix}{node.c4_id}'` что правильно (`''` + id = id), но когда prefix НЕ пустой, используется `f'{prefix}.{node.c4_id}'` — тоже правильно. Но: проверить, что при первом вызове передаётся `prefix=''` (по умолчанию), а не `prefix=None`
- [ ] Добавить валидацию в pipeline (`_validate` или post-generation): пройтись по всем парам в `deployment_map` и проверить, что infra-путь (правая сторона) действительно существует в `tech_archi_to_c4` values. Если путь не разрешается — `logger.warning('Dangling deployment mapping: %s -> %s')`. Это поймает рассинхронизации между topology и mapping
- [ ] Add/update tests (`tests/test_builders.py`):
  - `test_deployment_map_with_subdomain_path` — system с subdomain → mapping путь `domain.subdomain.system`
  - `test_deployment_map_without_subdomain_no_double_dot` — system без subdomain → `domain.system`, не `domain..system`
  - `test_deployment_path_index_root_no_prefix` — root node → c4_id без точки-prefix
  - `test_deployment_path_index_nested_qualified` — вложенный node → `parent.child` qualified path
  - `test_deployment_map_subsystem_inherits_subdomain` — subsystem mapping включает subdomain system-родителя
- [ ] Mark completed

---

### Task 4: Audit Deployment Solution Views and QA-10 Coverage
Проверить генерацию deployment solution views — исторически были проблемы с wildcard expansion (`.* ` убрано), с include-путями и с тем, что deployment views должны показывать infra-элементы из `deployment_map`, а не только прямые element_archi_ids. Проверить и усилить QA-10 (deployment hierarchy issues): сейчас он ловит 3 паттерна — floating software, empty location, root node without location. Добавить недостающие паттерны.

- [ ] Прочитать `archi2likec4/generators/solution_views.py` (или где генерируются solution views) — найти обработку `view_type == 'deployment'`. Проверить: (a) include-элементы — используются ли `tech_archi_to_c4` для разрешения infra-путей? (b) если deployment view содержит только app-элементы, берутся ли их infra-targets из `deployment_map`? Написать тест если не покрыто; (c) не осталось ли `.*` wildcard expansion — поискать `Grep` по `*` в генераторах
- [ ] Прочитать `archi2likec4/audit_data.py` строки 317–368 (QA-10) — проверить полноту проверок. Добавить: (a) Check 4: infraSoftware/dataStore с children (leaf node, у которого есть дети — нарушение модели); (b) Check 5: глубина вложенности > 6 уровней (вероятно ошибка парсинга/enrichment); (c) Check 6: дублирование archi_id в разных ветках дерева (один элемент появляется и как child location_A, и как child location_B)
- [ ] Убедиться, что QA-10 check 3 ("root Node/Zone not under Location") корректно работает с учётом того, что `location_child_ids` собирает только ПРЯМЫХ children Location — infraNode может быть вложен через промежуточный infraNode, который сам вложен в Location. Сейчас такой infraNode попадёт в root list как "не под Location", хотя он вложен через цепочку. Проверить и исправить если нужно
- [ ] Add/update tests:
  - `tests/test_audit_data.py`: `test_qa10_leaf_with_children` — infraSoftware с children вызывает инцидент
  - `tests/test_audit_data.py`: `test_qa10_excessive_depth` — дерево глубиной 7 вызывает инцидент
  - `tests/test_audit_data.py`: `test_qa10_nested_infranode_under_location_ok` — infraNode → infraNode → Location цепочка НЕ вызывает "root without location"
  - `tests/test_generators.py`: `test_deployment_solution_view_includes_infra_from_map` — deployment solution view включает infra-элементы из deployment_map
- [ ] Mark completed

---

### Task 5: End-to-End Validation and Regression Protection
Связать все найденные и исправленные дефекты в сквозную проверку. Добавить post-generation structural validation topology.c4 — пробежать по реальному дереву и поймать нарушения invariants. Убедиться, что все 561+ тестов проходят.

- [ ] Добавить в `archi2likec4/pipeline.py` после генерации `deployment/topology.c4` (строка 506) вызов функции `_validate_deployment_tree(deployment_nodes)` — проверяет invariants на финальном дереве: (a) все leaf-ноды (infraSoftware/dataStore) не имеют children; (b) никакие два узла в дереве не имеют одинаковый archi_id; (c) все c4_id уникальны в пределах каждого уровня вложенности (sibling uniqueness); (d) qualified paths не содержат `..` (double dot от пустого subdomain/prefix)
- [ ] Функцию `_validate_deployment_tree()` разместить в `archi2likec4/builders/deployment.py` — она принимает `list[DeploymentNode]`, возвращает `list[str]` (список описаний нарушений). В pipeline логировать каждое нарушение как `logger.warning`
- [ ] Запустить `python -m pytest tests/ -x -q` — убедиться что все тесты проходят после всех изменений из Tasks 1–4
- [ ] Запустить конвертер на реальных данных (`python3 -m archi2likec4`) — проверить, что: (a) не появились новые WARNING; (b) topology.c4 структурно не изменился (diff минимален или пуст); (c) AUDIT.md не содержит новых QA-10 инцидентов (если содержит — проанализировать, это реальные проблемы или false positives)
- [ ] Запустить `python -m ruff check archi2likec4/ --select E,F,W` — исправить все предупреждения
- [ ] Mark completed
