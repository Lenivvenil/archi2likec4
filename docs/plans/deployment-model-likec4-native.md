# Plan: Deployment Model Migration to LikeC4 Native

## Overview
Мигрировать деплой-диаграммы с устаревшего подхода (`element` + `deployedOn` relationship в `model {}`)
на нативный LikeC4 Deployment Model (`deployment { environment { node { instanceOf } } }`).
Цель: инфра-узлы становятся `deploymentNode`, приложения размещаются внутри серверов/VM через `instanceOf`,
а не вложены в домены — что делает деплой-диаграмму читаемой и поддерживаемой.

## Validation Commands
- `python -m pytest tests/ -v --tb=short`
- `ruff check archi2likec4/ tests/`
- `mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Replace element infra kinds with deploymentNode in specification

Заменить `element infraNode/infraSoftware/infraZone/infraLocation` на `deploymentNode` в спецификации и
удалить `relationship deployedOn`, который заменяется механизмом `instanceOf`.

- [x] В `archi2likec4/generators/spec.py` заменить все четыре блока `element infraNode/infraSoftware/infraZone/infraLocation` на `deploymentNode infraNode/infraSoftware/infraZone/infraLocation`
- [x] Удалить блок `relationship deployedOn { color archi-tech; line dashed }` из той же функции
- [x] В `archi2likec4/builders/deployment.py` изменить присвоение `kind = 'dataStore'` для DB-паттерна SystemSoftware → `kind = 'infraSoftware'`; обновить `_LEAF_KINDS = frozenset({'infraSoftware'})`
- [x] В `archi2likec4/builders/data.py` (`build_datastore_entity_links`): убрать ранний выход по `kind == 'dataStore'`, так как DB-ноды теперь `infraSoftware`; убрать неиспользуемый импорт `flatten_deployment_nodes`
- [x] В `archi2likec4/audit_data.py` заменить `dn.kind in ('infraSoftware', 'dataStore')` → `dn.kind == 'infraSoftware'`
- [x] Обновить тесты: в `tests/test_generators.py` (`TestGenerateSpec_InfraKinds`) все ассерты `'element infra'` → `'deploymentNode infra'`; тест `test_spec_includes_deployed_on` переименовать в `test_spec_no_deployed_on` с проверкой `assert 'deployedOn' not in spec`
- [x] В `tests/test_builders.py` заменить `kind == 'dataStore'` на `kind == 'infraSoftware'` во всех конструкторах `DeploymentNode` и ассертах в классах `TestDataStoreDetection`, `TestBuildDatastoreEntityLinks`, `TestDeploymentTopology`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 2: Rewrite generators/deployment.py to use deployment {} block with instanceOf

Полностью переработать генератор топологии: выходной файл должен использовать синтаксис
`deployment { environment prod { ... } }`, а каждый infra-узел, на который задеплоено приложение,
должен содержать `instanceOf <app_c4_path>`.

- [x] Переписать `_render_deployment_node(node, lines, indent, current_path, instances)`:
  - передавать `current_path` (строка вида `hq.vmware.srv`) через рекурсию
  - для дочернего узла: `child_path = f'{current_path}.{child.c4_id}'`
  - после рендера metadata блока добавить: `for app_path in instances.get(current_path, []): lines.append(f'  instanceOf {app_path}')`
- [x] Переписать `generate_deployment_c4(nodes, deployment_map=None)`:
  - построить обратный индекс `instances: dict[str, list[str]]` из `deployment_map` (`infra_path → [app_paths]`)
  - обернуть в `deployment {\n  environment prod {\n  ...\n  }\n}`
  - корневые ноды: `current_path = node.c4_id`
- [x] Удалить функцию `generate_deployment_mapping_c4()` (файл `deployment/mapping.c4` больше не генерируется)
- [x] Добавить функцию `generate_deployment_overview_view(env='prod') -> str`:
  ```
  views {
    deployment view deployment_architecture {
      title 'Deployment Architecture'
      include prod.**
    }
  }
  ```
- [x] Обновить `archi2likec4/generators/__init__.py`: убрать `generate_deployment_mapping_c4` и `generate_deployment_view` из импортов и `__all__`; добавить `generate_deployment_overview_view`
- [x] Обновить тесты: в `tests/test_generators.py` класс `TestGenerateDeploymentC4` — ассерты `'model {'` → `'deployment {'` и `'environment prod {'`; добавить тесты `test_instance_of_inserted` и `test_instance_of_nested_path`; удалить класс `TestGenerateDeploymentMapping`; класс `TestGenerateDeploymentView` → `TestGenerateDeploymentOverviewView` с проверкой `'deployment view deployment_architecture'` и `'prod.**'`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 3: Update pipeline.py orchestration to pass deployment_map

Обновить оркестратор конвейера: передать `deployment_map` в `generate_deployment_c4`, удалить
генерацию устаревшего `mapping.c4`, заменить вызов `generate_deployment_view` на
`generate_deployment_overview_view`.

- [x] В `archi2likec4/pipeline.py` убрать импорты `generate_deployment_mapping_c4`, `generate_deployment_view`
- [x] Добавить импорт `generate_deployment_overview_view` в `pipeline.py`
- [x] Изменить вызов `generate_deployment_c4(built.deployment_nodes)` → `generate_deployment_c4(built.deployment_nodes, built.deployment_map)`
- [x] Удалить блок генерации `deployment/mapping.c4` (вызов `generate_deployment_mapping_c4`)
- [x] Изменить вызов `generate_deployment_view()` → `generate_deployment_overview_view()`
- [x] Оставить генерацию `deployment/datastore-mapping.c4` (persists — логический уровень, не деплой)
- [x] Обновить лог-сообщение на `'deployment/ (topology + view)'`
- [x] В `tests/test_pipeline_e2e.py` обновить ассерт `'element infraNode' in spec` → `'deploymentNode infraNode' in spec`
- [x] Add/update tests for the above changes
- [x] Mark completed

---

### Task 4: Update views.py deployment branch to generate deployment view syntax

Обновить ветку `sv.view_type == 'deployment'` в `generate_solution_views()`:
генерировать `deployment view` вместо `view`, использовать `prod.<path>.**` для infra-узлов,
убрать app-paths из include (они живут внутри нод через `instanceOf`), дедуплицировать предков.

- [ ] В `archi2likec4/generators/views.py` строки 453–513: изменить `view {view_id}` → `deployment view {view_id}`
- [ ] Убрать добавление `app_paths` в `include` блок (только `infra_paths`)
- [ ] Добавить `prod.{ip}.**` формат для каждого infra пути
- [ ] Изменить логику ancestor dedup: оставлять путь только если нет другого пути, являющегося его предком (`has_ancestor = any(other != ip and ip.startswith(other + '.') for other in infra_set)`); если предок есть — отбросить
- [ ] Добавить guard: эмитировать блок deployment view только если `infra_paths` непустой
- [ ] Убрать `exclude * where kind is dataEntity` из deployment view (не применимо)
- [ ] Обновить detection строки: `'  view ' in content or '  deployment view ' in content`
- [ ] Обновить тесты в `tests/test_generators.py`: `test_deployment_solution_view_includes_infra_from_map` — убрать ассерты на app_paths, добавить ассерты `'prod.dc.server_1.**' in content`; `test_deployment_view_no_wildcard_expansion` переименовать в `test_deployment_view_uses_wildcard_expansion` с проверкой `'prod.<path>.**' in content` и ancestor dedup
- [ ] Add/update tests for the above changes
- [ ] Mark completed
