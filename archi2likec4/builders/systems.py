"""Builders: system, subsystem, function, and interface construction."""

import logging
import re
from collections.abc import Callable

from ..models import (
    PROMOTE_WARN_THRESHOLD,
    AppComponent,
    AppFunction,
    AppInterface,
    RawRelationship,
    Subsystem,
    System,
)
from ..utils import build_metadata, make_id, make_unique_id

logger = logging.getLogger(__name__)


def _extract_url(documentation: str) -> str | None:
    """Extract the first HTTP(S) URL from a documentation string."""
    if not documentation:
        return None
    url_match = re.search(r'https?://\S+', documentation)
    if url_match:
        return url_match.group(0).rstrip('.,;)')
    return None


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
    parent_name_fn: Callable[[AppComponent], str],
    sub_name_fn: Callable[[AppComponent], str],
    prop_map: dict[str, str] | None = None,
    standard_keys: list[str] | None = None,
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
        sub_c4_id = make_unique_id(make_id(sub_name), sub_ids_used)

        parent.subsystems.append(Subsystem(
            c4_id=sub_c4_id, name=ac.name, archi_id=ac.archi_id,
            documentation=ac.documentation,
            metadata=build_metadata(ac, prop_map=prop_map, standard_keys=standard_keys),
            tags=_assign_tags(ac.source_folder),
        ))


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


def build_systems(  # noqa: C901 — 4-phase system construction (collect, promote, dot-names, attach); see #27
    components: list[AppComponent],
    promote_children: dict[str, str] | None = None,
    promote_warn_threshold: int | None = None,
    reviewed_systems: list[str] | None = None,
    prop_map: dict[str, str] | None = None,
    standard_keys: list[str] | None = None,
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
        c4_id = make_unique_id(make_id(name), used_ids)
        used_ids.add(c4_id)

        tags = _assign_tags(ac.source_folder)

        if reviewed_systems and name in reviewed_systems and 'to_review' in tags:
            tags.remove('to_review')

        sys_extra_ids = list(extra_ids.get(name, []))

        systems[name] = System(
            c4_id=c4_id, name=name, archi_id=ac.archi_id,
            documentation=ac.documentation,
            metadata=build_metadata(ac, prop_map=prop_map, standard_keys=standard_keys),
            tags=tags,
            extra_archi_ids=sys_extra_ids,
        )

    # ── Attach regular subsystems ────────────────────────────────────────
    _attach_subsystems(
        systems, subsystem_acs,
        parent_name_fn=lambda ac: ac.name.split('.', 1)[0],
        sub_name_fn=lambda ac: ac.name.split('.', 1)[1] if '.' in ac.name else ac.name,
        prop_map=prop_map, standard_keys=standard_keys,
    )

    # ── Attach promoted subsystems (3-segment names) ─────────────────────
    # Ensure 2-segment parent systems exist for any 3+ segment promoted ACs
    for ac in promoted_subsystem_acs:
        parent_2seg = '.'.join(ac.name.split('.', 2)[:2])
        if parent_2seg not in systems:
            c4_id = make_unique_id(make_id(parent_2seg), used_ids)
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
        prop_map=prop_map, standard_keys=standard_keys,
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


def _build_rel_parent_map(relationships: list[RawRelationship] | None) -> dict[str, str]:
    """Build function_archi_id → component_archi_id from structural relationships."""
    parent_rel_types = {'CompositionRelationship', 'AssignmentRelationship', 'RealizationRelationship'}
    rel_parent: dict[str, str] = {}
    if relationships:
        for rel in relationships:
            if rel.rel_type in parent_rel_types:
                if rel.target_type == 'ApplicationFunction' and rel.source_type == 'ApplicationComponent':
                    rel_parent.setdefault(rel.target_id, rel.source_id)
                elif rel.source_type == 'ApplicationFunction' and rel.target_type == 'ApplicationComponent':
                    rel_parent.setdefault(rel.source_id, rel.target_id)
    return rel_parent


def _assign_unique_fn_id(fn: AppFunction, used_ids: set[str]) -> None:
    """Assign a unique c4_id to a function, avoiding collisions with used_ids."""
    c4_id = make_id(fn.name)
    if c4_id in used_ids:
        suffix = 2
        while f'{c4_id}_{suffix}' in used_ids:
            suffix += 1
        c4_id = f'{c4_id}_{suffix}'
    fn.c4_id = c4_id


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

    rel_parent = _build_rel_parent_map(relationships)

    orphans = 0
    for fn in functions:
        parent_id = rel_parent.get(fn.archi_id, fn.parent_archi_id)
        if not parent_id:
            orphans += 1
            continue
        if parent_id in archi_to_subsystem:
            _sys, sub = archi_to_subsystem[parent_id]
            _assign_unique_fn_id(fn, {f.c4_id for f in sub.functions})
            sub.functions.append(fn)
        elif parent_id in archi_to_system:
            sys = archi_to_system[parent_id]
            _assign_unique_fn_id(fn, {f.c4_id for f in sys.functions} | {s.c4_id for s in sys.subsystems})
            sys.functions.append(fn)
        elif promoted_parents and parent_id in promoted_parents:
            orphans += 1
        else:
            orphans += 1
    return orphans


def _resolve_iface_owner_by_name(
    iface_name: str,
    name_to_sys: dict[str, System],
    name_to_sub: dict[str, tuple[System, Subsystem]],
) -> tuple[System, Subsystem | None] | None:
    """Try to resolve interface ownership from its dot-delimited name."""
    parts = iface_name.split('.')
    if len(parts) >= 2:
        sub_name = f'{parts[0]}.{parts[1]}'
        if sub_name in name_to_sub:
            sys, sub = name_to_sub[sub_name]
            return (sys, sub)
        if parts[0] in name_to_sys:
            return (name_to_sys[parts[0]], None)
        # Promoted systems have dot-names (e.g. "EFS.Card_Service")
        if sub_name in name_to_sys:
            return (name_to_sys[sub_name], None)
    elif iface_name in name_to_sys:
        return (name_to_sys[iface_name], None)
    return None


def _resolve_iface_owners_from_rels(
    relationships: list[RawRelationship],
    comp_index: dict[str, tuple[System, Subsystem | None]],
    iface_ids: set[str],
) -> dict[str, tuple[System, Subsystem | None]]:
    """Resolve interface ownership from structural relationships."""
    _ownership_rels = {'CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'}
    owners: dict[str, tuple[System, Subsystem | None]] = {}
    for rel in relationships:
        if rel.rel_type not in _ownership_rels:
            continue
        if rel.source_type == 'ApplicationComponent' and rel.target_type == 'ApplicationInterface':
            if rel.source_id in comp_index and rel.target_id in iface_ids:
                owners[rel.target_id] = comp_index[rel.source_id]
        elif (rel.source_type == 'ApplicationInterface' and rel.target_type == 'ApplicationComponent'
                and rel.target_id in comp_index and rel.source_id in iface_ids):
            owners.setdefault(rel.source_id, comp_index[rel.target_id])
    return owners


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
    iface_owner = _resolve_iface_owners_from_rels(relationships, comp_index, set(iface_index.keys()))

    name_to_sys: dict[str, System] = {s.name: s for s in systems}
    name_to_sub: dict[str, tuple[System, Subsystem]] = {}
    for sys in systems:
        for sub in sys.subsystems:
            name_to_sub[sub.name] = (sys, sub)

    unresolved = 0
    for iface in interfaces:
        if iface.archi_id in iface_owner:
            continue
        owner = _resolve_iface_owner_by_name(iface.name, name_to_sys, name_to_sub)
        if owner:
            iface_owner[iface.archi_id] = owner
        else:
            unresolved += 1

    if unresolved:
        logger.warning('%d ApplicationInterface(s) could not be resolved to a system', unresolved)

    for iface_id, (owner_sys, owner_sub) in iface_owner.items():
        iface_obj = iface_index.get(iface_id)
        if not iface_obj:
            continue
        tgt = owner_sub if owner_sub else owner_sys
        if iface_obj.name not in owner_sys.api_interfaces:
            owner_sys.api_interfaces.append(iface_obj.name)
        url = _extract_url(iface_obj.documentation)
        if url:
            tgt.links.append((url, iface_obj.name))

    iface_c4_path: dict[str, str] = {}
    for iface_id, (owner_sys, owner_sub) in iface_owner.items():
        if owner_sub:
            iface_c4_path[iface_id] = f'{owner_sys.c4_id}.{owner_sub.c4_id}'
        else:
            iface_c4_path[iface_id] = owner_sys.c4_id
    return iface_c4_path
