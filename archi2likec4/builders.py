"""Builders: transform parsed elements into the output model."""

import re

from .models import (
    EXTRA_DOMAIN_PATTERNS,
    PROMOTE_CHILDREN,
    PROMOTE_WARN_THRESHOLD,
    AppComponent,
    AppFunction,
    AppInterface,
    DataAccess,
    DataEntity,
    DataObject,
    DomainInfo,
    Integration,
    RawRelationship,
    Subsystem,
    System,
)
from .utils import build_metadata, make_id


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
    if not documentation:
        return None
    url_match = re.search(r'https?://\S+', documentation)
    if url_match:
        return url_match.group(0).rstrip('.,;)')
    return None


# ── Builders ─────────────────────────────────────────────────────────────

def build_systems(
    components: list[AppComponent],
    promote_children: dict[str, str] | None = None,
) -> tuple[list[System], dict[str, list[str]]]:
    if promote_children is None:
        promote_children = PROMOTE_CHILDREN

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
            print(f'  INFO: Promoted parent "{parent_name}" removed — '
                  f'{child_count} children promoted')

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
        c4_id = make_id(name)
        if c4_id in used_ids:
            suffix = 2
            while f'{c4_id}_{suffix}' in used_ids:
                suffix += 1
            c4_id = f'{c4_id}_{suffix}'
        used_ids.add(c4_id)

        tags: list[str] = []
        if ac.source_folder == '!РАЗБОР':
            tags.append('to_review')
        elif ac.source_folder == '!External_services':
            tags.append('external')

        sys_extra_ids = list(extra_ids.get(name, []))

        systems[name] = System(
            c4_id=c4_id, name=name, archi_id=ac.archi_id,
            documentation=ac.documentation, metadata=build_metadata(ac), tags=tags,
            extra_archi_ids=sys_extra_ids,
        )

    # ── Build promoted_parents map: parent_archi_id → [child c4_ids] ──
    # Instead of remapping to one child, fan out to ALL children so that
    # downstream consumers (integrations, data_access) distribute links honestly.
    promoted_parents: dict[str, list[str]] = {}
    for parent_name, parent_aid in parent_remap.items():
        children_c4_ids = sorted(
            sys.c4_id for name, sys in systems.items()
            if name.startswith(f'{parent_name}.')
        )
        if children_c4_ids:
            promoted_parents[parent_aid] = children_c4_ids
            print(f'  INFO: Parent "{parent_name}" archi_id fans out to '
                  f'{len(children_c4_ids)} children')

    # ── Attach regular subsystems ────────────────────────────────────────
    for ac in subsystem_acs:
        parts = ac.name.split('.', 1)
        parent_name = parts[0]
        sub_name = parts[1] if len(parts) > 1 else ac.name
        if parent_name not in systems:
            print(f'  WARN: Subsystem "{ac.name}" has no parent system "{parent_name}", skipping')
            continue

        parent = systems[parent_name]
        sub_ids_used = {s.c4_id for s in parent.subsystems}
        sub_c4_id = make_id(sub_name)
        if sub_c4_id in sub_ids_used:
            suffix = 2
            while f'{sub_c4_id}_{suffix}' in sub_ids_used:
                suffix += 1
            sub_c4_id = f'{sub_c4_id}_{suffix}'

        tags: list[str] = []
        if ac.source_folder == '!РАЗБОР':
            tags.append('to_review')
        elif ac.source_folder == '!External_services':
            tags.append('external')

        parent.subsystems.append(Subsystem(
            c4_id=sub_c4_id, name=ac.name, archi_id=ac.archi_id,
            documentation=ac.documentation, metadata=build_metadata(ac), tags=tags,
        ))

    # ── Attach promoted subsystems (3-segment names) ─────────────────────
    for ac in promoted_subsystem_acs:
        parts = ac.name.split('.', 2)
        parent_name = f'{parts[0]}.{parts[1]}'
        sub_name = parts[2]
        if parent_name not in systems:
            print(f'  WARN: Promoted subsystem "{ac.name}" has no parent system "{parent_name}", skipping')
            continue

        parent = systems[parent_name]
        sub_ids_used = {s.c4_id for s in parent.subsystems}
        sub_c4_id = make_id(sub_name)
        if sub_c4_id in sub_ids_used:
            suffix = 2
            while f'{sub_c4_id}_{suffix}' in sub_ids_used:
                suffix += 1
            sub_c4_id = f'{sub_c4_id}_{suffix}'

        tags: list[str] = []
        if ac.source_folder == '!РАЗБОР':
            tags.append('to_review')
        elif ac.source_folder == '!External_services':
            tags.append('external')

        parent.subsystems.append(Subsystem(
            c4_id=sub_c4_id, name=ac.name, archi_id=ac.archi_id,
            documentation=ac.documentation, metadata=build_metadata(ac), tags=tags,
        ))

    # ── Phase 4: warn about suspicious parents ───────────────────────────
    parent_sub_count: dict[str, int] = {}
    for ac in subsystem_acs:
        parent_name = ac.name.split('.', 1)[0]
        parent_sub_count[parent_name] = parent_sub_count.get(parent_name, 0) + 1
    for parent_name, count in sorted(parent_sub_count.items()):
        if count >= PROMOTE_WARN_THRESHOLD and parent_name not in promote_children:
            print(f'  WARN: System "{parent_name}" has {count} subsystems — '
                  f'consider adding to PROMOTE_CHILDREN')

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
        print(f'  WARN: {unresolved} ApplicationInterface(s) could not be resolved to a system')

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
) -> list[Integration]:
    comp_c4_path, comp_system_id = _build_comp_c4_path(systems)

    raw_integrations: list[Integration] = []
    skipped = 0
    for rel in relationships:
        if rel.rel_type == 'AccessRelationship':
            continue
        if rel.rel_type in ('CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'):
            continue
        # Skip relationships involving ApplicationFunctions (not cross-system integrations)
        if rel.source_type == 'ApplicationFunction' or rel.target_type == 'ApplicationFunction':
            continue

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
        print(f'  INFO: Skipped {skipped} integration(s) with unresolvable endpoints')

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
    return deduped


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
        print(f'  INFO: Skipped {skipped} data access(es) with unresolvable endpoints')

    return sorted(results, key=lambda d: (d.system_path, d.entity_id))


def assign_domains(
    systems: list[System],
    domains: list[DomainInfo],
    promote_children: dict[str, str] | None = None,
) -> dict[str, list[System]]:
    """Assign each system to a primary domain based on view membership."""
    # Reverse map: archi_id → [(domain_c4_id, ...)]
    id_to_domains: dict[str, list[str]] = {}
    for domain in domains:
        for aid in domain.archi_ids:
            id_to_domains.setdefault(aid, []).append(domain.c4_id)

    result: dict[str, list[System]] = {d.c4_id: [] for d in domains}
    result['unassigned'] = []

    for sys in systems:
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
        promote_children = PROMOTE_CHILDREN
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
    for extra in EXTRA_DOMAIN_PATTERNS:
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


def apply_domain_prefix(
    integrations: list[Integration],
    data_access: list[DataAccess],
    sys_domain: dict[str, str],
) -> None:
    """Add domain prefix to integration and data access paths.

    Transforms 'efs' → 'channels.efs' based on domain assignment.
    """
    for intg in integrations:
        src_domain = sys_domain.get(intg.source_path, 'unassigned')
        tgt_domain = sys_domain.get(intg.target_path, 'unassigned')
        intg.source_path = f'{src_domain}.{intg.source_path}'
        intg.target_path = f'{tgt_domain}.{intg.target_path}'

    for da in data_access:
        domain = sys_domain.get(da.system_path, 'unassigned')
        da.system_path = f'{domain}.{da.system_path}'


def build_archi_to_c4_map(
    systems: list[System],
    sys_domain: dict[str, str],
    iface_c4_path: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a complete archi_id → c4_path mapping for all elements.

    Includes systems, subsystems, appFunctions, and optionally interfaces.
    Returns dict: archi_id → full c4 path (e.g. 'products.efs.account_service.fn_create')
    """
    result: dict[str, str] = {}
    for sys in systems:
        domain = sys_domain.get(sys.c4_id, 'unassigned')
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
                # Resolve system c4_id to domain.system path
                sys_c4_id = iface_path.split('.')[0]
                domain = sys_domain.get(sys_c4_id, 'unassigned')
                result[iface_id] = f'{domain}.{iface_path}'
    return result
