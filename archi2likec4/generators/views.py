"""Generate landscape, domain, and solution view .c4 files."""

from __future__ import annotations

import logging

from ..models import RawRelationship, SolutionView
from ..utils import escape_str

logger = logging.getLogger(__name__)


def generate_landscape_view() -> str:
    """Generate the top-level landscape view."""
    return """\
views {

  view index {
    title 'Application Landscape'
    include *
    exclude * where kind is dataEntity
  }

}
"""


def generate_domain_functional_view(domain_c4_id: str, domain_name: str) -> str:
    """Generate a domain functional architecture view.

    Shows only system-level elements inside the domain.  Each system is
    clickable and navigates to its own detail view that shows subsystems
    and appFunctions.
    """
    return f"""\
views {{

  view {domain_c4_id}_functional of {domain_c4_id} {{
    title '{escape_str(domain_name)} - Functional Architecture'
    include *
    exclude * where kind is subsystem
    exclude * where kind is appFunction
    exclude * where kind is dataEntity
  }}

}}
"""


def generate_domain_integration_view(domain_c4_id: str, domain_name: str) -> str:
    """Generate a domain integration architecture view."""
    return f"""\
views {{

  view {domain_c4_id}_integration of {domain_c4_id} {{
    title '{escape_str(domain_name)} - Integration Architecture'
    include
      {domain_c4_id},
      -> {domain_c4_id} ->
  }}

}}
"""


def generate_persistence_map() -> str:
    """Generate persistence-map view."""
    return """\
// ── Persistence Map ────────────────────────────────────────
//
// Shows which systems access which data entities.
// To be refined when dataStore (container level) is modeled:
//   - Add dataStore elements inside systems
//   - Replace system -> dataEntity with dataStore -[persists]-> dataEntity
//   - Use 'include element.kind = dataStore' for focused views
//

views {

  view persistence_map {
    title 'Data Persistence Map'
    include
      element.kind = system,
      element.kind = dataEntity,
      * -> element.kind = dataEntity
  }

}
"""


def _system_path_from_c4(
    path: str,
    sys_subdomain: dict[str, str] | None,
    sys_ids: set[str] | None = None,
    sys_domain: dict[str, str] | None = None,
) -> str:
    """Extract the domain-qualified system path from a full c4 element path.

    Handles both 2-part (domain.system) and 3-part (domain.subdomain.system)
    paths as well as deeper paths (subsystems, functions).  When sys_subdomain
    is provided it is used to detect whether the second segment is a subdomain
    rather than the system itself.

    ``sys_ids`` is the set of all known system c4_ids.  When provided, the
    3-part path is only returned if parts[2] is a known system, preventing a
    false match when parts[2] is a subsystem whose archi_id coincidentally
    equals a system that has parts[1] as its subdomain.

    ``sys_domain`` maps system c4_id → domain name.  When provided, the
    3-part path is only returned if parts[2] belongs to the same domain as
    parts[0], preventing a false match when a same-named system exists in a
    different domain.
    """
    parts = path.split('.')
    # parts[2] is the system if its mapped subdomain equals parts[1]
    # (authoritative via sys_subdomain lookup),
    # AND parts[2] is a known system id (not a subsystem),
    # AND parts[2] belongs to the same domain as parts[0].
    # Note: parts[1] may itself also be a system id in the same domain
    # (subdomain name collision); that does NOT change the interpretation
    # because sys_subdomain.get(parts[2]) == parts[1] is definitive.
    if (
        sys_subdomain
        and len(parts) >= 3
        and sys_subdomain.get(parts[2]) == parts[1]
        and (sys_ids is None or parts[2] in sys_ids)
        and (sys_domain is None or sys_domain.get(parts[2]) == parts[0])
    ):
        return f'{parts[0]}.{parts[1]}.{parts[2]}'
    if len(parts) >= 2:
        return f'{parts[0]}.{parts[1]}'
    return path


def generate_solution_views(  # noqa: C901 — 3 view-type branches with distinct rendering logic; tracked as #2
    solution_views: list[SolutionView],
    archi_to_c4: dict[str, str],
    sys_domain: dict[str, str],
    relationships: list[RawRelationship] | None = None,
    promoted_archi_to_c4: dict[str, list[str]] | None = None,
    tech_archi_to_c4: dict[str, str] | None = None,
    entity_archi_ids: set[str] | None = None,
    deployment_map: list[tuple[str, str]] | None = None,
    sys_subdomain: dict[str, str] | None = None,
    deployment_env: str = 'prod',
) -> tuple[dict[str, str], int, int]:
    """Generate solution view .c4 files.

    Returns (files, total_unresolved, total_elements) where:
      - files: dict filename → file content string
      - total_unresolved: count of diagram elements that could not be resolved
      - total_elements: total diagram elements processed
    Groups functional and integration views for the same solution into one file.
    Uses actual diagram relationships for integration views when available.
    When a promoted parent archi_id appears, fans out to all children.

    Strict filtering rules per view type:
      - functional: exclude dataEntity/dataStore; only primary system gets .*
      - integration: entity cap (≤10); fan-out fix; orphan removal; exclude dataStore
      - deployment: app paths without .*; infra paths without .*; ancestor dedup; exclude dataEntity
    """
    if entity_archi_ids is None:
        entity_archi_ids = set()

    # Element count thresholds for QA-11 warnings
    _MAX_FUNCTIONAL = 25
    _MAX_INTEGRATION = 50  # ~20 systems + ~30 relationships
    _MAX_DEPLOYMENT = 40
    _MAX_INTEGRATION_ENTITIES = 10

    # Build deployment target lookup: app_c4_path → set of infra c4_ids
    _deploy_targets: dict[str, set[str]] = {}
    if deployment_map:
        for app_path, infra_id in deployment_map:
            _deploy_targets.setdefault(app_path, set()).add(infra_id)

    # Precompute system c4_id set for subdomain path disambiguation
    _sys_ids: set[str] = set(sys_domain.keys())

    # Build relationship lookup: rel_archi_id → (source_archi_id, target_archi_id, rel_type)
    rel_lookup: dict[str, tuple[str, str, str]] = {}
    # Structural rel types excluded from integration views (consistent with build_integrations)
    _structural_types = {'CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'}
    if relationships:
        for rel in relationships:
            rel_lookup[rel.rel_id] = (rel.source_id, rel.target_id, rel.rel_type)
    # Group views by solution slug
    by_solution: dict[str, list[SolutionView]] = {}
    for sv in solution_views:
        by_solution.setdefault(sv.solution, []).append(sv)

    files: dict[str, str] = {}
    used_view_ids: set[str] = set()
    total_unresolved = 0
    total_elements = 0
    for solution_slug, views in sorted(by_solution.items()):
        lines = [
            f'// ── Solution: {views[0].name.split(".", 1)[-1] if "." in views[0].name else views[0].name} ──',
            '',
            'views {',
            '',
        ]

        for sv in sorted(views, key=lambda v: v.view_type):
            # Resolve element archi_ids to c4 paths
            c4_paths: list[str] = []
            entity_paths: list[str] = []
            unresolved = 0

            if sv.view_type == 'deployment':
                # Deployment views resolve via tech_archi_to_c4, not archi_to_c4
                # Only count non-entity elements (entities are filtered out)
                non_entity_count = sum(1 for a in sv.element_archi_ids if a not in entity_archi_ids)
                total_elements += non_entity_count
                for aid in sv.element_archi_ids:
                    if aid in entity_archi_ids:
                        continue  # skip data entities on deployment views
                    if tech_archi_to_c4 and aid in tech_archi_to_c4:
                        c4_paths.append(tech_archi_to_c4[aid])
                    elif aid in archi_to_c4:
                        c4_paths.append(archi_to_c4[aid])
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                    else:
                        unresolved += 1
            elif sv.view_type == 'functional':
                # Functional views: skip data entities entirely
                non_entity_count = sum(1 for a in sv.element_archi_ids if a not in entity_archi_ids)
                total_elements += non_entity_count
                for aid in sv.element_archi_ids:
                    if aid in entity_archi_ids:
                        continue  # skip data entities
                    c4_path = archi_to_c4.get(aid)
                    if c4_path:
                        c4_paths.append(c4_path)
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                    else:
                        unresolved += 1
            elif sv.view_type == 'integration':
                # Integration views: separate app elements from data entities
                non_entity_count = sum(1 for a in sv.element_archi_ids if a not in entity_archi_ids)
                total_elements += non_entity_count
                for aid in sv.element_archi_ids:
                    if aid in entity_archi_ids:
                        # Resolve entity to its c4_id (stored in archi_to_c4 for entities)
                        entity_path = archi_to_c4.get(aid)
                        if entity_path:
                            entity_paths.append(entity_path)
                        continue
                    c4_path = archi_to_c4.get(aid)
                    if c4_path:
                        c4_paths.append(c4_path)
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                    else:
                        unresolved += 1
            total_unresolved += unresolved

            if not c4_paths and not entity_paths and sv.view_type != 'deployment':
                continue

            # Deduplicate paths
            unique_paths = list(dict.fromkeys(c4_paths))

            view_id = f'{sv.view_type}_{solution_slug}'
            if view_id in used_view_ids:
                suffix = 2
                while f'{view_id}_{suffix}' in used_view_ids:
                    suffix += 1
                view_id = f'{view_id}_{suffix}'
            used_view_ids.add(view_id)
            view_type_labels = {'functional': 'Functional', 'integration': 'Integration', 'deployment': 'Deployment'}
            view_type_label = view_type_labels.get(sv.view_type, sv.view_type.title())
            solution_label = sv.name.split('.', 1)[-1] if '.' in sv.name else sv.name
            title = f'{view_type_label} Architecture: {solution_label}'

            if sv.view_type == 'functional':
                # Functional view: include specific elements (systems + children)
                # Find unique system-level paths (domain.system) and count elements per system
                system_paths: list[str] = []
                seen_sys: set[str] = set()
                sys_element_count: dict[str, int] = {}
                for p in unique_paths:
                    if len(p.split('.')) >= 2:
                        sys_path = _system_path_from_c4(p, sys_subdomain, _sys_ids, sys_domain)
                        sys_element_count[sys_path] = sys_element_count.get(sys_path, 0) + 1
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)

                if len(system_paths) == 1:
                    # Scoped view for a single system
                    lines.append(f"  view {view_id} of {system_paths[0]} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append("    include *")
                    lines.append("    exclude * where kind is dataEntity")
                    lines.append("    exclude * where kind is dataStore")
                    lines.append("  }")
                    # QA-11: warn on element count (estimate)
                    est = sys_element_count.get(system_paths[0], 0)
                    if est > _MAX_FUNCTIONAL:
                        logger.warning('QA-11: functional view %s has ~%d elements '
                                        '(threshold: %d)', view_id, est, _MAX_FUNCTIONAL)
                else:
                    # Multi-system: determine primary system (most elements)
                    primary_sys = (
                        max(system_paths, key=lambda sp: sys_element_count.get(sp, 0))
                        if system_paths else None
                    )
                    lines.append(f"  view {view_id} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append("    include")
                    for sp in system_paths:
                        if sp == primary_sys:
                            lines.append(f"      {sp},")
                            lines.append(f"      {sp}.*,")
                        else:
                            lines.append(f"      {sp},")
                    # Remove trailing comma from last line
                    if lines[-1].endswith(','):
                        lines[-1] = lines[-1][:-1]
                    lines.append("    exclude * where kind is dataEntity")
                    lines.append("    exclude * where kind is dataStore")
                    lines.append("  }")
                    # QA-11: warn on element count
                    est = (
                        len(system_paths) + sys_element_count.get(primary_sys, 0)
                        if primary_sys else len(system_paths)
                    )
                    if est > _MAX_FUNCTIONAL:
                        logger.warning('QA-11: functional view %s has ~%d elements '
                                        '(threshold: %d)', view_id, est, _MAX_FUNCTIONAL)

            elif sv.view_type == 'integration':
                # Integration view: system-level with specific relationships from diagram
                system_paths = []
                seen_sys = set()
                for p in unique_paths:
                    if len(p.split('.')) >= 2:
                        sys_path = _system_path_from_c4(p, sys_subdomain, _sys_ids, sys_domain)
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)

                # Resolve diagram relationships to system-level pairs
                rel_pairs: list[tuple[str, str]] = []
                seen_pairs: set[tuple[str, str]] = set()
                for rel_id in sv.relationship_archi_ids:
                    if rel_id not in rel_lookup:
                        continue
                    src_aid, tgt_aid, rtype = rel_lookup[rel_id]
                    # Skip structural relationships (same filter as build_integrations)
                    if rtype in _structural_types or rtype == 'AccessRelationship':
                        continue
                    # Resolve endpoints — lift BOTH sides to system level BEFORE iteration
                    # This prevents N×M fan-out for promoted parents
                    src_sys_set: set[str] = set()
                    if src_aid in archi_to_c4:
                        src_path = archi_to_c4[src_aid]
                        src_sys_set.add(
                            _system_path_from_c4(src_path, sys_subdomain, _sys_ids, sys_domain)
                            if len(src_path.split('.')) >= 2 else src_path)
                    elif promoted_archi_to_c4 and src_aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[src_aid]:
                            src_sys_set.add(
                                _system_path_from_c4(child_path, sys_subdomain, _sys_ids, sys_domain)
                                if len(child_path.split('.')) >= 2 else child_path)

                    tgt_sys_set: set[str] = set()
                    if tgt_aid in archi_to_c4:
                        tgt_path = archi_to_c4[tgt_aid]
                        tgt_sys_set.add(
                            _system_path_from_c4(tgt_path, sys_subdomain, _sys_ids, sys_domain)
                            if len(tgt_path.split('.')) >= 2 else tgt_path)
                    elif promoted_archi_to_c4 and tgt_aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[tgt_aid]:
                            tgt_sys_set.add(
                                _system_path_from_c4(child_path, sys_subdomain, _sys_ids, sys_domain)
                                if len(child_path.split('.')) >= 2 else child_path)

                    if not src_sys_set or not tgt_sys_set:
                        continue

                    # One pair per unique (src_sys, tgt_sys) — no cross-product explosion
                    for src_sys in src_sys_set:
                        for tgt_sys in tgt_sys_set:
                            if src_sys == tgt_sys:
                                continue
                            pair = (src_sys, tgt_sys)
                            if pair not in seen_pairs:
                                seen_pairs.add(pair)
                                rel_pairs.append(pair)

                # Orphan removal: keep only systems that participate in relationships
                if rel_pairs:
                    connected_systems: set[str] = set()
                    for src, tgt in rel_pairs:
                        connected_systems.add(src)
                        connected_systems.add(tgt)
                    system_paths = [sp for sp in system_paths if sp in connected_systems]

                # Entity cap: include entities only if ≤ threshold
                include_entities = False
                resolved_entities: list[str] = []
                if sv.view_type == 'integration' and entity_paths:
                    resolved_entities = list(dict.fromkeys(entity_paths))
                    if len(resolved_entities) <= _MAX_INTEGRATION_ENTITIES:
                        include_entities = True
                    else:
                        logger.info('Integration view %s: %d data entities exceed cap (%d), excluding',
                                     view_id, len(resolved_entities), _MAX_INTEGRATION_ENTITIES)

                lines.append(f"  view {view_id} {{")
                lines.append(f"    title '{escape_str(title)}'")
                if not include_entities and resolved_entities:
                    cap = _MAX_INTEGRATION_ENTITIES
                    lines.append(f"    // {len(resolved_entities)} data entities excluded (>{cap} cap)")
                lines.append("    include")
                for sp in system_paths:
                    lines.append(f"      {sp},")
                if include_entities:
                    for ep in resolved_entities:
                        lines.append(f"      {ep},")
                if rel_pairs:
                    # Use specific relationship pairs from diagram
                    for src, tgt in rel_pairs:
                        lines.append(f"      {src} -> {tgt},")
                # Remove trailing comma
                if lines[-1].endswith(','):
                    lines[-1] = lines[-1][:-1]
                lines.append("    exclude * where kind is dataStore")
                lines.append("  }")
                # QA-11: warn on element count
                est = len(system_paths) + len(rel_pairs) + (len(resolved_entities) if include_entities else 0)
                if est > _MAX_INTEGRATION:
                    logger.warning('QA-11: integration view %s has ~%d elements '
                                    '(threshold: %d)', view_id, est, _MAX_INTEGRATION)

            elif sv.view_type == 'deployment':
                # Deployment view: collect infra paths from diagram and deployment_map.
                # App paths are NOT included in the view — they are placed inside infra
                # nodes via ``instanceOf`` in deployment/topology.c4.
                resolved_unique = list(dict.fromkeys(c4_paths))
                if resolved_unique:
                    tech_c4_values = set((tech_archi_to_c4 or {}).values())
                    app_paths = [rp for rp in resolved_unique if rp not in tech_c4_values]
                    infra_paths = [rp for rp in resolved_unique if rp in tech_c4_values]

                    # Enrich: pull mapped infra targets from deployment_map
                    # for app paths that don't already have infra in the diagram.
                    # Also check prefix matches (system path picks up subsystem mappings).
                    if app_paths and _deploy_targets:
                        seen_infra: set[str] = set(infra_paths)
                        for ap in app_paths:
                            # Exact match
                            for target in _deploy_targets.get(ap, set()):
                                if target not in seen_infra:
                                    seen_infra.add(target)
                                    infra_paths.append(target)
                            # Prefix match: system path picks up subsystem mappings
                            ap_prefix = ap + '.'
                            for map_key, targets in _deploy_targets.items():
                                if map_key.startswith(ap_prefix):
                                    for target in targets:
                                        if target not in seen_infra:
                                            seen_infra.add(target)
                                            infra_paths.append(target)

                    # Ancestor dedup for infra: if both 'loc' and 'loc.cluster.node' are present,
                    # keep only the ancestor (with .**) to avoid redundant includes.
                    deduped_infra: list[str] = []
                    infra_set = set(infra_paths)
                    for ip in infra_paths:
                        # Keep ip only if no other path is a proper ancestor of ip
                        has_ancestor = any(
                            other != ip and ip.startswith(other + '.')
                            for other in infra_set
                        )
                        if not has_ancestor:
                            deduped_infra.append(ip)
                    infra_paths = deduped_infra

                    if infra_paths:
                        lines.append(f"  deployment view {view_id} {{")
                        lines.append(f"    title '{escape_str(title)}'")
                        lines.append("    include")
                        # Infra paths: <env>.<path>.** to include all nested deployment nodes
                        for ip in infra_paths:
                            lines.append(f"      {deployment_env}.{ip}.**,")
                        if lines[-1].endswith(','):
                            lines[-1] = lines[-1][:-1]
                        lines.append("  }")
                        # QA-11: warn on element count
                        est = len(infra_paths)
                        if est > _MAX_DEPLOYMENT:
                            logger.warning('QA-11: deployment view %s has ~%d elements '
                                            '(threshold: %d)', view_id, est, _MAX_DEPLOYMENT)

            lines.append('')

        lines.append('}')
        lines.append('')
        # Only emit file if it contains at least one view block
        content = '\n'.join(lines)
        if '  view ' in content or '  deployment view ' in content:
            files[solution_slug] = content

    if total_unresolved:
        resolved = total_elements - total_unresolved
        ratio = total_unresolved / total_elements if total_elements else 0
        logger.warning('%d/%d diagram element(s) could not be resolved '
                        '(%.0f%% unresolved, %d resolved)',
                        total_unresolved, total_elements, ratio * 100, resolved)
    return files, total_unresolved, total_elements
