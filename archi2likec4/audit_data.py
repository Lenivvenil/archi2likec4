"""Structured audit data: compute quality incidents as data objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .i18n import get_msg, get_qa10_issue
from .models import DeploymentNode, Subsystem, System

if TYPE_CHECKING:
    from .builders._result import BuildResult
    from .config import ConvertConfig

# Maximum number of affected items shown in an incident's detail table.
_MAX_AFFECTED_ITEMS = 30


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
    affected: list[dict[str, str | int]] = field(default_factory=list)   # table rows
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
    built: BuildResult,
    sv_unresolved: int,
    sv_total: int,
    config: ConvertConfig,
) -> tuple[AuditSummary, list[AuditIncident]]:
    """Compute structured audit incidents from build results.

    Returns (summary, incidents) where incidents only includes non-empty ones.
    Filters by config.audit_suppress (system names) and
    config.audit_suppress_incidents (QA-IDs to skip entirely).
    Uses config.language ('ru'|'en') for incident text.
    """
    lang: str = config.language
    systems: list[System] = built.systems

    # Flat list of all systems + subsystems
    all_sys: list[System | Subsystem] = []
    for sys_item in systems:
        all_sys.append(sys_item)
        all_sys.extend(sys_item.subsystems)

    suppress: set[str] = set(config.audit_suppress)
    suppress_incidents: set[str] = set(config.audit_suppress_incidents)

    total_sys = len(systems)
    incidents: list[AuditIncident] = []

    # ── Summary metrics ──────────────────────────────────────────────
    unassigned: list[System] = built.domain_systems.get('unassigned', [])
    unassigned_count = len(unassigned)
    assigned_count = total_sys - unassigned_count

    standard_keys = config.standard_keys
    meta_check_keys = [k for k in standard_keys if k != 'full_name']
    meta_possible = len(all_sys) * len(meta_check_keys)
    meta_filled = sum(
        1 for s in all_sys for key in meta_check_keys
        if s.metadata.get(key, 'TBD') != 'TBD'
    )
    meta_pct = round(meta_filled / meta_possible * 100) if meta_possible else 100

    deployment_map: list[tuple[str, str]] = built.deployment_map
    # Collect all paths present in the deployment map.
    # A system is considered deployed if any deployment path equals its c4_path
    # or starts with its c4_path followed by '.' (subsystem/component entries).
    # Paths may be: 'domain.system', 'domain.system.subsystem',
    # 'domain.subdomain.system', or 'domain.subdomain.system.subsystem'.
    deployment_paths: set[str] = {pair[0] for pair in deployment_map}

    summary = AuditSummary(
        total_systems=total_sys,
        total_subsystems=sum(len(s.subsystems) for s in systems),
        meta_completeness_pct=meta_pct,
        assigned_count=assigned_count,
        total_integrations=len(built.integrations),
        total_entities=len(built.entities),
        deployment_mappings=len(deployment_map),
    )

    # ── QA-1: Unassigned systems ─────────────────────────────────────
    filtered = [s for s in unassigned if s.name not in suppress]
    suppressed_cnt = unassigned_count - len(filtered)
    if filtered or suppressed_cnt > 0:
        incidents.append(AuditIncident(
            qa_id='QA-1',
            severity='Critical',
            title=get_msg('QA-1', 'title', lang),
            count=len(filtered),
            description=get_msg('QA-1', 'description', lang, count=len(filtered)),
            impact=get_msg('QA-1', 'impact', lang),
            remediation=get_msg('QA-1', 'remediation', lang),
            affected=[
                {'name': s.name, 'tags': ', '.join(s.tags) if s.tags else ''}
                for s in sorted(filtered, key=lambda x: x.name)
            ],
            suppressed_count=suppressed_cnt,
            suppressed=('QA-1' in suppress_incidents),
        ))

    # ── QA-2: Metadata gaps ──────────────────────────────────────────
    # Per-field completeness
    field_stats: list[dict[str, str | int]] = []
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
    sys_tbd: list[dict[str, str | int]] = []
    for s in all_sys:
        if s.name in suppress:
            continue
        tbd_count = sum(1 for key in meta_check_keys if s.metadata.get(key, 'TBD') == 'TBD')
        if tbd_count > 0:
            domain = s.domain if hasattr(s, 'domain') and s.domain else ''
            sys_tbd.append({'name': s.name, 'domain': domain, 'tbd_count': tbd_count,
                            'total_fields': len(meta_check_keys)})
    sys_tbd.sort(key=lambda x: (-int(x['tbd_count']), x['name']))

    all_tbd_count = sum(1 for d in sys_tbd if d['tbd_count'] == len(meta_check_keys))

    if all_tbd_count > 0:
        incidents.append(AuditIncident(
            qa_id='QA-2',
            severity='High',
            title=get_msg('QA-2', 'title', lang),
            count=all_tbd_count,
            description=get_msg('QA-2', 'description', lang,
                                count=all_tbd_count, total=len(all_sys)),
            impact=get_msg('QA-2', 'impact', lang),
            remediation=get_msg('QA-2', 'remediation', lang),
            affected=sys_tbd[:_MAX_AFFECTED_ITEMS],
            suppressed_count=0,
            suppressed=('QA-2' in suppress_incidents),
        ))

    # ── QA-3: To-review systems ──────────────────────────────────────
    to_review = [s for s in systems if 'to_review' in s.tags and s.name not in suppress]
    if to_review:
        incidents.append(AuditIncident(
            qa_id='QA-3',
            severity='High',
            title=get_msg('QA-3', 'title', lang),
            count=len(to_review),
            description=get_msg('QA-3', 'description', lang),
            impact=get_msg('QA-3', 'impact', lang),
            remediation=get_msg('QA-3', 'remediation', lang),
            affected=[
                {'name': s.name, 'domain': s.domain or 'unassigned'}
                for s in sorted(to_review, key=lambda x: x.name)
            ],
            suppressed=('QA-3' in suppress_incidents),
        ))

    # ── QA-4: Promote candidates ─────────────────────────────────────
    promote_threshold = config.promote_warn_threshold
    already_promoted = set(config.promote_children.keys())
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
            title=get_msg('QA-4', 'title', lang),
            count=len(candidates),
            description=get_msg('QA-4', 'description', lang,
                                count=len(candidates), threshold=promote_threshold),
            impact=get_msg('QA-4', 'impact', lang),
            remediation=get_msg('QA-4', 'remediation', lang),
            affected=[
                {'name': name, 'subsystem_count': cnt}
                for name, cnt in candidates
            ],
            suppressed=('QA-4' in suppress_incidents),
        ))

    # ── QA-5: No documentation ───────────────────────────────────────
    no_docs = [s for s in systems if not s.documentation and s.name not in suppress]
    if no_docs:
        show = sorted(no_docs, key=lambda x: x.name)[:_MAX_AFFECTED_ITEMS]
        incidents.append(AuditIncident(
            qa_id='QA-5',
            severity='Medium',
            title=get_msg('QA-5', 'title', lang),
            count=len(no_docs),
            description=get_msg('QA-5', 'description', lang),
            impact=get_msg('QA-5', 'impact', lang),
            remediation=get_msg('QA-5', 'remediation', lang),
            affected=[
                {'name': s.name, 'domain': s.domain or 'unassigned'}
                for s in show
            ],
            suppressed=('QA-5' in suppress_incidents),
        ))

    # ── QA-6: Orphan functions ───────────────────────────────────────
    orphan_fns: int = built.diagnostics.orphan_fns
    if orphan_fns > 0:
        incidents.append(AuditIncident(
            qa_id='QA-6',
            severity='Low',
            title=get_msg('QA-6', 'title', lang),
            count=orphan_fns,
            description=get_msg('QA-6', 'description', lang, count=orphan_fns),
            impact=get_msg('QA-6', 'impact', lang),
            remediation=get_msg('QA-6', 'remediation', lang),
            suppressed=('QA-6' in suppress_incidents),
        ))

    # ── QA-7: Lost integrations ──────────────────────────────────────
    skipped_intg: int = built.diagnostics.intg_skipped
    total_eligible: int = built.diagnostics.intg_total_eligible
    if skipped_intg > 0 and total_eligible > 0:
        pct = round(skipped_intg / total_eligible * 100)
        incidents.append(AuditIncident(
            qa_id='QA-7',
            severity='Critical',
            title=get_msg('QA-7', 'title', lang),
            count=skipped_intg,
            description=get_msg('QA-7', 'description', lang,
                                skipped=skipped_intg, total=total_eligible, pct=pct),
            impact=get_msg('QA-7', 'impact', lang),
            remediation=get_msg('QA-7', 'remediation', lang),
            suppressed=('QA-7' in suppress_incidents),
        ))

    # ── QA-8: Solution view coverage ─────────────────────────────────
    if sv_total > 0 and sv_unresolved > 0:
        sv_resolved = sv_total - sv_unresolved
        incidents.append(AuditIncident(
            qa_id='QA-8',
            severity='High',
            title=get_msg('QA-8', 'title', lang),
            count=sv_unresolved,
            description=get_msg('QA-8', 'description', lang,
                                unresolved=sv_unresolved, total=sv_total,
                                resolved=sv_resolved),
            impact=get_msg('QA-8', 'impact', lang),
            remediation=get_msg('QA-8', 'remediation', lang),
            suppressed=('QA-8' in suppress_incidents),
        ))

    # ── QA-9: No infrastructure mapping ──────────────────────────────
    def _sys_c4_path(s: System) -> str:
        sd = s.subdomain
        if sd:
            return f'{s.domain}.{sd}.{s.c4_id}'
        return f'{s.domain}.{s.c4_id}'

    # Collect all system-level paths to avoid confusing subdomain paths
    # with subsystem paths during one-segment-deeper matching.
    all_system_paths: set[str] = {_sys_c4_path(s) for s in systems}

    def _is_deployed(s: System) -> bool:
        p = _sys_c4_path(s)
        if p in deployment_paths:
            return True
        # Check subsystem-level paths (one segment deeper).
        # Skip paths that are themselves known system paths (subdomain match).
        prefix = p + '.'
        for dp in deployment_paths:
            if dp.startswith(prefix) and '.' not in dp[len(prefix):] and dp not in all_system_paths:
                return True
        return False

    unmapped = [s for s in systems if not _is_deployed(s)
                    and s.domain and s.domain != 'unassigned'
                    and s.name not in suppress]
    if unmapped:
        show = sorted(unmapped, key=lambda x: x.name)[:_MAX_AFFECTED_ITEMS]
        incidents.append(AuditIncident(
            qa_id='QA-9',
            severity='Medium',
            title=get_msg('QA-9', 'title', lang),
            count=len(unmapped),
            description=get_msg('QA-9', 'description', lang, count=len(unmapped)),
            impact=get_msg('QA-9', 'impact', lang),
            remediation=get_msg('QA-9', 'remediation', lang),
            affected=[
                {'name': s.name, 'domain': s.domain}
                for s in show
            ],
            suppressed=('QA-9' in suppress_incidents),
        ))

    # ── QA-10: Deployment hierarchy issues ─────────────────────────
    deployment_nodes: list[DeploymentNode] = built.deployment_nodes
    if deployment_nodes:
        from .utils import flatten_deployment_nodes
        all_dn = flatten_deployment_nodes(deployment_nodes)

        qa10_affected: list[dict[str, str | int]] = []

        # Check 1: SystemSoftware as root node ("floating software")
        for dn in deployment_nodes:
            if dn.kind == 'infraSoftware':
                qa10_affected.append({
                    'name': dn.name, 'kind': dn.kind,
                    'issue': get_qa10_issue('floating_sw', lang),
                })

        # Check if locations exist in model
        locations = [dn for dn in all_dn if dn.kind == 'infraLocation']
        if locations:
            # Check 2: Location without children
            for loc in locations:
                if not loc.children:
                    qa10_affected.append({
                        'name': loc.name, 'kind': loc.kind,
                        'issue': get_qa10_issue('empty_location', lang),
                    })

            # Check 3: Root Node/Zone not under Location (transitive)
            # Collect ALL archi_ids that are transitively nested under any Location
            under_location: set[str] = set()

            def _collect_descendants(node: DeploymentNode) -> None:
                for child in node.children:
                    under_location.add(child.archi_id)
                    _collect_descendants(child)

            for loc in locations:
                _collect_descendants(loc)
            for dn in deployment_nodes:
                if dn.kind in ('infraNode', 'infraZone') and dn.archi_id not in under_location:
                    qa10_affected.append({
                        'name': dn.name, 'kind': dn.kind,
                        'issue': get_qa10_issue('root_no_location', lang),
                    })

        # Check 4: Leaf node (infraSoftware) with children
        for dn in all_dn:
            if dn.kind == 'infraSoftware' and dn.children:
                qa10_affected.append({
                    'name': dn.name, 'kind': dn.kind,
                    'issue': get_qa10_issue('leaf_with_children', lang),
                })

        # Check 5: Excessive nesting depth (> 6 levels)
        def _max_depth(nodes: list[DeploymentNode], depth: int = 1) -> int:
            if not nodes:
                return depth - 1
            return max(_max_depth(n.children, depth + 1) for n in nodes)

        def _nodes_at_depth(nodes: list[DeploymentNode], target: int, current: int = 1) -> list[DeploymentNode]:
            result = []
            for n in nodes:
                if current == target:
                    result.append(n)
                result.extend(_nodes_at_depth(n.children, target, current + 1))
            return result

        max_d = _max_depth(deployment_nodes)
        if max_d > 6:
            deep_nodes = _nodes_at_depth(deployment_nodes, max_d)
            for dn in deep_nodes:
                qa10_affected.append({
                    'name': dn.name, 'kind': dn.kind,
                    'issue': get_qa10_issue('excessive_depth', lang),
                })

        # Check 6: Duplicate archi_id across different branches
        seen_ids: dict[str, str] = {}  # archi_id → first node name
        for dn in all_dn:
            if dn.archi_id in seen_ids:
                qa10_affected.append({
                    'name': dn.name, 'kind': dn.kind,
                    'issue': get_qa10_issue('duplicate_archi_id', lang),
                })
            else:
                seen_ids[dn.archi_id] = dn.name

        if qa10_affected:
            incidents.append(AuditIncident(
                qa_id='QA-10',
                severity='Medium',
                title=get_msg('QA-10', 'title', lang),
                count=len(qa10_affected),
                description=get_msg('QA-10', 'description', lang,
                                    count=len(qa10_affected)),
                impact=get_msg('QA-10', 'impact', lang),
                remediation=get_msg('QA-10', 'remediation', lang),
                affected=qa10_affected,
                suppressed=('QA-10' in suppress_incidents),
            ))

    return summary, incidents
