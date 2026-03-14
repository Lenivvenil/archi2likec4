"""Builders: transform parsed elements into the output model."""

import logging
import re

from .models import (
    PROMOTE_WARN_THRESHOLD,
    AppComponent,
    AppFunction,
    AppInterface,
    DataAccess,
    DataEntity,
    DataObject,
    DeploymentNode,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    RawRelationship,
    Subdomain,
    Subsystem,
    System,
    TechElement,
)
from .utils import build_metadata, make_id

logger = logging.getLogger('archi2likec4')


# ── Helpers ──────────────────────────────────────────────────────────────

def _build_comp_index(systems: list[System]) -> dict[str, tuple[System, Subsystem | None]]:
    """Build archi_id → (System, Subsystem|None) lookup, including extra_archi_ids."""
    comp_index: dict[str, tuple[System, Subsystem | None]] = {}
    for sys in systems:
        if sys.archi_id:
            comp_index[sys.archi_id] = (sys, None)
        for eid in sys.extra_archi_ids:
            comp_index[eid] = (sys, None)
        for sub in sys.subsystems:
            if sub.archi_id:
                comp_index[sub.archi_id] = (sys, sub)
    return comp_index


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


def _extract_url(documentation: str) -> str | None:
    """Extract the first HTTP(S) URL from a documentation string."""
    if not documentation:
        return None
    url_match = re.search(r'https?://\S+', documentation)
    if url_match:
        return url_match.group(0).rstrip('.,;)')
    return None


def _make_unique_id(base_id: str, used_ids: set[str]) -> str:
    """Return *base_id* if unused, otherwise append _2, _3, … until unique."""
    if base_id not in used_ids:
        return base_id
    suffix = 2
    while f'{base_id}_{suffix}' in used_ids:
        suffix += 1
    return f'{base_id}_{suffix}'


def _assign_tags(source_folder: str) -> list[str]:
    """Derive element tags from the coArchi source folder name."""
    if source_folder == '!РАЗБОР':
        return ['to_review']
    if source_folder == '!External_services':
        return ['external']
    return []


def _attach_subsystems(
    parent_systems: dict[str, System],
    subsystem_acs: list[AppComponent],
    parent_name_fn,
    sub_name_fn,
) -> None:
    """Attach a list of subsystem AppComponents to their parent Systems.

    *parent_name_fn(ac)* extracts the parent system name.
    *sub_name_fn(ac)* extracts the subsystem display name.
    """
    for ac in subsystem_acs:
        parent_name = parent_name_fn(ac)
        sub_name = sub_name_fn(ac)
        if parent_name not in parent_systems:
            logger.warning('Subsystem "%s" has no parent system "%s", skipping',
                           ac.name, parent_name)
            continue

        parent = parent_systems[parent_name]
        sub_ids_used = {s.c4_id for s in parent.subsystems}
        sub_c4_id = _make_unique_id(make_id(sub_name), sub_ids_used)

        parent.subsystems.append(Subsystem(
            c4_id=sub_c4_id, name=ac.name, archi_id=ac.archi_id,
            documentation=ac.documentation, metadata=build_metadata(ac),
            tags=_assign_tags(ac.source_folder),
        ))


# ── Builders ─────────────────────────────────────────────────────────────

def build_systems(
    components: list[AppComponent],
    promote_children: dict[str, str] | None = None,
    promote_warn_threshold: int | None = None,
    reviewed_systems: list[str] | None = None,
) -> tuple[list[System], dict[str, list[str]]]:
    """Build System objects from parsed AppComponents.

    Returns (systems, promoted_parents) where promoted_parents maps
    parent archi_id → list of child c4_ids for fan-out.
    """
    if promote_children is None:
        promote_children = {}
    if promote_warn_threshold is None:
        promote_warn_threshold = PROMOTE_WARN_THRESHOLD

    # ── Phase 1: collect dot-free names as potential systems ──────────────
    system_acs: dict[str, AppComponent] = {}
    extra_ids: dict[str, list[str]] = {}  # name → [archi_ids from discarded duplicates]
    dot_acs: list[AppComponent] = []
    for ac in components:
        if '.' in ac.name.rstrip('.'):
            dot_acs.append(ac)
        else:
            clean_name = ac.name.rstrip('.')
            existing = system_acs.get(clean_name)
            if existing is None or len(ac.properties) > len(existing.properties):
                if existing is not None and existing.archi_id:
                    extra_ids.setdefault(clean_name, []).append(existing.archi_id)
                system_acs[clean_name] = ac
            elif ac.archi_id:
                extra_ids.setdefault(clean_name, []).append(ac.archi_id)

    # ── Phase 2: separate dot_acs into promoted vs regular ───────────────
    promoted_subsystem_acs: list[AppComponent] = []
    regular_dot_acs: list[AppComponent] = []
    for ac in dot_acs:
        parent_name = ac.name.split('.', 1)[0]
        if parent_name in promote_children:
            parts = ac.name.split('.', 2)
            if len(parts) == 2:
                # 2-segment: "EFS.Card_Service" → promoted system
                clean_name = ac.name
                existing = system_acs.get(clean_name)
                if existing is None or len(ac.properties) > len(existing.properties):
                    if existing is not None and existing.archi_id:
                        extra_ids.setdefault(clean_name, []).append(existing.archi_id)
                    system_acs[clean_name] = ac
                elif ac.archi_id:
                    extra_ids.setdefault(clean_name, []).append(ac.archi_id)
            else:
                # 3+ segment: "EFS.Collection_Service.ODS" → subsystem of promoted
                promoted_subsystem_acs.append(ac)
        else:
            regular_dot_acs.append(ac)

    # Remove promoted parents from system_acs (only if they have promoted children)
    promoted_parent_names: set[str] = {
        ac.name.split('.', 1)[0]
        for ac in dot_acs
        if ac.name.split('.', 1)[0] in promote_children
    }
    # Save parent archi_ids for remapping to representative child
    parent_remap: dict[str, str] = {}  # parent_name → parent_archi_id
    for parent_name in promoted_parent_names:
        removed = system_acs.pop(parent_name, None)
        if removed:
            child_count = sum(1 for a in dot_acs if a.name.split('.', 1)[0] == parent_name)
            if removed.archi_id:
                parent_remap[parent_name] = removed.archi_id
            logger.info('Promoted parent "%s" removed — %d children promoted',
                        parent_name, child_count)

    # ── Phase 3: regular dot_acs — old subsystem-or-standalone logic ─────
    subsystem_acs: list[AppComponent] = []
    for ac in regular_dot_acs:
        parent_name = ac.name.split('.', 1)[0]
        if parent_name in system_acs:
            subsystem_acs.append(ac)
        else:
            clean_name = ac.name.rstrip('.')
            existing = system_acs.get(clean_name)
            if existing is None or len(ac.properties) > len(existing.properties):
                if existing is not None and existing.archi_id:
                    extra_ids.setdefault(clean_name, []).append(existing.archi_id)
                system_acs[clean_name] = ac
            elif ac.archi_id:
                extra_ids.setdefault(clean_name, []).append(ac.archi_id)

    # ── Build System objects ─────────────────────────────────────────────
    systems: dict[str, System] = {}
    used_ids: set[str] = set()

    for name, ac in sorted(system_acs.items()):
        c4_id = _make_unique_id(make_id(name), used_ids)
        used_ids.add(c4_id)

        tags = _assign_tags(ac.source_folder)

        if reviewed_systems and name in reviewed_systems:
            if 'to_review' in tags:
                tags.remove('to_review')

        sys_extra_ids = list(extra_ids.get(name, []))

        systems[name] = System(
            c4_id=c4_id, name=name, archi_id=ac.archi_id,
            documentation=ac.documentation, metadata=build_metadata(ac), tags=tags,
            extra_archi_ids=sys_extra_ids,
        )

    # ── Attach regular subsystems ────────────────────────────────────────
    _attach_subsystems(
        systems, subsystem_acs,
        parent_name_fn=lambda ac: ac.name.split('.', 1)[0],
        sub_name_fn=lambda ac: ac.name.split('.', 1)[1] if '.' in ac.name else ac.name,
    )

    # ── Attach promoted subsystems (3-segment names) ─────────────────────
    # Ensure 2-segment parent systems exist for any 3+ segment promoted ACs
    for ac in promoted_subsystem_acs:
        parent_2seg = '.'.join(ac.name.split('.', 2)[:2])
        if parent_2seg not in systems:
            c4_id = _make_unique_id(make_id(parent_2seg), used_ids)
            used_ids.add(c4_id)
            systems[parent_2seg] = System(
                c4_id=c4_id, name=parent_2seg, archi_id='',
                documentation='', metadata={},
            )
            logger.info('Auto-created promoted system "%s" for 3-segment child "%s"',
                        parent_2seg, ac.name)

    _attach_subsystems(
        systems, promoted_subsystem_acs,
        parent_name_fn=lambda ac: '.'.join(ac.name.split('.', 2)[:2]),
        sub_name_fn=lambda ac: ac.name.split('.', 2)[2],
    )

    # ── Build promoted_parents map: parent_archi_id → [child c4_ids] ──
    # Built AFTER auto-create so that 3-segment-only parents are included.
    promoted_parents: dict[str, list[str]] = {}
    for parent_name, parent_aid in parent_remap.items():
        children_c4_ids = sorted(
            sys.c4_id for name, sys in systems.items()
            if name.startswith(f'{parent_name}.')
        )
        if children_c4_ids:
            promoted_parents[parent_aid] = children_c4_ids
            logger.info('Parent "%s" archi_id fans out to %d children',
                        parent_name, len(children_c4_ids))

    # ── Phase 4: warn about suspicious parents ───────────────────────────
    parent_sub_count: dict[str, int] = {}
    for ac in subsystem_acs:
        parent_name = ac.name.split('.', 1)[0]
        parent_sub_count[parent_name] = parent_sub_count.get(parent_name, 0) + 1
    for parent_name, count in sorted(parent_sub_count.items()):
        if count >= promote_warn_threshold and parent_name not in promote_children:
            logger.warning('System "%s" has %d subsystems — '
                           'consider adding to PROMOTE_CHILDREN',
                           parent_name, count)

    return sorted(systems.values(), key=lambda s: s.name), promoted_parents


def attach_functions(
    systems: list[System],
    functions: list[AppFunction],
    relationships: list[RawRelationship] | None = None,
    promoted_parents: dict[str, list[str]] | None = None,
) -> int:
    """Attach AppFunctions to their parent System or Subsystem.

    Uses relationship-resolved parent first (CompositionRelationship etc.).
    Falls back to filesystem-resolved parent_archi_id for orphans.
    Functions referencing a promoted parent become honest orphans
    (the parent no longer exists as a single system).
    Returns the count of orphan functions (no parent found).
    """
    # Build archi_id → System/Subsystem lookup
    archi_to_system: dict[str, System] = {}
    archi_to_subsystem: dict[str, tuple[System, Subsystem]] = {}
    for sys in systems:
        if sys.archi_id:
            archi_to_system[sys.archi_id] = sys
        for eid in sys.extra_archi_ids:
            archi_to_system[eid] = sys
        for sub in sys.subsystems:
            if sub.archi_id:
                archi_to_subsystem[sub.archi_id] = (sys, sub)

    # Build relationship-based parent map: function_archi_id → component_archi_id
    parent_rel_types = {'CompositionRelationship', 'AssignmentRelationship', 'RealizationRelationship'}
    rel_parent: dict[str, str] = {}
    if relationships:
        for rel in relationships:
            if rel.rel_type in parent_rel_types:
                if rel.target_type == 'ApplicationFunction' and rel.source_type == 'ApplicationComponent':
                    rel_parent.setdefault(rel.target_id, rel.source_id)
                elif rel.source_type == 'ApplicationFunction' and rel.target_type == 'ApplicationComponent':
                    rel_parent.setdefault(rel.source_id, rel.target_id)

    orphans = 0
    for fn in functions:
        # Prefer explicit relationship parent over filesystem hierarchy
        if fn.archi_id in rel_parent:
            parent_id = rel_parent[fn.archi_id]
        else:
            parent_id = fn.parent_archi_id
        if not parent_id:
            orphans += 1
            continue
        if parent_id in archi_to_subsystem:
            _sys, sub = archi_to_subsystem[parent_id]
            # Generate unique c4_id within subsystem
            used = {f.c4_id for f in sub.functions}
            c4_id = make_id(fn.name)
            if c4_id in used:
                suffix = 2
                while f'{c4_id}_{suffix}' in used:
                    suffix += 1
                c4_id = f'{c4_id}_{suffix}'
            fn.c4_id = c4_id
            sub.functions.append(fn)
        elif parent_id in archi_to_system:
            sys = archi_to_system[parent_id]
            # Include subsystem c4_ids to avoid name collisions
            used = {f.c4_id for f in sys.functions} | {s.c4_id for s in sys.subsystems}
            c4_id = make_id(fn.name)
            if c4_id in used:
                suffix = 2
                while f'{c4_id}_{suffix}' in used:
                    suffix += 1
                c4_id = f'{c4_id}_{suffix}'
            fn.c4_id = c4_id
            sys.functions.append(fn)
        elif promoted_parents and parent_id in promoted_parents:
            # Function references a promoted parent — honest orphan
            orphans += 1
        else:
            orphans += 1
    return orphans


def build_data_entities(data_objects: list[DataObject], used_ids: set[str]) -> list[DataEntity]:
    """Convert DataObject to DataEntity with unique IDs (prefixed de_)."""
    entities: list[DataEntity] = []
    for do in data_objects:
        c4_id = make_id(do.name, prefix='de')
        if c4_id in used_ids:
            suffix = 2
            while f'{c4_id}_{suffix}' in used_ids:
                suffix += 1
            c4_id = f'{c4_id}_{suffix}'
        used_ids.add(c4_id)
        entities.append(DataEntity(
            c4_id=c4_id, name=do.name, archi_id=do.archi_id,
            documentation=do.documentation,
        ))
    return sorted(entities, key=lambda e: e.name)


def attach_interfaces(
    systems: list[System],
    interfaces: list[AppInterface],
    relationships: list[RawRelationship],
) -> dict[str, str]:
    """Resolve ApplicationInterface ownership and attach to systems.

    Returns iface_c4_path: archi_id → c4_path for resolved interfaces.
    """
    comp_index = _build_comp_index(systems)

    iface_index: dict[str, AppInterface] = {i.archi_id: i for i in interfaces}
    iface_owner: dict[str, tuple[System, Subsystem | None]] = {}

    for rel in relationships:
        if rel.rel_type in ('CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'):
            if rel.source_type == 'ApplicationComponent' and rel.target_type == 'ApplicationInterface':
                if rel.source_id in comp_index and rel.target_id in iface_index:
                    iface_owner[rel.target_id] = comp_index[rel.source_id]
            # Reverse direction: Interface → Component
            elif rel.source_type == 'ApplicationInterface' and rel.target_type == 'ApplicationComponent':
                if rel.target_id in comp_index and rel.source_id in iface_index:
                    iface_owner.setdefault(rel.source_id, comp_index[rel.target_id])

    name_to_sys: dict[str, System] = {s.name: s for s in systems}
    name_to_sub: dict[str, tuple[System, Subsystem]] = {}
    for sys in systems:
        for sub in sys.subsystems:
            name_to_sub[sub.name] = (sys, sub)

    unresolved = 0
    for iface in interfaces:
        if iface.archi_id in iface_owner:
            continue
        parts = iface.name.split('.')
        if len(parts) >= 2:
            sub_name = f'{parts[0]}.{parts[1]}'
            if sub_name in name_to_sub:
                sys, sub = name_to_sub[sub_name]
                iface_owner[iface.archi_id] = (sys, sub)
                continue
            if parts[0] in name_to_sys:
                iface_owner[iface.archi_id] = (name_to_sys[parts[0]], None)
                continue
            # Promoted systems have dot-names (e.g. "EFS.Card_Service")
            promoted_name = f'{parts[0]}.{parts[1]}'
            if promoted_name in name_to_sys:
                iface_owner[iface.archi_id] = (name_to_sys[promoted_name], None)
                continue
        elif iface.name in name_to_sys:
            iface_owner[iface.archi_id] = (name_to_sys[iface.name], None)
            continue
        unresolved += 1

    if unresolved:
        logger.warning('%d ApplicationInterface(s) could not be resolved to a system', unresolved)

    for iface_id, (owner_sys, owner_sub) in iface_owner.items():
        iface = iface_index.get(iface_id)
        if not iface:
            continue
        tgt = owner_sub if owner_sub else owner_sys
        if iface.name not in owner_sys.api_interfaces:
            owner_sys.api_interfaces.append(iface.name)
        url = _extract_url(iface.documentation)
        if url:
            tgt.links.append((url, iface.name))

    iface_c4_path: dict[str, str] = {}
    for iface_id, (owner_sys, owner_sub) in iface_owner.items():
        if owner_sub:
            iface_c4_path[iface_id] = f'{owner_sys.c4_id}.{owner_sub.c4_id}'
        else:
            iface_c4_path[iface_id] = owner_sys.c4_id
    return iface_c4_path


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


def build_data_access(
    systems: list[System],
    entities: list[DataEntity],
    relationships: list[RawRelationship],
    promoted_parents: dict[str, list[str]] | None = None,
) -> list[DataAccess]:
    """Resolve AccessRelationship: AppComponent → DataObject.

    When a relationship references a promoted parent, fan out to ALL children
    so each child gets a separate data access link.
    """
    comp_c4_path: dict[str, str] = {}
    for sys in systems:
        if sys.archi_id:
            comp_c4_path[sys.archi_id] = sys.c4_id
        for eid in sys.extra_archi_ids:
            comp_c4_path[eid] = sys.c4_id
        for sub in sys.subsystems:
            if sub.archi_id:
                comp_c4_path[sub.archi_id] = f'{sys.c4_id}.{sub.c4_id}'

    entity_by_archi: dict[str, DataEntity] = {e.archi_id: e for e in entities}

    results: list[DataAccess] = []
    seen: set[tuple[str, str, str]] = set()
    skipped = 0

    for rel in relationships:
        if rel.rel_type != 'AccessRelationship':
            continue

        # Determine component and entity from relationship direction
        comp_id: str | None = None
        entity: DataEntity | None = None
        if rel.source_type == 'ApplicationComponent' and rel.target_type == 'DataObject':
            comp_id = rel.source_id
            entity = entity_by_archi.get(rel.target_id)
        elif rel.source_type == 'DataObject' and rel.target_type == 'ApplicationComponent':
            comp_id = rel.target_id
            entity = entity_by_archi.get(rel.source_id)
        else:
            continue

        if not entity:
            skipped += 1
            continue

        # Resolve component to c4 paths (fan-out for promoted parents)
        sys_paths: list[str] = []
        if comp_id:
            path = comp_c4_path.get(comp_id)
            if path:
                sys_paths = [path]
            elif promoted_parents and comp_id in promoted_parents:
                sys_paths = list(promoted_parents[comp_id])

        if not sys_paths:
            skipped += 1
            continue

        name = rel.name.strip() if rel.name else ''

        for sp in sys_paths:
            sys_id = sp.split('.')[0]
            pair = (sys_id, entity.c4_id, name)
            if pair in seen:
                continue
            seen.add(pair)
            results.append(DataAccess(
                system_path=sys_id, entity_id=entity.c4_id,
                name=name,
            ))

    if skipped:
        logger.info('Skipped %d data access(es) with unresolvable endpoints', skipped)

    return sorted(results, key=lambda d: (d.system_path, d.entity_id))


def assign_domains(
    systems: list[System],
    domains: list[DomainInfo],
    promote_children: dict[str, str] | None = None,
    extra_domain_patterns: list[dict] | None = None,
    domain_overrides: dict[str, str] | None = None,
) -> dict[str, list[System]]:
    """Assign each system to a primary domain based on view membership."""
    # Reverse map: archi_id → [(domain_c4_id, ...)]
    id_to_domains: dict[str, list[str]] = {}
    for domain in domains:
        for aid in domain.archi_ids:
            id_to_domains.setdefault(aid, []).append(domain.c4_id)

    result: dict[str, list[System]] = {d.c4_id: [] for d in domains}
    result['unassigned'] = []

    # Pass 0: explicit domain overrides (highest priority)
    remaining = list(systems)
    if domain_overrides:
        override_ids: set[int] = set()
        for sys in systems:
            if sys.name in domain_overrides:
                target = domain_overrides[sys.name]
                if target not in result:
                    result[target] = []
                sys.domain = target
                result[target].append(sys)
                override_ids.add(id(sys))
        remaining = [s for s in systems if id(s) not in override_ids]

    for sys in remaining:
        # Collect archi IDs for this system (system + duplicates + all subsystems)
        all_ids: set[str] = set()
        if sys.archi_id:
            all_ids.add(sys.archi_id)
        all_ids.update(sys.extra_archi_ids)
        for sub in sys.subsystems:
            if sub.archi_id:
                all_ids.add(sub.archi_id)

        # Count hits per domain
        hits: dict[str, int] = {}
        for aid in all_ids:
            for domain_id in id_to_domains.get(aid, []):
                hits[domain_id] = hits.get(domain_id, 0) + 1

        if hits:
            # Primary = domain with most hits; ties broken alphabetically (smallest id first)
            primary = min(hits.items(), key=lambda x: (-x[1], x[0]))[0]
            sys.domain = primary
            result[primary].append(sys)
        else:
            sys.domain = 'unassigned'
            result['unassigned'].append(sys)

    # Second pass: fallback domain for promoted children
    if promote_children is None:
        promote_children = {}
    still_unassigned: list[System] = []
    for sys in result['unassigned']:
        parent_prefix = sys.name.split('.', 1)[0]
        if parent_prefix in promote_children:
            fallback = promote_children[parent_prefix]
            if fallback not in result:
                result[fallback] = []
            sys.domain = fallback
            result[fallback].append(sys)
        else:
            still_unassigned.append(sys)
    result['unassigned'] = still_unassigned

    # Third pass: assign unassigned systems to extra domains via pattern matching
    if extra_domain_patterns is None:
        extra_domain_patterns = []
    for extra in extra_domain_patterns:
        extra_id = extra['c4_id']
        patterns_lower = [p.lower() for p in extra['patterns']]
        if extra_id not in result:
            result[extra_id] = []

        still_unassigned = []
        for sys in result['unassigned']:
            name_lower = sys.name.lower()
            matched = any(p in name_lower for p in patterns_lower)
            if matched:
                sys.domain = extra_id
                result[extra_id].append(sys)
            else:
                still_unassigned.append(sys)
        result['unassigned'] = still_unassigned

    return result


def assign_subdomains(
    systems: list[System],
    parsed_subdomains: list[ParsedSubdomain],
) -> tuple[list[Subdomain], dict[str, list[str]]]:
    """Assign each system to a subdomain (Pass 4 of hierarchy assignment).

    Checks if any archi_id of a system appears in a ParsedSubdomain's
    component_ids list. Sets system.subdomain to the matched subdomain c4_id.

    Returns (subdomains, subdomain_systems) where subdomain_systems maps
    subdomain c4_id → list of system c4_ids.
    """
    # Build archi_id → ParsedSubdomain index
    archi_to_psd: dict[str, ParsedSubdomain] = {}
    for psd in parsed_subdomains:
        for cid in psd.component_ids:
            archi_to_psd[cid] = psd

    subdomain_systems: dict[str, list[str]] = {}
    subdomains_by_key: dict[tuple[str, str], Subdomain] = {}

    for sys in systems:
        # Collect all archi_ids for this system
        all_ids: list[str] = []
        if sys.archi_id:
            all_ids.append(sys.archi_id)
        all_ids.extend(sys.extra_archi_ids)

        # Find matching subdomain (first archi_id match wins)
        matched_psd: ParsedSubdomain | None = None
        for aid in all_ids:
            matched_psd = archi_to_psd.get(aid)
            if matched_psd:
                break

        if matched_psd is None:
            continue

        # Key by (domain_folder, archi_id) to avoid cross-domain collisions
        sd_key = (matched_psd.domain_folder, matched_psd.archi_id)
        if sd_key not in subdomains_by_key:
            subdomains_by_key[sd_key] = Subdomain(
                c4_id=matched_psd.archi_id,
                name=matched_psd.name,
                domain_id=matched_psd.domain_folder,
                system_ids=[],
            )

        # Assign system to subdomain
        sys.subdomain = matched_psd.archi_id
        subdomains_by_key[sd_key].system_ids.append(sys.c4_id)
        subdomain_systems.setdefault(matched_psd.archi_id, []).append(sys.c4_id)

    subdomains = sorted(subdomains_by_key.values(), key=lambda s: (s.domain_id, s.c4_id))
    return subdomains, subdomain_systems


def apply_domain_prefix(
    integrations: list[Integration],
    data_access: list[DataAccess],
    sys_domain: dict[str, str],
    sys_subdomain: dict[str, str] | None = None,
) -> None:
    """Add domain (and optional subdomain) prefix to integration and data access paths.

    Transforms 'efs' → 'channels.efs' (no subdomain) or
    'efs' → 'channels.banking.efs' (with subdomain) based on assignment.
    """
    def _prefix(sys_c4_id: str) -> str:
        domain = sys_domain.get(sys_c4_id, 'unassigned')
        subdomain = sys_subdomain.get(sys_c4_id, '') if sys_subdomain else ''
        if subdomain:
            return f'{domain}.{subdomain}.{sys_c4_id}'
        return f'{domain}.{sys_c4_id}'

    for intg in integrations:
        intg.source_path = _prefix(intg.source_path)
        intg.target_path = _prefix(intg.target_path)

    for da in data_access:
        da.system_path = _prefix(da.system_path)


def build_archi_to_c4_map(
    systems: list[System],
    sys_domain: dict[str, str],
    iface_c4_path: dict[str, str] | None = None,
    sys_subdomain: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a complete archi_id → c4_path mapping for all elements.

    Includes systems, subsystems, appFunctions, and optionally interfaces.
    Returns dict: archi_id → full c4 path (e.g. 'products.banking.efs.account_service.fn_create')
    """
    result: dict[str, str] = {}
    for sys in systems:
        domain = sys_domain.get(sys.c4_id, 'unassigned')
        subdomain = sys_subdomain.get(sys.c4_id, '') if sys_subdomain else sys.subdomain
        if subdomain:
            sys_path = f'{domain}.{subdomain}.{sys.c4_id}'
        else:
            sys_path = f'{domain}.{sys.c4_id}'
        if sys.archi_id:
            result[sys.archi_id] = sys_path
        for eid in sys.extra_archi_ids:
            result[eid] = sys_path
        for sub in sys.subsystems:
            sub_path = f'{sys_path}.{sub.c4_id}'
            if sub.archi_id:
                result[sub.archi_id] = sub_path
            for fn in sub.functions:
                if fn.archi_id:
                    result[fn.archi_id] = f'{sub_path}.{fn.c4_id}'
        for fn in sys.functions:
            if fn.archi_id:
                result[fn.archi_id] = f'{sys_path}.{fn.c4_id}'
    # Add interfaces — resolve to their owner system path
    if iface_c4_path:
        for iface_id, iface_path in iface_c4_path.items():
            if iface_id not in result:
                # Resolve system c4_id to domain(.subdomain).system path
                sys_c4_id = iface_path.split('.')[0]
                domain = sys_domain.get(sys_c4_id, 'unassigned')
                sd = sys_subdomain.get(sys_c4_id, '') if sys_subdomain else ''
                if sd:
                    result[iface_id] = f'{domain}.{sd}.{iface_path}'
                else:
                    result[iface_id] = f'{domain}.{iface_path}'
    return result


# ── Deployment topology ─────────────────────────────────────────────────

_INFRA_NODE_TYPES = frozenset({
    'Node', 'Device', 'TechnologyCollaboration',
})
_INFRA_ZONE_TYPES = frozenset({
    'CommunicationNetwork', 'Path',
})
_INFRA_SW_TYPES = frozenset({
    'SystemSoftware', 'TechnologyService', 'Artifact',
})

# Patterns to identify database/storage SystemSoftware → dataStore kind
_DATASTORE_PATTERNS = re.compile(
    r'(?i)\b(?:postgres|postgresql|oracle|mysql|mariadb|mongo|mongodb|redis'
    r'|elasticsearch|opensearch|cassandra|clickhouse|sqlite|mssql|sql\s*server'
    r'|db2|couchdb|dynamodb|memcached|neo4j|influxdb|timescaledb'
    r'|stage\s*db|database|хранилище)\b'
)


def build_deployment_topology(
    tech_elements: list[TechElement],
    relationships: list[RawRelationship],
) -> list[DeploymentNode]:
    """Build deployment hierarchy from tech elements and AggregationRelationship.

    AggregationRelationship source contains target:
    - TechnologyCollaboration → Node (cluster contains servers)
    - Node → SystemSoftware (server contains software)
    - Device → SystemSoftware (device contains software)

    Returns only root nodes (elements not contained by anything).
    """
    if not tech_elements:
        return []

    # 1. Create DeploymentNode for each TechElement with unique c4_ids
    used_ids: set[str] = set()
    node_by_archi: dict[str, DeploymentNode] = {}

    for te in tech_elements:
        c4_id = _make_unique_id(make_id(te.name), used_ids)
        used_ids.add(c4_id)

        if te.tech_type == 'Location':
            kind = 'infraLocation'
        elif te.tech_type in _INFRA_ZONE_TYPES:
            kind = 'infraZone'
        elif te.tech_type in _INFRA_NODE_TYPES:
            kind = 'infraNode'
        elif te.tech_type in _INFRA_SW_TYPES and _DATASTORE_PATTERNS.search(te.name):
            kind = 'dataStore'
        else:
            kind = 'infraSoftware'

        dn = DeploymentNode(
            c4_id=c4_id,
            name=te.name,
            archi_id=te.archi_id,
            tech_type=te.tech_type,
            kind=kind,
            documentation=te.documentation,
        )
        node_by_archi[te.archi_id] = dn

    # 2. Resolve AggregationRelationship → parent contains children
    children_set: set[str] = set()  # archi_ids that are children

    for rel in relationships:
        if rel.rel_type != 'AggregationRelationship':
            continue
        parent = node_by_archi.get(rel.source_id)
        child = node_by_archi.get(rel.target_id)
        if parent and child and rel.target_id not in children_set:
            parent.children.append(child)
            children_set.add(rel.target_id)

    # 3. Return only root nodes (not children of anything)
    roots = [dn for aid, dn in node_by_archi.items() if aid not in children_set]
    roots.sort(key=lambda n: n.name)

    logger.debug('%d tech elements → %d root deployment nodes',
                 len(tech_elements), len(roots))
    return roots


def enrich_deployment_from_visual_nesting(
    deployment_nodes: list[DeploymentNode],
    visual_nesting_pairs: list[tuple[str, str]],
) -> int:
    """Use visual nesting from Archi diagrams to fix missing parent-child relationships.

    When a tech element appears as a root node but a deployment diagram shows it
    visually nested inside another tech element, re-parent it. This fixes the common
    case where Archi has no AggregationRelationship but the diagram canvas shows nesting.

    Mutates deployment_nodes in-place. Returns the count of re-parented nodes.
    """
    if not visual_nesting_pairs:
        return 0

    # Build flat index: archi_id → DeploymentNode
    all_nodes = _flatten_deployment_nodes(deployment_nodes)
    by_archi: dict[str, DeploymentNode] = {dn.archi_id: dn for dn in all_nodes}
    root_ids = {dn.archi_id for dn in deployment_nodes}

    # Deduplicate and filter: only consider pairs where both sides are known tech elements
    # and the child is currently a root node
    reparent: dict[str, str] = {}  # child_archi_id → parent_archi_id
    for parent_aid, child_aid in visual_nesting_pairs:
        if parent_aid not in by_archi or child_aid not in by_archi:
            continue
        if child_aid not in root_ids:
            continue  # already nested
        if child_aid == parent_aid:
            continue
        # First diagram wins (most authoritative)
        if child_aid not in reparent:
            reparent[child_aid] = parent_aid

    # Apply reparenting
    reparented = 0
    for child_aid, parent_aid in reparent.items():
        child = by_archi[child_aid]
        parent = by_archi[parent_aid]
        # Avoid cycles: don't reparent if parent is descendant of child
        if _is_descendant(child, parent_aid):
            continue
        # Check child is not already a child of parent
        if any(c.archi_id == child_aid for c in parent.children):
            continue
        parent.children.append(child)
        reparented += 1

    # Remove reparented nodes from root list
    if reparented:
        reparented_aids = {aid for aid in reparent if by_archi[aid] in deployment_nodes}
        deployment_nodes[:] = [dn for dn in deployment_nodes if dn.archi_id not in reparented_aids]
        deployment_nodes.sort(key=lambda n: n.name)

    if reparented:
        logger.info('Re-parented %d deployment nodes from visual nesting', reparented)

    return reparented


def _is_descendant(node: DeploymentNode, target_archi_id: str) -> bool:
    """Check if target_archi_id is a descendant of node."""
    for child in node.children:
        if child.archi_id == target_archi_id:
            return True
        if _is_descendant(child, target_archi_id):
            return True
    return False


def _flatten_deployment_nodes(nodes: list[DeploymentNode]) -> list[DeploymentNode]:
    """Recursively flatten a tree of DeploymentNodes into a flat list."""
    result: list[DeploymentNode] = []
    for node in nodes:
        result.append(node)
        result.extend(_flatten_deployment_nodes(node.children))
    return result


def _build_deployment_path_index(
    nodes: list[DeploymentNode],
    prefix: str = '',
) -> dict[str, str]:
    """Build archi_id → qualified c4 path for all nodes in the tree.

    Root nodes get their c4_id as path; nested nodes get parent.child paths.
    """
    result: dict[str, str] = {}
    for node in nodes:
        path = f'{prefix}{node.c4_id}' if not prefix else f'{prefix}.{node.c4_id}'
        result[node.archi_id] = path
        result.update(_build_deployment_path_index(node.children, path))
    return result


def build_tech_archi_to_c4_map(
    deployment_nodes: list[DeploymentNode],
) -> dict[str, str]:
    """Build archi_id → c4_path for all deployment nodes (public wrapper)."""
    return _build_deployment_path_index(deployment_nodes)


def build_deployment_map(
    systems: list[System],
    deployment_nodes: list[DeploymentNode],
    relationships: list[RawRelationship],
    sys_domain: dict[str, str],
) -> list[tuple[str, str]]:
    """Build (app_c4_path, node_c4_id) pairs from cross-layer RealizationRelationship.

    Resolves ApplicationComponent ↔ Node/SystemSoftware/Device via RealizationRelationship.
    """
    if not deployment_nodes or not systems:
        return []

    # Build app index: archi_id → full c4 path (domain.system)
    app_path: dict[str, str] = {}
    for sys in systems:
        domain = sys_domain.get(sys.c4_id, 'unassigned')
        full = f'{domain}.{sys.c4_id}'
        if sys.archi_id:
            app_path[sys.archi_id] = full
        for eid in sys.extra_archi_ids:
            app_path[eid] = full
        for sub in sys.subsystems:
            if sub.archi_id:
                app_path[sub.archi_id] = f'{full}.{sub.c4_id}'

    # Build tech index: archi_id → qualified c4 path (parent.child for nested)
    tech_path = _build_deployment_path_index(deployment_nodes)

    # Only ApplicationComponent is resolvable via app_path (systems/subsystems).
    _app_types = {'ApplicationComponent'}
    _tech_types = {'Node', 'SystemSoftware', 'Device', 'TechnologyCollaboration',
                   'TechnologyService', 'Artifact', 'CommunicationNetwork', 'Path'}

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for rel in relationships:
        if rel.rel_type not in ('RealizationRelationship', 'AssignmentRelationship'):
            continue

        app_id: str | None = None
        tech_id: str | None = None

        if rel.source_type in _app_types and rel.target_type in _tech_types:
            app_id, tech_id = rel.source_id, rel.target_id
        elif rel.source_type in _tech_types and rel.target_type in _app_types:
            app_id, tech_id = rel.target_id, rel.source_id
        else:
            continue

        a = app_path.get(app_id)
        t = tech_path.get(tech_id)
        if not a or not t:
            continue

        pair = (a, t)
        if pair in seen:
            continue
        seen.add(pair)
        result.append(pair)

    result.sort()
    return result


def build_datastore_entity_links(
    deployment_nodes: list[DeploymentNode],
    entities: list[DataEntity],
    relationships: list[RawRelationship],
) -> list[tuple[str, str]]:
    """Build (dataStore_c4_path, dataEntity_c4_id) pairs.

    Links dataStore deployment nodes to DataEntity via relationships where
    both sides reference the same logical data concept (AccessRelationship
    between SystemSoftware and DataObject).
    """
    if not deployment_nodes or not entities:
        return []

    all_dn = _flatten_deployment_nodes(deployment_nodes)
    datastore_nodes = [dn for dn in all_dn if dn.kind == 'dataStore']
    if not datastore_nodes:
        return []

    tech_path = _build_deployment_path_index(deployment_nodes)
    entity_by_archi = {e.archi_id: e for e in entities}

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for rel in relationships:
        if rel.rel_type != 'AccessRelationship':
            continue

        sw_id: str | None = None
        do_id: str | None = None

        if rel.source_type == 'SystemSoftware' and rel.target_type == 'DataObject':
            sw_id, do_id = rel.source_id, rel.target_id
        elif rel.source_type == 'DataObject' and rel.target_type == 'SystemSoftware':
            sw_id, do_id = rel.target_id, rel.source_id
        else:
            continue

        t = tech_path.get(sw_id)
        entity = entity_by_archi.get(do_id)
        if not t or not entity:
            continue

        pair = (t, entity.c4_id)
        if pair not in seen:
            seen.add(pair)
            result.append(pair)

    result.sort()
    return result
