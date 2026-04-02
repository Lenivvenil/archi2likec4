"""Generate landscape, domain, and solution view .c4 files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import NamedTuple

from ..models import RawRelationship, SolutionView
from ..utils import escape_str, system_path_from_c4

logger = logging.getLogger(__name__)

# ── Environment detection from solution view names ────────────────────────
_ENV_PATTERN = re.compile(r'\(([^)]+)\)\s*$')
_ENV_MAP: dict[str, str] = {
    'dev': 'dev', 'development': 'dev',
    'test': 'test', 'testing': 'test',
    'stage': 'stage', 'staging': 'stage',
    'pre prod': 'pre_prod', 'pre-prod': 'pre_prod', 'preprod': 'pre_prod',
    'prod': 'prod', 'production': 'prod',
}


def _detect_env(name: str, default: str) -> str:
    """Extract deployment environment from solution view name suffix like ``(Dev)``.

    Returns *default* when no known environment suffix is found.
    """
    m = _ENV_PATTERN.search(name)
    if m:
        raw = m.group(1).strip().lower()
        return _ENV_MAP.get(raw, default)
    return default


@dataclass
class ViewContext:
    """Shared lookup tables for solution view generation."""

    archi_to_c4: dict[str, str]
    sys_domain: dict[str, str]
    promoted_archi_to_c4: dict[str, list[str]] | None = None
    tech_archi_to_c4: dict[str, str] | None = None
    entity_archi_ids: set[str] = field(default_factory=set)
    rel_lookup: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    deploy_targets: dict[str, set[str]] = field(default_factory=dict)
    sys_subdomain: dict[str, str] | None = None
    sys_ids: set[str] = field(default_factory=set)
    deployment_env: str = 'prod'


class _ViewData(NamedTuple):
    """Per-view resolved data passed to type-specific generators."""

    view_id: str
    title: str
    c4_paths: list[str]
    unique_paths: list[str]
    entity_paths: list[str]
    relationship_archi_ids: list[str]


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
    """Thin wrapper kept for backwards compatibility with tests.

    Delegates to :func:`archi2likec4.utils.system_path_from_c4`.
    """
    return system_path_from_c4(path, sys_subdomain, sys_ids, sys_domain)


def _resolve_elements(
    element_archi_ids: list[str],
    ctx: ViewContext,
    view_type: str,
) -> tuple[list[str], list[str], int, int]:
    """Resolve element archi_ids to c4 paths.

    Returns (c4_paths, entity_paths, unresolved_count, total_counted_elements).

    Resolution strategy per view_type:
      - deployment: skip entities; prefer tech_archi_to_c4, fallback archi_to_c4, then promoted
      - functional: skip entities; use archi_to_c4, then promoted
      - integration: separate entities into entity_paths; app elements via archi_to_c4 then promoted
    """
    c4_paths: list[str] = []
    entity_paths: list[str] = []
    unresolved = 0
    non_entity_count = sum(1 for a in element_archi_ids if a not in ctx.entity_archi_ids)
    use_tech = view_type == 'deployment'
    collect_entities = view_type == 'integration'

    for aid in element_archi_ids:
        if aid in ctx.entity_archi_ids:
            if collect_entities:
                entity_path = ctx.archi_to_c4.get(aid)
                if entity_path:
                    entity_paths.append(entity_path)
            continue

        # Deployment prefers tech_archi_to_c4 lookup
        if use_tech and ctx.tech_archi_to_c4 and aid in ctx.tech_archi_to_c4:
            c4_paths.append(ctx.tech_archi_to_c4[aid])
        elif aid in ctx.archi_to_c4:
            c4_paths.append(ctx.archi_to_c4[aid])
        elif ctx.promoted_archi_to_c4 and aid in ctx.promoted_archi_to_c4:
            c4_paths.extend(ctx.promoted_archi_to_c4[aid])
        else:
            unresolved += 1

    return c4_paths, entity_paths, unresolved, non_entity_count


def _enrich_infra_paths(
    app_paths: list[str],
    infra_paths: list[str],
    deploy_targets: dict[str, set[str]],
) -> None:
    """Enrich infra_paths in-place from deploy_targets for the given app_paths.

    Adds infra targets via exact match and prefix match (system path picks up
    subsystem mappings).
    """
    seen_infra: set[str] = set(infra_paths)
    for ap in app_paths:
        for target in deploy_targets.get(ap, set()):
            if target not in seen_infra:
                seen_infra.add(target)
                infra_paths.append(target)
        ap_prefix = ap + '.'
        for map_key, targets in deploy_targets.items():
            if map_key.startswith(ap_prefix):
                for target in targets:
                    if target not in seen_infra:
                        seen_infra.add(target)
                        infra_paths.append(target)


def _generate_deployment_view(vd: _ViewData, ctx: ViewContext) -> list[str]:
    """Generate deployment view lines for a single solution view.

    Returns list of .c4 lines for the deployment view block (empty if nothing to render).

    The deployment view shows infrastructure nodes that host application components.
    App paths are NOT included directly — they are placed inside infra nodes via
    ``instanceOf`` in deployment/topology.c4.

    Steps:
      1. Split resolved paths into app vs infra (using tech_archi_to_c4 values).
      2. Enrich infra paths from deployment_map for app paths without diagram infra.
      3. Ancestor dedup: if both 'loc' and 'loc.cluster.node' are present, keep ancestor.
      4. Emit ``deployment view`` block with ``<env>.<ip>.**`` includes.
    """
    resolved_unique = list(dict.fromkeys(vd.c4_paths))
    if not resolved_unique:
        return []

    tech_c4_values = set((ctx.tech_archi_to_c4 or {}).values())
    app_paths = [rp for rp in resolved_unique if rp not in tech_c4_values]
    infra_paths = [rp for rp in resolved_unique if rp in tech_c4_values]

    # Enrich: pull mapped infra targets from deployment_map
    if app_paths and ctx.deploy_targets:
        _enrich_infra_paths(app_paths, infra_paths, ctx.deploy_targets)

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

    if not infra_paths and not app_paths:
        return []

    # Enrich infra from reverse deploy_targets when only infra paths present
    if not app_paths and infra_paths and ctx.deploy_targets:
        infra_set = set(infra_paths)
        for _app_path, targets in ctx.deploy_targets.items():
            for t in targets:
                if t in infra_set or any(t.startswith(ip + '.') or ip.startswith(t + '.') for ip in infra_set):
                    infra_set.add(t)
        infra_paths = list(infra_set)

    env = ctx.deployment_env
    lines: list[str] = []
    lines.append(f"  deployment view {vd.view_id} {{")
    lines.append(f"    title '{escape_str(vd.title)}'")
    # LikeC4 deployment views: tag-based where clauses don't work reliably,
    # so we use targeted path includes instead.
    if infra_paths:
        for ip in sorted(set(infra_paths)):
            lines.append(f"    include {env}.{ip}.**")
    else:
        lines.append(f"    include {env}.**")
    lines.append("  }")
    return lines


def _collect_system_paths(
    unique_paths: list[str],
    ctx: ViewContext,
) -> tuple[list[str], dict[str, int]]:
    """Collect unique system-level paths from resolved c4 element paths.

    Returns (system_paths, element_count_per_system).
    """
    system_paths: list[str] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for p in unique_paths:
        if len(p.split('.')) >= 2:
            sp = _system_path_from_c4(p, ctx.sys_subdomain, ctx.sys_ids, ctx.sys_domain)
            counts[sp] = counts.get(sp, 0) + 1
            if sp not in seen:
                seen.add(sp)
                system_paths.append(sp)
    return system_paths, counts


def _generate_functional_view(vd: _ViewData, ctx: ViewContext) -> list[str]:
    """Generate functional view lines for a single solution view.

    Returns list of .c4 lines for the functional view block.
    """
    system_paths, sys_element_count = _collect_system_paths(vd.unique_paths, ctx)

    if not system_paths:
        return []

    lines: list[str] = []
    if len(system_paths) == 1:
        # Scoped view for a single system
        lines.append(f"  view {vd.view_id} of {system_paths[0]} {{")
        lines.append(f"    title '{escape_str(vd.title)}'")
        lines.append("    include *")
        lines.append("    exclude * where kind is dataEntity")
        lines.append("    exclude * where kind is dataStore")
        lines.append("  }")
        # QA-11: warn on element count (estimate)
        est = sys_element_count.get(system_paths[0], 0)
        if est > _MAX_FUNCTIONAL:
            logger.warning('QA-11: functional view %s has ~%d elements '
                            '(threshold: %d)', vd.view_id, est, _MAX_FUNCTIONAL)
    else:
        # Multi-system: determine primary system (most elements)
        primary_sys = max(system_paths, key=lambda sp: sys_element_count.get(sp, 0))
        lines.append(f"  view {vd.view_id} {{")
        lines.append(f"    title '{escape_str(vd.title)}'")
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
                            '(threshold: %d)', vd.view_id, est, _MAX_FUNCTIONAL)

    return lines


def _resolve_endpoint_to_systems(archi_id: str, ctx: ViewContext) -> set[str]:
    """Resolve a single relationship endpoint archi_id to system-level c4 paths."""
    result: set[str] = set()
    if archi_id in ctx.archi_to_c4:
        path = ctx.archi_to_c4[archi_id]
        result.add(
            _system_path_from_c4(path, ctx.sys_subdomain, ctx.sys_ids, ctx.sys_domain)
            if len(path.split('.')) >= 2 else path)
    elif ctx.promoted_archi_to_c4 and archi_id in ctx.promoted_archi_to_c4:
        for child_path in ctx.promoted_archi_to_c4[archi_id]:
            result.add(
                _system_path_from_c4(child_path, ctx.sys_subdomain, ctx.sys_ids, ctx.sys_domain)
                if len(child_path.split('.')) >= 2 else child_path)
    return result


# Structural rel types excluded from integration views (consistent with build_integrations)
_STRUCTURAL_TYPES = frozenset({'CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'})


def _resolve_rel_pairs(
    relationship_archi_ids: list[str],
    ctx: ViewContext,
) -> list[tuple[str, str]]:
    """Resolve diagram relationship archi_ids to unique system-level (src, tgt) pairs."""
    rel_pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for rel_id in relationship_archi_ids:
        if rel_id not in ctx.rel_lookup:
            continue
        src_aid, tgt_aid, rtype = ctx.rel_lookup[rel_id]
        if rtype in _STRUCTURAL_TYPES or rtype == 'AccessRelationship':
            continue
        src_sys_set = _resolve_endpoint_to_systems(src_aid, ctx)
        tgt_sys_set = _resolve_endpoint_to_systems(tgt_aid, ctx)
        if not src_sys_set or not tgt_sys_set:
            continue
        for src_sys in src_sys_set:
            for tgt_sys in tgt_sys_set:
                if src_sys == tgt_sys:
                    continue
                pair = (src_sys, tgt_sys)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    rel_pairs.append(pair)
    return rel_pairs


def _generate_integration_view(vd: _ViewData, ctx: ViewContext) -> list[str]:
    """Generate integration view lines for a single solution view.

    Returns list of .c4 lines for the integration view block.

    Steps:
      1. Lift resolved paths to system-level.
      2. Resolve diagram relationships to system-level pairs.
      3. Orphan removal: keep only systems that participate in relationships.
      4. Entity cap: include entities only if within threshold.
    """
    system_paths, _ = _collect_system_paths(vd.unique_paths, ctx)

    # Resolve diagram relationships to system-level pairs
    rel_pairs = _resolve_rel_pairs(vd.relationship_archi_ids, ctx)

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
    if vd.entity_paths:
        resolved_entities = list(dict.fromkeys(vd.entity_paths))
        if len(resolved_entities) <= _MAX_INTEGRATION_ENTITIES:
            include_entities = True
        else:
            logger.info('Integration view %s: %d data entities exceed cap (%d), excluding',
                         vd.view_id, len(resolved_entities), _MAX_INTEGRATION_ENTITIES)

    # Nothing to include — skip this view
    has_includable = system_paths or rel_pairs or (resolved_entities and include_entities)
    if not has_includable:
        return []

    lines: list[str] = []
    lines.append(f"  view {vd.view_id} {{")
    lines.append(f"    title '{escape_str(vd.title)}'")
    if not include_entities and resolved_entities:
        lines.append(f"    // {len(resolved_entities)} data entities excluded (>{_MAX_INTEGRATION_ENTITIES} cap)")
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
                        '(threshold: %d)', vd.view_id, est, _MAX_INTEGRATION)

    return lines


# Element count thresholds for QA-11 warnings
_MAX_FUNCTIONAL = 25
_MAX_INTEGRATION = 50  # ~20 systems + ~30 relationships
_MAX_DEPLOYMENT = 40
_MAX_INTEGRATION_ENTITIES = 10

_VIEW_TYPE_LABELS = {'functional': 'Functional', 'integration': 'Integration', 'deployment': 'Deployment'}


def _make_unique_view_id(view_type: str, solution_slug: str, used: set[str]) -> str:
    """Generate a unique view id, appending a numeric suffix on collision."""
    view_id = f'{view_type}_{solution_slug}'
    if view_id in used:
        suffix = 2
        while f'{view_id}_{suffix}' in used:
            suffix += 1
        view_id = f'{view_id}_{suffix}'
    used.add(view_id)
    return view_id


def _build_rel_lookup(relationships: list[RawRelationship] | None) -> dict[str, tuple[str, str, str]]:
    """Build relationship lookup: rel_archi_id -> (source_archi_id, target_archi_id, rel_type)."""
    if not relationships:
        return {}
    return {rel.rel_id: (rel.source_id, rel.target_id, rel.rel_type) for rel in relationships}


def _build_deploy_targets(deployment_map: list[tuple[str, str]] | None) -> dict[str, set[str]]:
    """Build deployment target lookup: app_c4_path -> set of infra c4_ids."""
    targets: dict[str, set[str]] = {}
    if deployment_map:
        for app_path, infra_id in deployment_map:
            targets.setdefault(app_path, set()).add(infra_id)
    return targets


def _dispatch_view(
    sv: SolutionView,
    solution_slug: str,
    used_view_ids: set[str],
    ctx: ViewContext,
) -> tuple[list[str], int, int]:
    """Resolve elements and dispatch to the appropriate per-type view generator.

    Returns (view_lines, unresolved_count, non_entity_count).
    """
    # Skip unsupported view types before resolution to avoid inflating metrics
    if sv.view_type not in _VIEW_TYPE_LABELS:
        return [], 0, 0

    c4_paths, entity_paths, unresolved, non_entity_count = _resolve_elements(
        sv.element_archi_ids, ctx, sv.view_type,
    )

    if not c4_paths and not entity_paths and sv.view_type != 'deployment':
        return [], unresolved, non_entity_count

    unique_paths = list(dict.fromkeys(c4_paths))
    view_id = _make_unique_view_id(sv.view_type, solution_slug, used_view_ids)
    label = _VIEW_TYPE_LABELS[sv.view_type]
    solution_label = sv.name.split('.', 1)[-1] if '.' in sv.name else sv.name
    title = f'{label} Architecture: {solution_label}'

    vd = _ViewData(
        view_id=view_id,
        title=title,
        c4_paths=c4_paths,
        unique_paths=unique_paths,
        entity_paths=entity_paths,
        relationship_archi_ids=sv.relationship_archi_ids,
    )

    if sv.view_type == 'functional':
        lines = _generate_functional_view(vd, ctx)
    elif sv.view_type == 'integration':
        lines = _generate_integration_view(vd, ctx)
    else:  # deployment
        # NOTE: _detect_env is available but not activated until the deployment
        # model declares multiple environments (dev/test/stage/prod).
        # Currently all topology lives under a single environment (config.deployment_env).
        lines = _generate_deployment_view(vd, ctx)

    return lines, unresolved, non_entity_count


def _group_by_solution(solution_views: list[SolutionView]) -> dict[str, list[SolutionView]]:
    """Group solution views by their solution slug."""
    by_solution: dict[str, list[SolutionView]] = {}
    for sv in solution_views:
        by_solution.setdefault(sv.solution, []).append(sv)
    return by_solution


def build_view_context(  # noqa: PLR0913  # factory for ViewContext dataclass
    archi_to_c4: dict[str, str],
    sys_domain: dict[str, str],
    relationships: list[RawRelationship] | None = None,
    *,
    promoted_archi_to_c4: dict[str, list[str]] | None = None,
    tech_archi_to_c4: dict[str, str] | None = None,
    entity_archi_ids: set[str] | None = None,
    deployment_map: list[tuple[str, str]] | None = None,
    sys_subdomain: dict[str, str] | None = None,
    deployment_env: str = 'prod',
) -> ViewContext:
    """Build a ViewContext from raw parsed/built data.

    Converts raw data into lookup structures:
      - relationships → rel_lookup
      - deployment_map → deploy_targets
      - sys_domain.keys() → sys_ids
    """
    return ViewContext(
        archi_to_c4=archi_to_c4,
        sys_domain=sys_domain,
        promoted_archi_to_c4=promoted_archi_to_c4,
        tech_archi_to_c4=tech_archi_to_c4,
        entity_archi_ids=entity_archi_ids if entity_archi_ids is not None else set(),
        deploy_targets=_build_deploy_targets(deployment_map),
        sys_ids=set(sys_domain.keys()),
        rel_lookup=_build_rel_lookup(relationships),
        sys_subdomain=sys_subdomain,
        deployment_env=deployment_env,
    )


def generate_solution_views(
    solution_views: list[SolutionView],
    ctx: ViewContext,
) -> tuple[dict[str, str], int, int]:
    """Generate solution view .c4 files.

    Returns (files, total_unresolved, total_elements).
    Dispatches to per-type generators via ``_dispatch_view``.
    """
    by_solution = _group_by_solution(solution_views)

    files: dict[str, str] = {}
    used_view_ids: set[str] = set()
    total_unresolved = 0
    total_elements = 0
    for solution_slug, views in sorted(by_solution.items()):
        sol_name = views[0].name.split('.', 1)[-1] if '.' in views[0].name else views[0].name
        lines = [f'// ── Solution: {sol_name} ──', '', 'views {', '']

        for sv in sorted(views, key=lambda v: v.view_type):
            view_lines, unresolved, count = _dispatch_view(
                sv, solution_slug, used_view_ids, ctx,
            )
            total_elements += count
            total_unresolved += unresolved
            if view_lines:
                lines.extend(view_lines)
                lines.append('')

        lines.append('}')
        lines.append('')
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
