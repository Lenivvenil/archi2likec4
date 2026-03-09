"""Structured audit data: compute quality incidents as data objects."""

from dataclasses import dataclass, field

from .models import System, Subsystem, _STANDARD_KEYS


@dataclass
class AuditSummary:
    """High-level model metrics."""
    total_systems: int = 0
    total_subsystems: int = 0
    meta_completeness_pct: int = 0
    assigned_count: int = 0
    total_integrations: int = 0
    total_entities: int = 0
    deployment_mappings: int = 0


@dataclass
class AuditIncident:
    """A single quality audit incident (QA-1 … QA-9)."""
    qa_id: str                           # "QA-1"
    severity: str                        # "Critical" | "High" | "Medium" | "Low"
    title: str                           # "Системы без домена"
    count: int                           # affected items count
    description: str = ''                # problem statement
    impact: str = ''                     # impact assessment
    remediation: str = ''                # step-by-step fix
    affected: list[dict] = field(default_factory=list)   # table rows
    suppressed_count: int = 0            # items hidden by suppress-list
    suppressed: bool = False             # entire incident suppressed by QA-ID


# Field labels for metadata completeness
_FIELD_LABELS: dict[str, str] = {
    'ci': 'CI',
    'full_name': 'Full name',
    'lc_stage': 'LC stage',
    'criticality': 'Criticality',
    'target_state': 'Target state',
    'business_owner_dep': 'Business owner',
    'dev_team': 'Dev team',
    'architect': 'Architect',
    'is_officer': 'IS-officer',
    'placement': 'Placement',
}


def compute_audit_incidents(
    built: object,
    sv_unresolved: int,
    sv_total: int,
    config: object,
) -> tuple[AuditSummary, list[AuditIncident]]:
    """Compute structured audit incidents from build results.

    Returns (summary, incidents) where incidents only includes non-empty ones.
    Filters by config.audit_suppress (system names) and
    config.audit_suppress_incidents (QA-IDs to skip entirely).
    """
    systems: list[System] = built.systems  # type: ignore[attr-defined]

    # Flat list of all systems + subsystems
    all_sys: list[System | Subsystem] = []
    for s in systems:
        all_sys.append(s)
        all_sys.extend(s.subsystems)

    suppress: set[str] = set(getattr(config, 'audit_suppress', []))
    suppress_incidents: set[str] = set(getattr(config, 'audit_suppress_incidents', []))

    total_sys = len(systems)
    incidents: list[AuditIncident] = []

    # ── Summary metrics ──────────────────────────────────────────────
    unassigned: list[System] = built.domain_systems.get('unassigned', [])  # type: ignore[attr-defined]
    unassigned_count = len(unassigned)
    assigned_count = total_sys - unassigned_count

    meta_check_keys = [k for k in _STANDARD_KEYS if k != 'full_name']
    meta_possible = len(all_sys) * len(meta_check_keys)
    meta_filled = sum(
        1 for s in all_sys for key in meta_check_keys
        if s.metadata.get(key, 'TBD') != 'TBD'
    )
    meta_pct = round(meta_filled / meta_possible * 100) if meta_possible else 100

    deployment_map: list = built.deployment_map  # type: ignore[attr-defined]
    mapped_sys_paths = {pair[0] for pair in deployment_map}

    summary = AuditSummary(
        total_systems=total_sys,
        total_subsystems=sum(len(s.subsystems) for s in systems),
        meta_completeness_pct=meta_pct,
        assigned_count=assigned_count,
        total_integrations=len(built.integrations),  # type: ignore[attr-defined]
        total_entities=len(built.entities),  # type: ignore[attr-defined]
        deployment_mappings=len(deployment_map),
    )

    # ── QA-1: Unassigned systems ─────────────────────────────────────
    filtered = [s for s in unassigned if s.name not in suppress]
    suppressed_cnt = unassigned_count - len(filtered)
    if filtered:
        incidents.append(AuditIncident(
            qa_id='QA-1',
            severity='Critical',
            title='Системы без домена',
            count=len(filtered),
            description=(
                f'{len(filtered)} систем не размещены ни на одной диаграмме '
                'в functional_areas/. Конвертер помещает их в домен «unassigned».'
            ),
            impact=(
                'Системы не отображаются в доменных views, невозможно '
                'понять их бизнес-принадлежность.'
            ),
            remediation=(
                '1. Откройте Archi → Views → functional_areas\n'
                '2. Для каждой системы определите целевой домен\n'
                '3. Перетащите элемент на соответствующую диаграмму домена'
            ),
            affected=[
                {'name': s.name, 'tags': ', '.join(s.tags) if s.tags else ''}
                for s in sorted(filtered, key=lambda x: x.name)
            ],
            suppressed_count=suppressed_cnt,
            suppressed=('QA-1' in suppress_incidents),
        ))

    # ── QA-2: Metadata gaps ──────────────────────────────────────────
    # Per-field completeness
    field_stats: list[dict] = []
    for key in meta_check_keys:
        filled = sum(1 for s in all_sys if s.metadata.get(key, 'TBD') != 'TBD')
        field_stats.append({
            'key': key,
            'label': _FIELD_LABELS.get(key, key),
            'filled': filled,
            'total': len(all_sys),
            'pct': round(filled / len(all_sys) * 100) if all_sys else 0,
        })

    # Systems with most TBD fields
    sys_tbd: list[dict] = []
    for s in all_sys:
        if s.name in suppress:
            continue
        tbd_count = sum(1 for key in meta_check_keys if s.metadata.get(key, 'TBD') == 'TBD')
        if tbd_count > 0:
            domain = s.domain if hasattr(s, 'domain') and s.domain else ''
            sys_tbd.append({'name': s.name, 'domain': domain, 'tbd_count': tbd_count,
                            'total_fields': len(meta_check_keys)})
    sys_tbd.sort(key=lambda x: (-x['tbd_count'], x['name']))

    all_tbd_count = sum(1 for d in sys_tbd if d['tbd_count'] == len(meta_check_keys))

    if all_tbd_count > 0:
        incidents.append(AuditIncident(
            qa_id='QA-2',
            severity='High',
            title='Незаполненные карточки систем',
            count=all_tbd_count,
            description=(
                f'{all_tbd_count} из {len(all_sys)} систем/подсистем не имеют '
                'ни одного заполненного свойства (CI, Criticality, LC stage и др.).'
            ),
            impact=(
                'Метаданные в архитектурном портале отображаются как '
                '«TBD» — невозможно оценить критичность, ответственных, стадию ЖЦ.'
            ),
            remediation=(
                '1. Откройте элемент в Archi → вкладка Properties\n'
                '2. Заполните как минимум: CI, Criticality, Dev team\n'
                '3. Приоритет — системы с наибольшим числом пустых полей'
            ),
            affected=sys_tbd[:20],
            suppressed_count=0,
            suppressed=('QA-2' in suppress_incidents),
        ))

    # ── QA-3: To-review systems ──────────────────────────────────────
    to_review = [s for s in systems if 'to_review' in s.tags and s.name not in suppress]
    if to_review:
            incidents.append(AuditIncident(
                qa_id='QA-3',
                severity='High',
                title='Системы на разборе',
                count=len(to_review),
                description=(
                    'Эти системы находятся в папке !РАЗБОР — '
                    'их статус в модели не определён.'
                ),
                impact=(
                    'Системы помечены тегом #to_review и требуют '
                    'решения: оставить в модели или удалить.'
                ),
                remediation=(
                    '1. Для каждой системы определите, является ли она актуальной\n'
                    '2. Если актуальна — переместите из !РАЗБОР в правильную папку\n'
                    '3. Если не актуальна — удалите элемент из модели'
                ),
                affected=[
                    {'name': s.name, 'domain': s.domain or 'unassigned'}
                    for s in sorted(to_review, key=lambda x: x.name)
                ],
                suppressed=('QA-3' in suppress_incidents),
            ))

    # ── QA-4: Promote candidates ─────────────────────────────────────
    promote_threshold = getattr(config, 'promote_warn_threshold', 10)
    already_promoted = set(getattr(config, 'promote_children', {}).keys())
    candidates = [
        (s.name, len(s.subsystems))
        for s in systems
        if len(s.subsystems) >= promote_threshold and s.name not in already_promoted
        and s.name not in suppress
    ]
    candidates.sort(key=lambda x: (-x[1], x[0]))
    if candidates:
        incidents.append(AuditIncident(
                qa_id='QA-4',
                severity='Medium',
                title='Кандидаты на декомпозицию',
                count=len(candidates),
                description=(
                    f'{len(candidates)} систем имеют ≥{promote_threshold} '
                    'подсистем — вероятно, их дочерние компоненты являются '
                    'самостоятельными микросервисами.'
                ),
                impact=(
                    'Интеграции всех подсистем схлопываются в одну стрелку '
                    'родителя, теряется детализация.'
                ),
                remediation=(
                    '1. Добавьте систему в promote_children в .archi2likec4.yaml\n'
                    '2. Укажите целевой домен: promote_children: { "Parent": "domain" }\n'
                    '3. Перезапустите конвертер — подсистемы станут самостоятельными системами'
                ),
                affected=[
                    {'name': name, 'subsystem_count': cnt}
                    for name, cnt in candidates
                ],
                suppressed=('QA-4' in suppress_incidents),
            ))

    # ── QA-5: No documentation ───────────────────────────────────────
    no_docs = [s for s in systems if not s.documentation and s.name not in suppress]
    if no_docs:
            show = sorted(no_docs, key=lambda x: x.name)[:30]
            incidents.append(AuditIncident(
                qa_id='QA-5',
                severity='Medium',
                title='Системы без документации',
                count=len(no_docs),
                description='Эти системы не имеют описания в поле documentation.',
                impact=(
                    'В архитектурном портале отсутствует описание назначения '
                    'системы — затруднено понимание её роли.'
                ),
                remediation=(
                    '1. Откройте элемент в Archi → поле Documentation\n'
                    '2. Добавьте краткое описание назначения системы (1-2 предложения)'
                ),
                affected=[
                    {'name': s.name, 'domain': s.domain or 'unassigned'}
                    for s in show
                ],
                suppressed=('QA-5' in suppress_incidents),
            ))

    # ── QA-6: Orphan functions ───────────────────────────────────────
    orphan_fns: int = built.orphan_fns  # type: ignore[attr-defined]
    if orphan_fns > 0:
            incidents.append(AuditIncident(
                qa_id='QA-6',
                severity='Low',
                title='Осиротевшие функции',
                count=orphan_fns,
                description=(
                    f'{orphan_fns} ApplicationFunction не имеют привязки '
                    'к родительскому ApplicationComponent.'
                ),
                impact=(
                    'Функции не отображаются ни в одной системе — '
                    'потеряна часть функциональной архитектуры.'
                ),
                remediation=(
                    '1. Найдите осиротевшие функции в Archi (--verbose)\n'
                    '2. Добавьте CompositionRelationship к целевому ApplicationComponent\n'
                    '3. Или переместите XML-файл функции в папку целевого компонента'
                ),
                suppressed=('QA-6' in suppress_incidents),
            ))

    # ── QA-7: Lost integrations ──────────────────────────────────────
    total_flow_rels = sum(
            1 for r in built.relationships  # type: ignore[attr-defined]
            if r.rel_type in ('FlowRelationship', 'ServingRelationship', 'TriggeringRelationship')
        )
    resolved_intg = len(built.integrations)  # type: ignore[attr-defined]
    skipped_intg = total_flow_rels - resolved_intg
    if skipped_intg > 0:
        pct = round(skipped_intg / total_flow_rels * 100) if total_flow_rels else 0
        incidents.append(AuditIncident(
                qa_id='QA-7',
                severity='Critical',
                title='Потерянные интеграции',
                count=skipped_intg,
                description=(
                    f'{skipped_intg} из {total_flow_rels} интеграционных связей '
                    f'({pct}%) не удалось разрешить — один или оба endpoint не найдены.'
                ),
                impact=(
                    'Часть интеграций между системами не отображается — '
                    'неполная картина взаимодействий.'
                ),
                remediation=(
                    '1. Запустите конвертер с --verbose для детального лога\n'
                    '2. Проверьте, что source и target — валидные ApplicationComponent\n'
                    '3. Убедитесь, что связи не ведут на удалённые элементы'
                ),
                suppressed=('QA-7' in suppress_incidents),
            ))

    # ── QA-8: Solution view coverage ─────────────────────────────────
    if sv_total > 0 and sv_unresolved > 0:
        sv_resolved = sv_total - sv_unresolved
        sv_pct = round(sv_resolved / sv_total * 100)
        incidents.append(AuditIncident(
                qa_id='QA-8',
                severity='High',
                title='Покрытие solution views',
                count=sv_unresolved,
                description=(
                    f'{sv_unresolved} из {sv_total} элементов на solution-диаграммах '
                    f'не удалось сопоставить с C4-моделью (разрешено {sv_resolved}, '
                    f'не разрешено {sv_unresolved}).'
                ),
                impact=(
                    'Solution views могут отображать неполную картину — '
                    'часть элементов диаграмм теряется при конвертации.'
                ),
                remediation=(
                    '1. Проверьте, что все элементы — валидные ApplicationComponent\n'
                    '2. Удалите элементы других типов (BusinessService и т.д.)\n'
                    '3. Убедитесь, что элементы не «призраки» удалённых компонентов'
                ),
                suppressed=('QA-8' in suppress_incidents),
            ))

    # ── QA-9: No infrastructure mapping ──────────────────────────────
    unmapped = [s for s in systems if f'{s.domain}.{s.c4_id}' not in mapped_sys_paths
                    and s.domain and s.domain != 'unassigned'
                    and s.name not in suppress]
    if unmapped:
        show = sorted(unmapped, key=lambda x: x.name)[:30]
        incidents.append(AuditIncident(
                qa_id='QA-9',
                severity='Medium',
                title='Системы без инфраструктурной привязки',
                count=len(unmapped),
                description=(
                    f'{len(unmapped)} систем не имеют связи с инфраструктурными '
                    'нодами (Node, SystemSoftware).'
                ),
                impact='На deployment view не видно, где развёрнуты эти системы.',
                remediation=(
                    '1. Откройте систему в Archi\n'
                    '2. Создайте RealizationRelationship к целевому Node\n'
                    '3. Или добавьте AssignmentRelationship'
                ),
                affected=[
                    {'name': s.name, 'domain': s.domain}
                    for s in show
                ],
                suppressed=('QA-9' in suppress_incidents),
            ))

    return summary, incidents
