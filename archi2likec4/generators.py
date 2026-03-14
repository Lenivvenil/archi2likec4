"""Generators: produce LikeC4 .c4 file content from the output model."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .models import (
    AppFunction,
    DataAccess,
    DataEntity,
    DeploymentNode,
    Integration,
    RawRelationship,
    SolutionView,
    Subdomain,
    Subsystem,
    System,
)
from .i18n import get_audit_label
from .utils import escape_str

if TYPE_CHECKING:
    from .audit_data import AuditIncident
    from .config import ConvertConfig


# Maximum description length before truncation (characters).
_MAX_DESC_LEN = 500
_MAX_FN_DESC_LEN = 300

# ── Renderers (internal) ────────────────────────────────────────────────

def _render_system(sys: System, lines: list[str], indent: int = 2) -> None:
    pad = ' ' * indent
    title = escape_str(sys.name)
    lines.append(f"{pad}{sys.c4_id} = system '{title}' {{")
    for tag in sys.tags:
        lines.append(f'{pad}  #{tag}')
    if sys.documentation:
        desc = escape_str(sys.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sys.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{sys.archi_id}'")
    for key, value in sys.metadata.items():
        lines.append(f"{pad}    {key} '{escape_str(value)}'")
    if sys.api_interfaces:
        ifaces_str = '; '.join(sys.api_interfaces)
        lines.append(f"{pad}    api_interfaces '{escape_str(ifaces_str)}'")
    lines.append(f'{pad}  }}')
    # Subsystems and functions are rendered in systems/{c4_id}.c4 via extend
    lines.append(f'{pad}}}')


def _render_subsystem(sub: Subsystem, lines: list[str], indent: int = 4) -> None:
    pad = ' ' * indent
    title = escape_str(sub.name)
    lines.append(f"{pad}{sub.c4_id} = subsystem '{title}' {{")
    for tag in sub.tags:
        lines.append(f'{pad}  #{tag}')
    if sub.documentation:
        desc = escape_str(sub.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sub.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{sub.archi_id}'")
    for key, value in sub.metadata.items():
        lines.append(f"{pad}    {key} '{escape_str(value)}'")
    lines.append(f'{pad}  }}')
    # Render nested appFunctions
    if sub.functions:
        lines.append('')
        for fn in sorted(sub.functions, key=lambda f: f.name):
            _render_appfunction(fn, lines, indent=indent + 2)
    lines.append(f'{pad}}}')


def _render_appfunction(fn: AppFunction, lines: list[str], indent: int = 6) -> None:
    pad = ' ' * indent
    title = escape_str(fn.name)
    if fn.documentation:
        desc = escape_str(fn.documentation)
        if len(desc) > _MAX_FN_DESC_LEN:
            desc = desc[:_MAX_FN_DESC_LEN - 3] + '...'
        lines.append(f"{pad}{fn.c4_id} = appFunction '{title}' {{")
        lines.append(f"{pad}  description '{desc}'")
        lines.append(f"{pad}  metadata {{")
        lines.append(f"{pad}    archi_id '{fn.archi_id}'")
        lines.append(f"{pad}  }}")
        lines.append(f'{pad}}}')
    else:
        lines.append(f"{pad}{fn.c4_id} = appFunction '{title}' {{")
        lines.append(f"{pad}  metadata {{")
        lines.append(f"{pad}    archi_id '{fn.archi_id}'")
        lines.append(f"{pad}  }}")
        lines.append(f'{pad}}}')


# ── Generators ───────────────────────────────────────────────────────────

def generate_spec() -> str:
    return """\
specification {

  // ── Colors ──────────────────────────────────────────────
  color archi-app #7EB8DA
  color archi-app-light #BDE0F0
  color archi-data #F0D68A
  color archi-store #B0B0B0

  // ── Business domains ──────────────────────────────────
  element domain {
    style {
      shape rectangle
      color amber
    }
  }

  element subdomain {
    style {
      shape rectangle
      color secondary
    }
  }

  // ── Application landscape ──────────────────────────────
  element system {
    style {
      shape component
      color archi-app
    }
  }

  element subsystem {
    style {
      shape component
      color archi-app-light
    }
  }

  element appFunction {
    style {
      shape rectangle
      color archi-app-light
    }
  }

  // ── Data layer ─────────────────────────────────────────
  element dataEntity {
    style {
      shape document
      color archi-data
    }
  }

  element dataStore {
    style {
      shape cylinder
      color archi-store
    }
  }

  // ── Infrastructure / Deployment ──────────────────────
  color archi-tech #93D275
  color archi-tech-light #C5E6B8

  element infraNode {
    style {
      shape rectangle
      color archi-tech
    }
  }

  element infraSoftware {
    style {
      shape cylinder
      color archi-tech-light
    }
  }

  element infraZone {
    style {
      shape rectangle
      color archi-tech
      border dotted
    }
  }

  element infraLocation {
    style {
      shape rectangle
      color archi-tech
      border dashed
    }
  }

  // ── Relationship kinds ─────────────────────────────────
  relationship persists {
    color archi-store
    line dashed
  }

  relationship deployedOn {
    color archi-tech
    line dashed
  }

  // ── Tags ───────────────────────────────────────────────
  tag to_review
  tag external
  tag entity
  tag store
  tag infrastructure
  tag cluster
  tag device
  tag network
}
"""


def generate_domain_c4(
    domain_c4_id: str,
    domain_name: str,
    systems: list[System],
    subdomains: list[Subdomain] | None = None,
) -> str:
    """Generate a domain .c4 file: domain element with nested systems.

    If subdomains are provided, systems assigned to a subdomain are wrapped
    in a ``subdomain`` block; remaining systems are placed directly under the
    domain (fallback).
    """
    lines = [
        f'// ── {domain_name} ──────────────────────────────────────',
        'model {',
        '',
        f"  {domain_c4_id} = domain '{escape_str(domain_name)}' {{",
        '',
    ]

    domain_subdomains = [sd for sd in (subdomains or []) if sd.domain_id == domain_c4_id]
    if domain_subdomains:
        # Build lookup: subdomain c4_id → system c4_id set
        sd_system_sets: dict[str, set[str]] = {
            sd.c4_id: set(sd.system_ids) for sd in domain_subdomains
        }
        # Map each system to its subdomain (if any)
        sys_by_subdomain: dict[str, list[System]] = {}
        ungrouped: list[System] = []
        for sys in sorted(systems, key=lambda s: s.name):
            if sys.subdomain and sys.subdomain in sd_system_sets:
                sys_by_subdomain.setdefault(sys.subdomain, []).append(sys)
            else:
                ungrouped.append(sys)

        # Render subdomain blocks
        for sd in sorted(domain_subdomains, key=lambda s: s.name):
            sd_systems = sys_by_subdomain.get(sd.c4_id, [])
            if not sd_systems:
                continue
            lines.append(f"    {sd.c4_id} = subdomain '{escape_str(sd.name)}' {{")
            lines.append('')
            for sys in sd_systems:
                _render_system(sys, lines, indent=6)
                lines.append('')
            lines.append('    }')
            lines.append('')

        # Render ungrouped systems directly under domain
        for sys in ungrouped:
            _render_system(sys, lines, indent=4)
            lines.append('')
    else:
        for sys in sorted(systems, key=lambda s: s.name):
            _render_system(sys, lines, indent=4)
            lines.append('')

    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_system_detail_c4(domain_c4_id: str, sys: System) -> str:
    """Generate systems/{c4_id}.c4 with extend block + scoped detail view.

    The detail view (``view {sys_id}_detail of {domain}.{sys_id}``) enables
    drill-down navigation: clicking a system on the domain-level functional
    view opens this view showing its subsystems and appFunctions.

    If the system belongs to a subdomain, the path is
    ``{domain}.{subdomain}.{system}`` instead of ``{domain}.{system}``.
    """
    if sys.subdomain:
        full_path = f'{domain_c4_id}.{sys.subdomain}.{sys.c4_id}'
    else:
        full_path = f'{domain_c4_id}.{sys.c4_id}'
    lines = [
        f'// ── {sys.name} (detail) ──────────────────────────────────',
        'model {',
        '',
        f'  extend {full_path} {{',
        '',
    ]

    for sub in sorted(sys.subsystems, key=lambda s: s.name):
        _render_subsystem(sub, lines, indent=4)
        lines.append('')

    # Functions directly on system (no subsystem parent)
    for fn in sorted(sys.functions, key=lambda f: f.name):
        _render_appfunction(fn, lines, indent=4)

    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')

    # ── Scoped detail view for drill-down navigation ──
    lines.append('views {')
    lines.append('')
    lines.append(f'  view {sys.c4_id}_detail of {full_path} {{')
    lines.append(f"    title '{escape_str(sys.name)}'")
    lines.append('    include *')
    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_relationships(integrations: list[Integration]) -> str:
    """Generate relationships.c4: cross-domain integrations model block."""
    lines = [
        '// ── Cross-domain integrations ──────────────────────────',
        'model {',
        '',
    ]
    if not integrations:
        lines.append('  // No integrations found')
    else:
        for intg in integrations:
            if intg.name:
                label = escape_str(intg.name)
                lines.append(f"  {intg.source_path} -> {intg.target_path} '{label}'")
            else:
                lines.append(f"  {intg.source_path} -> {intg.target_path}")
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_entities(entities: list[DataEntity], data_access: list[DataAccess]) -> str:
    """Generate entities.c4: dataEntity elements + access relationships."""
    lines = [
        '// ── Data Entities ───────────────────────────────────────',
        '//',
        '// Migrated from ArchiMate DataObject as-is.',
        '// Quality is low (Kafka topics, internal structures, etc.).',
        '//',
        '// TODO: Canonical data model (Customer, Account, Loan, etc.)',
        '//       to be designed separately. These migrated entities',
        '//       preserve the original ArchiMate relationships and',
        '//       serve as an inventory for future data governance.',
        '//',
        '// Target pattern (when dataStore is added at container level):',
        '//   dataStore -[persists]-> dataEntity',
        '//',
        '// Current: domain.system -> dataEntity (migrated AccessRelationship)',
        '//',
        '',
        'model {',
        '',
    ]

    if not entities:
        lines.append('  // No data entities found')
    else:
        for entity in entities:
            title = escape_str(entity.name)
            if entity.documentation:
                desc = escape_str(entity.documentation)
                if len(desc) > 300:
                    desc = desc[:297] + '...'
                lines.append(f"  {entity.c4_id} = dataEntity '{title}' {{")
                lines.append('    #entity')
                lines.append(f"    description '{desc}'")
                lines.append("    metadata {")
                lines.append(f"      archi_id '{entity.archi_id}'")
                lines.append("    }")
                lines.append("  }")
            else:
                lines.append(f"  {entity.c4_id} = dataEntity '{title}' {{")
                lines.append('    #entity')
                lines.append("    metadata {")
                lines.append(f"      archi_id '{entity.archi_id}'")
                lines.append("    }")
                lines.append("  }")
            lines.append('')

    # Access relationships (migrated from ArchiMate AccessRelationship)
    if data_access:
        lines.append('  // ── System → DataEntity access (migrated from ArchiMate) ──')
        lines.append('  // These represent which systems work with which data entities.')
        lines.append('  // To be replaced by: dataStore -[persists]-> dataEntity')
        lines.append('  // when container/store level is modeled.')
        lines.append('')
        for da in data_access:
            if da.name:
                label = escape_str(da.name)
                lines.append(f"  {da.system_path} -> {da.entity_id} '{label}'")
            else:
                lines.append(f"  {da.system_path} -> {da.entity_id}")
        lines.append('')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


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


def generate_solution_views(
    solution_views: list[SolutionView],
    archi_to_c4: dict[str, str],
    sys_domain: dict[str, str],
    relationships: list[RawRelationship] | None = None,
    promoted_archi_to_c4: dict[str, list[str]] | None = None,
    tech_archi_to_c4: dict[str, str] | None = None,
    entity_archi_ids: set[str] | None = None,
    deployment_map: list[tuple[str, str]] | None = None,
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
      - deployment: app paths without .*; infra paths with .*; ancestor dedup; exclude dataEntity
    """
    _logger = logging.getLogger('archi2likec4')
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
            system_c4_ids: set[str] = set()  # track unique systems

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
                        parts = c4_path.split('.')
                        if len(parts) >= 2:
                            system_c4_ids.add(parts[1])
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                            parts = child_path.split('.')
                            if len(parts) >= 2:
                                system_c4_ids.add(parts[1])
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
                        parts = c4_path.split('.')
                        if len(parts) >= 2:
                            system_c4_ids.add(parts[1])
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                            parts = child_path.split('.')
                            if len(parts) >= 2:
                                system_c4_ids.add(parts[1])
                    else:
                        unresolved += 1
            else:
                total_elements += len(sv.element_archi_ids)
                for aid in sv.element_archi_ids:
                    c4_path = archi_to_c4.get(aid)
                    if c4_path:
                        c4_paths.append(c4_path)
                        parts = c4_path.split('.')
                        if len(parts) >= 2:
                            system_c4_ids.add(parts[1])
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[aid]:
                            c4_paths.append(child_path)
                            parts = child_path.split('.')
                            if len(parts) >= 2:
                                system_c4_ids.add(parts[1])
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
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
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
                        _logger.warning('QA-11: functional view %s has ~%d elements '
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
                        _logger.warning('QA-11: functional view %s has ~%d elements '
                                        '(threshold: %d)', view_id, est, _MAX_FUNCTIONAL)

            elif sv.view_type == 'integration':
                # Integration view: system-level with specific relationships from diagram
                system_paths = []
                seen_sys = set()
                for p in unique_paths:
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
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
                        src_parts = src_path.split('.')
                        src_sys_set.add(f'{src_parts[0]}.{src_parts[1]}' if len(src_parts) >= 2 else src_path)
                    elif promoted_archi_to_c4 and src_aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[src_aid]:
                            parts = child_path.split('.')
                            src_sys_set.add(f'{parts[0]}.{parts[1]}' if len(parts) >= 2 else child_path)

                    tgt_sys_set: set[str] = set()
                    if tgt_aid in archi_to_c4:
                        tgt_path = archi_to_c4[tgt_aid]
                        tgt_parts = tgt_path.split('.')
                        tgt_sys_set.add(f'{tgt_parts[0]}.{tgt_parts[1]}' if len(tgt_parts) >= 2 else tgt_path)
                    elif promoted_archi_to_c4 and tgt_aid in promoted_archi_to_c4:
                        for child_path in promoted_archi_to_c4[tgt_aid]:
                            parts = child_path.split('.')
                            tgt_sys_set.add(f'{parts[0]}.{parts[1]}' if len(parts) >= 2 else child_path)

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
                        _logger.info('Integration view %s: %d data entities exceed cap (%d), excluding',
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
                    _logger.warning('QA-11: integration view %s has ~%d elements '
                                    '(threshold: %d)', view_id, est, _MAX_INTEGRATION)

            elif sv.view_type == 'deployment':
                # Deployment view: separate app paths from infra paths
                resolved_unique = list(dict.fromkeys(c4_paths))
                if resolved_unique:
                    app_paths: list[str] = []
                    infra_paths: list[str] = []
                    for rp in resolved_unique:
                        if tech_archi_to_c4 and rp in tech_archi_to_c4.values():
                            infra_paths.append(rp)
                        elif any(rp == v for v in (tech_archi_to_c4 or {}).values()):
                            infra_paths.append(rp)
                        else:
                            # Check if it was resolved from archi_to_c4 (app element)
                            app_paths.append(rp)

                    # Re-classify: paths from tech_archi_to_c4 are infra, from archi_to_c4 are app
                    tech_c4_values = set((tech_archi_to_c4 or {}).values())
                    app_paths = [rp for rp in resolved_unique if rp not in tech_c4_values]
                    infra_paths = [rp for rp in resolved_unique if rp in tech_c4_values]

                    # Enrich: if app paths have no corresponding infra paths from
                    # the diagram, pull mapped targets from deployment_map
                    if app_paths and not infra_paths and _deploy_targets:
                        seen_infra: set[str] = set()
                        for ap in app_paths:
                            for target in _deploy_targets.get(ap, set()):
                                if target not in seen_infra:
                                    seen_infra.add(target)
                                    infra_paths.append(target)

                    # Ancestor dedup for infra: if both 'loc' and 'loc.cluster.node' are present,
                    # remove 'loc' — keep only the most specific paths
                    deduped_infra: list[str] = []
                    infra_set = set(infra_paths)
                    for ip in infra_paths:
                        # Check if any other infra path is a descendant of ip
                        has_descendant = any(
                            other != ip and other.startswith(ip + '.')
                            for other in infra_set
                        )
                        if not has_descendant:
                            deduped_infra.append(ip)
                    infra_paths = deduped_infra

                    lines.append(f"  view {view_id} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append("    include")
                    # App paths: without .* (don't expand appFunction)
                    for ap in app_paths:
                        lines.append(f"      {ap},")
                    # Infra paths: no .* — only elements from the Archi view
                    # are included (stand-specific nodes only)
                    for ip in infra_paths:
                        lines.append(f"      {ip},")
                    if lines[-1].endswith(','):
                        lines[-1] = lines[-1][:-1]
                    lines.append("    exclude * where kind is dataEntity")
                    lines.append("  }")
                    # QA-11: warn on element count
                    est = len(app_paths) + len(infra_paths)
                    if est > _MAX_DEPLOYMENT:
                        _logger.warning('QA-11: deployment view %s has ~%d elements '
                                        '(threshold: %d)', view_id, est, _MAX_DEPLOYMENT)

            lines.append('')

        lines.append('}')
        lines.append('')
        # Only emit file if it contains at least one view block
        content = '\n'.join(lines)
        if '  view ' in content:
            files[solution_slug] = content

    if total_unresolved:
        resolved = total_elements - total_unresolved
        ratio = total_unresolved / total_elements if total_elements else 0
        _logger.warning('%d/%d diagram element(s) could not be resolved '
                        '(%.0f%% unresolved, %d resolved)',
                        total_unresolved, total_elements, ratio * 100, resolved)
    return files, total_unresolved, total_elements


# ── Deployment generators ───────────────────────────────────────────────

def _render_deployment_node(node: DeploymentNode, lines: list[str], indent: int) -> None:
    """Recursively render a DeploymentNode and its children."""
    pad = ' ' * indent
    title = escape_str(node.name)
    lines.append(f"{pad}{node.c4_id} = {node.kind} '{title}' {{")
    if node.documentation:
        desc = escape_str(node.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
        lines.append(f"{pad}  description '{desc}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{node.archi_id}'")
    lines.append(f"{pad}    tech_type '{node.tech_type}'")
    lines.append(f'{pad}  }}')
    for child in sorted(node.children, key=lambda c: c.name):
        lines.append('')
        _render_deployment_node(child, lines, indent + 2)
    lines.append(f'{pad}}}')


def generate_deployment_c4(nodes: list[DeploymentNode]) -> str:
    """Generate deployment/topology.c4 with infrastructure nodes and containers."""
    lines = [
        '// ── Deployment Topology ──────────────────────────────────',
        'model {',
        '',
    ]
    for node in sorted(nodes, key=lambda n: n.name):
        _render_deployment_node(node, lines, indent=2)
        lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_mapping_c4(mapping: list[tuple[str, str]]) -> str:
    """Generate deployment/mapping.c4 with app→infrastructure relationships."""
    lines = [
        '// ── Deployment Mapping (App → Infrastructure) ────────────',
        'model {',
        '',
    ]
    for app_path, node_id in sorted(mapping):
        lines.append(f'  {app_path} -[deployedOn]-> {node_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_datastore_mapping_c4(links: list[tuple[str, str]]) -> str:
    """Generate deployment/datastore-mapping.c4 with dataStore→dataEntity relationships."""
    lines = [
        '// ── DataStore → DataEntity (persistence layer) ─────────────',
        'model {',
        '',
    ]
    for store_path, entity_id in sorted(links):
        lines.append(f'  {store_path} -[persists]-> {entity_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_view() -> str:
    """Generate views/deployment-architecture.c4."""
    return """\
views {

  view deployment_architecture {
    title 'Deployment Architecture'

    include
      element.kind = infraLocation,
      element.kind = infraZone,
      element.kind = infraNode,
      element.kind = infraSoftware,
      element.kind = dataStore
  }

}
"""


# ── Audit report ──────────────────────────────────────────────────────────


def generate_audit_md(
    built: object,
    sv_unresolved: int,
    sv_total: int,
    config: ConvertConfig,
) -> str:
    """Generate AUDIT.md — quality incident register for ArchiMate repository owners.

    Delegates all logic to compute_audit_incidents() (audit_data.py) as the
    single source of truth, then renders results as markdown. Respects
    config.audit_suppress_incidents to skip entire QA categories.
    Fully bilingual (ru/en) via config.language.
    """
    from . import __version__
    from .audit_data import compute_audit_incidents

    lang: str = getattr(config, 'language', 'ru')
    summary, all_incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)

    # Filter out suppressed and zero-count incidents (keep for suppressed_count tracking)
    incidents = [inc for inc in all_incidents if not inc.suppressed and inc.count > 0]

    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    # ── Header ────────────────────────────────────────────────────────
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    header = (
        f'# {_L("title")}\n\n'
        f'> {_L("auto_generated", version=__version__, date=now)}\n'
        f'> {_L("fix_prompt")}\n'
    )

    # ── Summary table ─────────────────────────────────────────────────
    total_sys = summary.total_systems
    assigned_pct = round(summary.assigned_count / total_sys * 100) if total_sys else 0
    summary_md = (
        f'## {_L("summary_heading")}\n\n'
        f'| {_L("metric")} | {_L("value")} |\n'
        '|---------|----------|\n'
        f'| {_L("systems")} | {total_sys} |\n'
        f'| {_L("subsystems")} | {summary.total_subsystems} |\n'
        f'| {_L("meta_completeness")} | {summary.meta_completeness_pct}% |\n'
        f'| {_L("domain_assigned")} | {summary.assigned_count} / {total_sys} ({assigned_pct}%) |\n'
        f'| {_L("integrations")} | {summary.total_integrations} |\n'
        f'| {_L("data_entities")} | {summary.total_entities} |\n'
        f'| {_L("deploy_mappings")} | {summary.deployment_mappings} |\n'
    )

    # ── Render incident sections ──────────────────────────────────────
    sections: list[str] = []
    suppressed_total = sum(inc.suppressed_count for inc in all_incidents)

    for inc in incidents:
        section = f'## {inc.qa_id}. [{inc.severity}] {inc.title} ({inc.count})\n\n'
        section += f'**{_L("problem")}:** {inc.description}\n\n'
        section += f'**{_L("impact_label")}:** {inc.impact}\n\n'
        section += f'**{_L("recommendation")}:**\n{inc.remediation}\n'

        if inc.affected:
            section += '\n'
            section += _render_affected_table(inc, lang)

        sections.append(section)

    # ── Assemble ──────────────────────────────────────────────────────
    suppressed_qa_ids = [inc.qa_id for inc in all_incidents if inc.suppressed]
    suppress_note = ''
    if suppressed_total > 0:
        suppress_note = _L('suppressed_note', count=suppressed_total)
    if suppressed_qa_ids:
        suppress_note += _L('suppressed_qa_note', ids=', '.join(suppressed_qa_ids))
    if not sections:
        return (
            header + '\n'
            + summary_md + '\n'
            + f'{_L("no_incidents")}{suppress_note}\n'
        )

    body = '\n---\n\n'.join(sections)
    footer_text = _L('footer', qa_num=len(incidents),
                      suppress_note=suppress_note, version=__version__)
    footer = f'\n---\n\n*{footer_text}*\n'
    return header + '\n' + summary_md + '\n---\n\n' + body + footer


def _render_affected_table(inc: 'AuditIncident', lang: str) -> str:
    """Render incident's affected items as a markdown table."""
    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    if not inc.affected:
        return ''

    # Determine columns from first affected item
    keys = list(inc.affected[0].keys())

    # QA-2 has special rendering with field_stats sub-tables
    if inc.qa_id == 'QA-2':
        return _render_qa2_table(inc, lang)

    # QA-10 has element/kind/issue columns
    if inc.qa_id == 'QA-10':
        header = f'| {_L("col_num")} | {_L("col_element")} | {_L("col_kind")} | {_L("col_issue")} |\n'
        header += '|---|---------|------|----------|\n'
        rows = []
        for i, item in enumerate(inc.affected, 1):
            rows.append(f'| {i} | {item.get("name", "")} | {item.get("kind", "")} | {item.get("issue", "")} |')
        return header + '\n'.join(rows) + '\n'

    # Generic table based on keys
    col_map = {
        'name': _L('col_system'),
        'tags': _L('col_tags'),
        'domain': _L('col_domain'),
        'subsystem_count': _L('col_subsystems'),
    }
    col_headers = [_L('col_num')] + [col_map.get(k, k) for k in keys]
    header = '| ' + ' | '.join(col_headers) + ' |\n'
    header += '|' + '|'.join('---' for _ in col_headers) + '|\n'

    shown = inc.affected
    suffix = ''
    if inc.count > len(shown):
        suffix = _L('shown_first', n=len(shown), total=inc.count)

    rows = []
    for i, item in enumerate(shown, 1):
        vals = [str(i)] + [str(item.get(k, '')) for k in keys]
        rows.append('| ' + ' | '.join(vals) + ' |')

    return header + '\n'.join(rows) + suffix + '\n'


def _render_qa2_table(inc: 'AuditIncident', lang: str) -> str:
    """Render QA-2 metadata gap tables (field completeness + top systems)."""
    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    # Top-N systems with most empty fields
    top_n = min(20, len(inc.affected))
    top_header = f'| {_L("col_num")} | {_L("col_system")} | {_L("col_domain")} | {_L("col_empty_fields")} |\n'
    top_header += '|---|---------|-------|--------------|\n'
    rows = []
    for i, item in enumerate(inc.affected[:top_n], 1):
        rows.append(f'| {i} | {item["name"]} | {item.get("domain", "")} '
                    f'| {item["tbd_count"]} / {item.get("total_fields", "")} |')

    return (
        f'\n**{_L("top_systems", n=top_n)}:**\n\n'
        + top_header + '\n'.join(rows) + '\n'
    )
