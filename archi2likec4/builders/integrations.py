"""Builders: integration (system-to-system relationship) construction."""

import logging

from ..models import (
    Integration,
    RawRelationship,
    System,
)
from ._paths import build_comp_c4_path

logger = logging.getLogger(__name__)

_SKIP_REL_TYPES = frozenset({
    'AccessRelationship', 'CompositionRelationship', 'AggregationRelationship',
    'RealizationRelationship', 'AssignmentRelationship',
})


def _resolve_endpoint_paths(
    archi_id: str,
    archi_type: str,
    comp_c4_path: dict[str, str],
    iface_c4_path: dict[str, str],
    promoted_parents: dict[str, list[str]] | None,
) -> list[str]:
    """Resolve an endpoint archi_id to one or more c4 paths (fan-out for promoted parents)."""
    if archi_type == 'ApplicationComponent':
        path = comp_c4_path.get(archi_id)
        if path:
            return [path]
        if promoted_parents and archi_id in promoted_parents:
            return list(promoted_parents[archi_id])
    elif archi_type == 'ApplicationInterface':
        path = iface_c4_path.get(archi_id)
        if path:
            return [path]
    return []


def _dedup_integrations(raw_integrations: list[Integration]) -> list[Integration]:
    """Deduplicate raw integrations at system level, merging flow names."""
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
    return deduped


def build_integrations(
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
    comp_c4_path = build_comp_c4_path(systems)

    raw_integrations: list[Integration] = []
    skipped = 0
    total_eligible = 0
    for rel in relationships:
        if rel.rel_type in _SKIP_REL_TYPES:
            continue
        if rel.source_type == 'ApplicationFunction' or rel.target_type == 'ApplicationFunction':
            continue

        total_eligible += 1

        src_paths = _resolve_endpoint_paths(rel.source_id, rel.source_type, comp_c4_path, iface_c4_path,
                                            promoted_parents)
        tgt_paths = _resolve_endpoint_paths(rel.target_id, rel.target_type, comp_c4_path, iface_c4_path,
                                            promoted_parents)

        if not src_paths or not tgt_paths:
            skipped += 1
            continue

        name = rel.name.strip() if rel.name else ''
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

    return _dedup_integrations(raw_integrations), skipped, total_eligible
