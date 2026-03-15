"""Builders: integration (system-to-system relationship) construction."""

import logging

from ..models import (
    Integration,
    RawRelationship,
    System,
)

logger = logging.getLogger('archi2likec4')


def _build_comp_c4_path(systems: list[System]) -> tuple[dict[str, str], dict[str, str]]:
    """Build archi_id → c4_path and archi_id → system_c4_id maps."""
    comp_c4_path: dict[str, str] = {}
    comp_system_id: dict[str, str] = {}
    for sys in systems:
        if sys.archi_id:
            comp_c4_path[sys.archi_id] = sys.c4_id
            comp_system_id[sys.archi_id] = sys.c4_id
        for eid in sys.extra_archi_ids:
            comp_c4_path[eid] = sys.c4_id
            comp_system_id[eid] = sys.c4_id
        for sub in sys.subsystems:
            if sub.archi_id:
                comp_c4_path[sub.archi_id] = f'{sys.c4_id}.{sub.c4_id}'
                comp_system_id[sub.archi_id] = sys.c4_id
    return comp_c4_path, comp_system_id


def build_integrations(  # noqa: C901
    systems: list[System],
    relationships: list[RawRelationship],
    iface_c4_path: dict[str, str],
    promoted_parents: dict[str, list[str]] | None = None,
) -> tuple[list[Integration], int, int]:
    """Build deduplicated system-to-system integrations.

    Returns (integrations, skipped_count, total_eligible) where skipped_count
    is the number of eligible relationships with unresolvable endpoints and
    total_eligible is the total number of eligible (non-structural) relationships.
    """
    comp_c4_path, comp_system_id = _build_comp_c4_path(systems)

    raw_integrations: list[Integration] = []
    skipped = 0
    total_eligible = 0
    for rel in relationships:
        if rel.rel_type == 'AccessRelationship':
            continue
        if rel.rel_type in ('CompositionRelationship', 'AggregationRelationship',
                            'RealizationRelationship', 'AssignmentRelationship'):
            continue
        # Skip relationships involving ApplicationFunctions (not cross-system integrations)
        if rel.source_type == 'ApplicationFunction' or rel.target_type == 'ApplicationFunction':
            continue

        total_eligible += 1

        # Resolve source to one or more c4 paths (fan-out for promoted parents)
        src_paths: list[str] = []
        if rel.source_type == 'ApplicationComponent':
            path = comp_c4_path.get(rel.source_id)
            if path:
                src_paths = [path]
            elif promoted_parents and rel.source_id in promoted_parents:
                src_paths = list(promoted_parents[rel.source_id])
        elif rel.source_type == 'ApplicationInterface':
            path = iface_c4_path.get(rel.source_id)
            if path:
                src_paths = [path]

        # Resolve target to one or more c4 paths
        tgt_paths: list[str] = []
        if rel.target_type == 'ApplicationComponent':
            path = comp_c4_path.get(rel.target_id)
            if path:
                tgt_paths = [path]
            elif promoted_parents and rel.target_id in promoted_parents:
                tgt_paths = list(promoted_parents[rel.target_id])
        elif rel.target_type == 'ApplicationInterface':
            path = iface_c4_path.get(rel.target_id)
            if path:
                tgt_paths = [path]

        if not src_paths or not tgt_paths:
            skipped += 1
            continue

        name = rel.name.strip() if rel.name else ''
        # Cross-product for fan-out (usually 1×1, N×1 or 1×N for promoted parents)
        for sp in src_paths:
            sp_sys = sp.split('.')[0]
            for tp in tgt_paths:
                tp_sys = tp.split('.')[0]
                if sp_sys == tp_sys:
                    continue
                raw_integrations.append(Integration(
                    source_path=sp, target_path=tp, name=name, rel_type=rel.rel_type,
                ))

    if skipped:
        logger.info('Skipped %d integration(s) with unresolvable endpoints', skipped)

    # Deduplicate at system level
    pair_flows: dict[tuple[str, str], list[str]] = {}
    for intg in raw_integrations:
        src_sys = intg.source_path.split('.')[0]
        tgt_sys = intg.target_path.split('.')[0]
        pair = (src_sys, tgt_sys)
        if pair not in pair_flows:
            pair_flows[pair] = []
        if intg.name:
            pair_flows[pair].append(intg.name)

    deduped: list[Integration] = []
    for (src, tgt), names in sorted(pair_flows.items()):
        unique_names = list(dict.fromkeys(names))
        count = len(unique_names)
        if count == 0:
            label = ''
        elif count == 1:
            label = unique_names[0]
        elif count <= 3:
            label = '; '.join(unique_names)
        else:
            label = f'{"; ".join(unique_names[:3])}... ({count} flows)'
        deduped.append(Integration(source_path=src, target_path=tgt, name=label, rel_type=''))
    return deduped, skipped, total_eligible
